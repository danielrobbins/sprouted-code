from __future__ import annotations

import shlex
from pathlib import Path

from .commands import CommandRunner
from .config import BuildConfig, ConfigError
from .manifest import ReleaseManifest
from .patches import resolve_build_patches
from .wsl import WslBuilder, resolve_wsl_builder, run_wsl_script


def windows_path_to_wsl(path: Path) -> str:
    resolved = path.resolve()
    drive = resolved.drive.rstrip(":").lower()
    if len(drive) != 1 or not drive.isalpha():
        raise ConfigError(f"Cannot map non-drive-letter path into WSL: {resolved}")
    relative = resolved.relative_to(resolved.anchor).as_posix()
    return f"/mnt/{drive}/{relative}"


def build_wsl_prepare_script(
    config: BuildConfig,
    manifest: ReleaseManifest,
    builder: WslBuilder,
    *,
    skip_fetch: bool = False,
) -> str:
    checkout = shlex.quote(builder.checkout)
    branch_prefix = str(config.require("source.build_branch_prefix")).rstrip("/")
    build_branch = shlex.quote(f"{branch_prefix}/{manifest.release}")
    base_commit = shlex.quote(manifest.base_commit)
    upstream_url = shlex.quote(str(config.require("source.upstream_url")))

    file_patches = resolve_build_patches(config, manifest)
    commands: list[str] = []
    if not skip_fetch:
        commands.append(f"git fetch {upstream_url} {shlex.quote(manifest.base_branch)}")
    commands.append(f"git switch -C {build_branch} {base_commit}")

    for patch in file_patches:
        wsl_path = shlex.quote(windows_path_to_wsl(patch))
        commands.extend(
            (
                f"git apply --ignore-whitespace --check {wsl_path}",
                f"git apply --ignore-whitespace {wsl_path}",
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
set -euo pipefail
checkout={checkout}
checkout="${{checkout/#\\~/$HOME}}"
if [ ! -d "$checkout/.git" ]; then
  echo "WSL-native VS Code checkout not found: $checkout" >&2
  exit 2
fi
cd "$checkout"
if [ -n "$(git status --porcelain)" ]; then
  echo "Refusing to prepare a dirty VS Code checkout: $checkout" >&2
  exit 2
fi
{body}
""".strip()


def prepare_wsl_checkout(
    config: BuildConfig,
    manifest: ReleaseManifest,
    runner: CommandRunner,
    *,
    architecture: str | None = None,
    skip_fetch: bool = False,
) -> WslBuilder:
    builder = resolve_wsl_builder(config, architecture=architecture)
    script = build_wsl_prepare_script(
        config,
        manifest,
        builder,
        skip_fetch=skip_fetch,
    )
    run_wsl_script(builder, runner, script)
    return builder
