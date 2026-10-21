from __future__ import annotations

import base64
import shlex

from .commands import CommandRunner
from .config import BuildConfig
from .manifest import ReleaseManifest
from .patches import resolve_build_patches
from .proxmox import ProxmoxBuilder, resolve_proxmox_builder, run_container_script


def build_proxmox_prepare_script(
    config: BuildConfig,
    manifest: ReleaseManifest,
    builder: ProxmoxBuilder,
    *,
    skip_fetch: bool = False,
) -> str:
    upstream_url = shlex.quote(str(config.require("source.upstream_url")))
    branch_prefix = str(config.require("source.build_branch_prefix")).rstrip("/")
    file_patches = resolve_build_patches(config, manifest)

    commands = ["mkdir -p /root/sprouted/patches"]
    for patch in file_patches:
        encoded = base64.b64encode(patch.read_bytes()).decode("ascii")
        destination = f"/root/sprouted/patches/{patch.name}"
        commands.append(
            f"printf %s {shlex.quote(encoded)} | base64 -d > {shlex.quote(destination)}"
        )

    commands.extend(
        (
            'cd "$checkout"',
            'if [ -n "$(git status --porcelain)" ]; then\n'
            '  echo "Refusing to prepare a dirty VS Code checkout: $checkout" >&2\n'
            "  exit 2\nfi",
        )
    )
    if not skip_fetch:
        commands.append(f"git fetch {upstream_url} {shlex.quote(manifest.base_branch)}")
    build_branch = f"{branch_prefix}/{manifest.release}"
    commands.append(
        f"git switch -C {shlex.quote(build_branch)} {shlex.quote(manifest.base_commit)}"
    )
    for patch in file_patches:
        remote_path = f"/root/sprouted/patches/{patch.name}"
        commands.extend(
            (
                f"git apply --ignore-whitespace --check {shlex.quote(remote_path)}",
                f"git apply --ignore-whitespace {shlex.quote(remote_path)}",
            )
        )
    if file_patches:
        commands.extend(
            (
                "git add --all",
                "git -c user.name='Sprouted Code Build' "
                "-c user.email='sprouted-code-build@localhost' "
                "commit -m 'Apply Sprouted Code local patch queue'",
            )
        )
    commands.append("git status --short --branch")
    body = "\n".join(commands)
    return f"""
#!/usr/bin/env bash
set -euo pipefail
export LANG=C.UTF-8
export LC_ALL=C.UTF-8
checkout={shlex.quote(builder.checkout)}
if [ ! -d "$checkout/.git" ]; then
  echo "Proxmox VS Code checkout not found: $checkout" >&2
  exit 2
fi
{body}
""".strip()


def prepare_proxmox_checkout(
    config: BuildConfig,
    manifest: ReleaseManifest,
    runner: CommandRunner,
    *,
    skip_fetch: bool = False,
    architecture: str | None = None,
) -> ProxmoxBuilder:
    builder = resolve_proxmox_builder(config, architecture=architecture)
    script = build_proxmox_prepare_script(
        config, manifest, builder, skip_fetch=skip_fetch
    )
    run_container_script(
        builder,
        runner,
        script,
        name=f"sprouted-prepare-linux-proxmox-{builder.architecture}",
    )
    return builder
