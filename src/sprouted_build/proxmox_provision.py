from __future__ import annotations

import shlex

from .commands import CommandRunner
from .config import BuildConfig
from .proxmox import ProxmoxBuilder, resolve_proxmox_builder, run_container_script


def build_proxmox_provision_script(
    config: BuildConfig,
    builder: ProxmoxBuilder,
    *,
    install_packages: bool,
    install_node: bool,
    clone: bool,
) -> str:
    upstream_url = shlex.quote(str(config.require("source.upstream_url")))
    commands: list[str] = []
    if install_packages:
        compiler_packages = f"{shlex.quote(builder.cc)} {shlex.quote(builder.cxx)}"
        repository_commands = ""
        if builder.apt_repositories:
            repositories = "\n".join(
                f"add-apt-repository -y {shlex.quote(repository)}"
                for repository in builder.apt_repositories
            )
            repository_commands = (
                "apt-get install -y software-properties-common\n"
                f"{repositories}\n"
                "apt-get update\n"
            )
        commands.append(
            "export DEBIAN_FRONTEND=noninteractive\n"
            "apt-get update\n"
            f"{repository_commands}"
            "apt-get install -y ca-certificates curl xz-utils git python3 "
            "build-essential pkg-config libx11-dev libxkbfile-dev "
            f"libsecret-1-dev libkrb5-dev fakeroot rpm jq {compiler_packages}"
        )
    if install_node:
        commands.append(
            f"mkdir -p {shlex.quote(builder.node_root)}\n"
            'if [ ! -x "$node_dir/bin/node" ]; then\n'
            '  archive="/tmp/node-v${node_version}-linux-${node_arch}.tar.xz"\n'
            '  curl -fsSL "https://nodejs.org/dist/v${node_version}/'
            'node-v${node_version}-linux-${node_arch}.tar.xz" -o "$archive"\n'
            f'  tar -xJf "$archive" -C {shlex.quote(builder.node_root)}\n'
            "fi"
        )
    if clone:
        commands.append(
            'mkdir -p "$(dirname "$checkout")"\n'
            'if [ ! -d "$checkout/.git" ]; then\n'
            f'  git clone {upstream_url} "$checkout"\n'
            "fi\n"
            'cd "$checkout"\n'
            "if git remote get-url origin >/dev/null 2>&1; then\n"
            f"  git remote set-url origin {upstream_url}\n"
            "else\n"
            f"  git remote add origin {upstream_url}\n"
            "fi"
        )
    body = "\n".join(commands) or ":"
    return f"""
#!/usr/bin/env bash
set -euo pipefail
export LANG=C.UTF-8
export LC_ALL=C.UTF-8
checkout={shlex.quote(builder.checkout)}
node_version={shlex.quote(builder.node_version)}
node_arch={shlex.quote(builder.node_platform_architecture)}
node_dir={shlex.quote(builder.node_directory)}
{body}
echo "Proxmox provisioning complete: container={builder.container_id} checkout=$checkout"
""".strip()


def provision_proxmox(
    config: BuildConfig,
    runner: CommandRunner,
    *,
    install_packages: bool = False,
    install_node: bool = False,
    clone: bool = False,
    architecture: str | None = None,
) -> ProxmoxBuilder:
    builder = resolve_proxmox_builder(config, architecture=architecture)
    script = build_proxmox_provision_script(
        config,
        builder,
        install_packages=install_packages,
        install_node=install_node,
        clone=clone,
    )
    run_container_script(
        builder,
        runner,
        script,
        name=f"sprouted-provision-linux-proxmox-{builder.architecture}",
    )
    return builder
