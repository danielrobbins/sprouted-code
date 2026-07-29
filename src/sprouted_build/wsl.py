from __future__ import annotations

import shlex
from dataclasses import dataclass

from .commands import CommandRunner
from .config import BuildConfig, ConfigError


LINUX_ARCHITECTURES = ("arm64", "x64")


@dataclass(frozen=True)
class WslBuilder:
    distro: str
    architecture: str
    checkout: str
    node_version: str
    cc: str = "gcc"
    cxx: str = "g++"
    apt_repositories: tuple[str, ...] = ()
    user: str | None = None

    @property
    def node_platform_architecture(self) -> str:
        return "arm64" if self.architecture == "arm64" else "x64"


def resolve_wsl_builder(
    config: BuildConfig,
    *,
    architecture: str | None = None,
) -> WslBuilder:
    selected_architecture = architecture or str(
        config.require("builders.wsl.default_architecture")
    )
    if selected_architecture not in LINUX_ARCHITECTURES:
        raise ConfigError(
            f"Unsupported WSL architecture: {selected_architecture}. "
            f"Expected one of: {', '.join(LINUX_ARCHITECTURES)}"
        )
    prefix = f"builders.wsl.{selected_architecture}"
    return WslBuilder(
        distro=str(config.require(f"{prefix}.distro")),
        architecture=selected_architecture,
        checkout=str(config.require(f"{prefix}.vscode_checkout")),
        node_version=str(config.require("toolchain.node_version")),
        cc=str(config.get(f"{prefix}.cc", "gcc")),
        cxx=str(config.get(f"{prefix}.cxx", "g++")),
        apt_repositories=config.string_tuple(f"{prefix}.apt_repositories"),
        user=(
            str(config.get(f"{prefix}.user")) if config.get(f"{prefix}.user") else None
        ),
    )


def _wsl_command(builder: WslBuilder) -> list[str]:
    command = [
        "wsl.exe",
        "-d",
        builder.distro,
    ]
    if builder.user:
        command.extend(("-u", builder.user))
    command.extend(
        (
            "--",
            "bash",
            "-c",
            "tr -d '\\r' | bash",
        )
    )
    return command


def run_wsl_script(
    builder: WslBuilder,
    runner: CommandRunner,
    script: str,
) -> None:
    runner.run(
        _wsl_command(builder),
        input_text=script.replace("\r\n", "\n").rstrip() + "\n",
    )


def build_wsl_preflight_script(builder: WslBuilder) -> str:
    expected_host = "aarch64" if builder.architecture == "arm64" else "x86_64"
    checkout = shlex.quote(builder.checkout)
    node_version = shlex.quote(builder.node_version)
    node_architecture = shlex.quote(builder.node_platform_architecture)
    script = f"""
set -euo pipefail
checkout={checkout}
checkout="${{checkout/#\\~/$HOME}}"
node_version={node_version}
node_dir="$HOME/.local/node-v${{node_version}}-linux-{node_architecture}"
expected_host={shlex.quote(expected_host)}
host_arch="$(uname -m)"

if [ "$host_arch" != "$expected_host" ]; then
  echo "WSL architecture mismatch: expected $expected_host, found $host_arch" >&2
  exit 2
fi
if [ ! -d "$checkout/.git" ]; then
  echo "WSL-native VS Code checkout not found: $checkout" >&2
  echo "Use a checkout in the Linux filesystem, not under /mnt/c." >&2
  exit 2
fi

clean_path="$(printf '%s' "$PATH" | tr ':' '\n' | grep -v '^/mnt/c/' | paste -sd: -)"
export PATH="$node_dir/bin:$clean_path"

missing=0
for command in git python3 {shlex.quote(builder.cc)} {shlex.quote(builder.cxx)} make pkg-config tar sha256sum node npm; do
  if ! command -v "$command" >/dev/null 2>&1; then
    echo "Missing required command: $command" >&2
    missing=1
  fi
done
if [ "$missing" -ne 0 ]; then
  exit 2
fi

actual_node="$(node --version)"
case "$actual_node" in
  v24.*) ;;
  *)
    echo "Wrong Node major: $actual_node. VS Code currently expects Node 24.x." >&2
    exit 2
    ;;
esac

required_node="$(tr -d '[:space:]' < "$checkout/.nvmrc")"
printf 'C compiler: %s; C++ compiler: %s\n' \
  "$({shlex.quote(builder.cc)} --version | head -1)" \
  "$({shlex.quote(builder.cxx)} --version | head -1)"
printf 'WSL preflight OK: distro=%s arch=%s node=%s npm=%s vscode=%s required_node=%s\n' \
  {shlex.quote(builder.distro)} "$host_arch" "$actual_node" "$(npm --version)" \
  "$checkout" "$required_node"
""".strip()
    return script.replace("\r\n", "\n")


def preflight_wsl(
    config: BuildConfig,
    runner: CommandRunner,
    *,
    architecture: str | None = None,
) -> WslBuilder:
    builder = resolve_wsl_builder(config, architecture=architecture)
    run_wsl_script(builder, runner, build_wsl_preflight_script(builder))
    return builder
