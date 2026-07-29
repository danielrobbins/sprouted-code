from __future__ import annotations

import shlex

from .commands import CommandRunner
from .config import BuildConfig
from .wsl import WslBuilder, resolve_wsl_builder, run_wsl_script


def build_wsl_provision_script(
    config: BuildConfig,
    builder: WslBuilder,
    *,
    install_packages: bool,
    install_node: bool,
    clone: bool,
) -> str:
    checkout = shlex.quote(builder.checkout)
    node_version = shlex.quote(builder.node_version)
    node_arch = shlex.quote(builder.node_platform_architecture)
    upstream_url = shlex.quote(str(config.require("source.upstream_url")))

    commands: list[str] = []
    if install_packages:
        sudo = "" if builder.user == "root" else "sudo "
        compiler_packages = f"{shlex.quote(builder.cc)} {shlex.quote(builder.cxx)}"
        repository_commands = ""
        if builder.apt_repositories:
            repositories = "\n".join(
                f"{sudo}add-apt-repository -y {shlex.quote(repository)}"
                for repository in builder.apt_repositories
            )
            repository_commands = (
                f"{sudo}apt-get install -y software-properties-common\n"
                f"{repositories}\n"
                f"{sudo}apt-get update\n"
            )
        commands.append(
            f"{sudo}apt-get update\n"
            f"{repository_commands}"
            f"{sudo}DEBIAN_FRONTEND=noninteractive apt-get install -y "
            "ca-certificates curl xz-utils git python3 "
            "build-essential pkg-config libx11-dev libxkbfile-dev "
            f"libsecret-1-dev libkrb5-dev fakeroot rpm jq {compiler_packages}"
        )
    if install_node:
        commands.append(
            'mkdir -p "$HOME/.local"\n'
            'if [ ! -x "$node_dir/bin/node" ]; then\n'
            '  archive="/tmp/node-v${node_version}-linux-'
            f'{builder.node_platform_architecture}.tar.xz"\n'
            '  curl -fsSL "https://nodejs.org/dist/v${node_version}/'
            f'node-v${{node_version}}-linux-{builder.node_platform_architecture}.tar.xz" '
            '-o "$archive"\n'
            '  tar -xJf "$archive" -C "$HOME/.local"\n'
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
set -euo pipefail
checkout={checkout}
checkout="${{checkout/#\\~/$HOME}}"
node_version={node_version}
node_dir="$HOME/.local/node-v${{node_version}}-linux-{node_arch}"
{body}
echo "WSL provisioning complete: distro={builder.distro} arch={builder.architecture} checkout=$checkout"
""".strip()


def provision_wsl(
    config: BuildConfig,
    runner: CommandRunner,
    *,
    architecture: str | None = None,
    install_packages: bool = False,
    install_node: bool = False,
    clone: bool = False,
) -> WslBuilder:
    builder = resolve_wsl_builder(config, architecture=architecture)
    script = build_wsl_provision_script(
        config,
        builder,
        install_packages=install_packages,
        install_node=install_node,
        clone=clone,
    )
    run_wsl_script(builder, runner, script)
    return builder
