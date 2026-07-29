from __future__ import annotations

import shlex

from .commands import CommandRunner
from .config import BuildConfig
from .macos import MacOSBuilder, resolve_macos_builder, run_macos_script


def build_macos_provision_script(
    config: BuildConfig,
    builder: MacOSBuilder,
    *,
    install_node: bool,
    clone: bool,
) -> str:
    upstream_url = shlex.quote(str(config.require("source.upstream_url")))
    commands: list[str] = []
    if install_node:
        commands.append(
            'mkdir -p "$node_root"\n'
            'if [ ! -x "$node_dir/bin/node" ]; then\n'
            '  archive="/tmp/node-v${node_version}-darwin-arm64.tar.gz"\n'
            '  curl -fsSL "https://nodejs.org/dist/v${node_version}/'
            'node-v${node_version}-darwin-arm64.tar.gz" -o "$archive"\n'
            '  tar -xzf "$archive" -C "$node_root"\n'
            '  rm -f "$archive"\n'
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
checkout={shlex.quote(builder.checkout)}
checkout="${{checkout/#\\~/$HOME}}"
node_root={shlex.quote(builder.node_root)}
node_root="${{node_root/#\\~/$HOME}}"
node_version={shlex.quote(builder.node_version)}
node_dir={shlex.quote(builder.node_directory)}
node_dir="${{node_dir/#\\~/$HOME}}"
{body}
echo "macOS provisioning complete: arch={builder.architecture} checkout=$checkout"
""".strip()


def provision_macos(
    config: BuildConfig,
    runner: CommandRunner,
    *,
    install_node: bool = False,
    clone: bool = False,
    architecture: str | None = None,
) -> MacOSBuilder:
    builder = resolve_macos_builder(config, architecture=architecture)
    script = build_macos_provision_script(
        config,
        builder,
        install_node=install_node,
        clone=clone,
    )
    run_macos_script(
        builder,
        runner,
        script,
        name=f"sprouted-provision-macos-{builder.architecture}",
    )
    return builder
