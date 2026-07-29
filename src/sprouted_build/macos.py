from __future__ import annotations

import re
import shlex
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

from .commands import CommandRunner
from .config import BuildConfig, ConfigError


MACOS_ARCHITECTURES = ("arm64",)


@dataclass(frozen=True)
class MacOSBuilder:
    ssh_target: str
    architecture: str
    checkout: str
    node_root: str
    artifact_directory: str
    node_version: str

    @property
    def node_directory(self) -> str:
        return f"{self.node_root}/node-v{self.node_version}-darwin-{self.architecture}"


def resolve_macos_builder(
    config: BuildConfig,
    *,
    architecture: str | None = None,
) -> MacOSBuilder:
    selected_architecture = architecture or str(
        config.require("builders.macos.default_architecture")
    )
    if selected_architecture not in MACOS_ARCHITECTURES:
        raise ConfigError(
            f"Unsupported macOS architecture: {selected_architecture}. "
            f"Expected one of: {', '.join(MACOS_ARCHITECTURES)}"
        )
    prefix = f"builders.macos.{selected_architecture}"
    return MacOSBuilder(
        ssh_target=str(config.require(f"{prefix}.ssh_target")),
        architecture=selected_architecture,
        checkout=str(config.require(f"{prefix}.vscode_checkout")),
        node_root=str(config.require(f"{prefix}.node_root")).rstrip("/"),
        artifact_directory=str(config.require(f"{prefix}.artifact_directory")).rstrip(
            "/"
        ),
        node_version=str(config.require("toolchain.node_version")),
    )


def run_macos_host_command(
    builder: MacOSBuilder,
    runner: CommandRunner,
    command: str,
) -> None:
    runner.run(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=10",
            builder.ssh_target,
            command,
        ]
    )


def run_macos_script(
    builder: MacOSBuilder,
    runner: CommandRunner,
    script: str,
    *,
    name: str,
) -> None:
    safe_name = re.sub(r"[^A-Za-z0-9_.-]", "-", name)
    remote_path = f"/tmp/{safe_name}-{uuid.uuid4().hex}.sh"
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            suffix=".sh",
            delete=False,
        ) as temporary:
            temporary.write(script.replace("\r\n", "\n").rstrip() + "\n")
            temporary_path = Path(temporary.name)
        runner.run(
            [
                "scp",
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=10",
                str(temporary_path),
                f"{builder.ssh_target}:{remote_path}",
            ]
        )
        command = (
            f"chmod +x {shlex.quote(remote_path)} && "
            f"{shlex.quote(remote_path)}; "
            "sprouted_status=$?; "
            f"rm -f {shlex.quote(remote_path)}; "
            "exit $sprouted_status"
        )
        run_macos_host_command(builder, runner, command)
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()


def build_macos_preflight_script(builder: MacOSBuilder) -> str:
    return f"""
#!/usr/bin/env bash
set -euo pipefail
checkout={shlex.quote(builder.checkout)}
checkout="${{checkout/#\\~/$HOME}}"
node_dir={shlex.quote(builder.node_directory)}
node_dir="${{node_dir/#\\~/$HOME}}"
if [ "$(uname -m)" != "arm64" ]; then
  echo "macOS ARM64 builds require arm64; found $(uname -m)" >&2
  exit 2
fi
if [ ! -d "$checkout/.git" ]; then
  echo "macOS VS Code checkout not found: $checkout" >&2
  exit 2
fi
export PATH="$node_dir/bin:$PATH"
for command in git python3 make curl tar zip shasum xcodebuild xcrun node npm; do
  command -v "$command" >/dev/null 2>&1 || {{ echo "Missing required command: $command" >&2; exit 2; }}
done
if [ "$(node --version)" != "v{builder.node_version}" ]; then
  echo "Wrong Node version: $(node --version); expected v{builder.node_version}" >&2
  exit 2
fi
xcode-select -p >/dev/null
xcrun --find clang >/dev/null
echo "macOS preflight OK: arch=$(uname -m) node=$(node --version) npm=$(npm --version) xcode=$(xcodebuild -version | tr '\\n' ' ') checkout=$checkout"
df -h "$HOME" | tail -n 1
""".strip()


def preflight_macos(
    config: BuildConfig,
    runner: CommandRunner,
    *,
    architecture: str | None = None,
) -> MacOSBuilder:
    builder = resolve_macos_builder(config, architecture=architecture)
    run_macos_script(
        builder,
        runner,
        build_macos_preflight_script(builder),
        name=f"sprouted-preflight-macos-{builder.architecture}",
    )
    return builder
