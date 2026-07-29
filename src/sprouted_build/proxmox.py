from __future__ import annotations

import re
import shlex
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .commands import CommandRunner
from .config import BuildConfig, ConfigError
from .wsl import LINUX_ARCHITECTURES


@dataclass(frozen=True)
class ProxmoxBuilder:
    ssh_target: str
    container_id: int
    remote_owner: str
    architecture: str
    checkout: str
    node_root: str
    artifact_directory: str
    node_version: str
    cc: str = "gcc"
    cxx: str = "g++"
    apt_repositories: tuple[str, ...] = ()

    @property
    def node_directory(self) -> str:
        return (
            f"{self.node_root}/node-v{self.node_version}-linux-"
            f"{self.node_platform_architecture}"
        )

    @property
    def node_platform_architecture(self) -> str:
        return "arm64" if self.architecture == "arm64" else "x64"

    @property
    def host_architecture(self) -> str:
        return "aarch64" if self.architecture == "arm64" else "x86_64"


def resolve_proxmox_builder(
    config: BuildConfig,
    *,
    architecture: str | None = None,
) -> ProxmoxBuilder:
    selected_architecture = architecture or str(
        config.require("builders.proxmox.default_architecture")
    )
    if selected_architecture not in LINUX_ARCHITECTURES:
        raise ConfigError(
            f"Unsupported Proxmox architecture: {selected_architecture}. "
            f"Expected one of: {', '.join(LINUX_ARCHITECTURES)}"
        )
    prefix = f"builders.proxmox.{selected_architecture}"
    try:
        container_id = int(config.require(f"{prefix}.container_id"))
    except (TypeError, ValueError) as error:
        raise ConfigError(f"{prefix}.container_id must be an integer") from error
    if container_id <= 0:
        raise ConfigError(f"{prefix}.container_id must be positive")
    remote_owner = str(config.require(f"{prefix}.remote_owner"))
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", remote_owner):
        raise ConfigError(f"Invalid Proxmox remote owner: {remote_owner!r}")
    return ProxmoxBuilder(
        ssh_target=str(config.require(f"{prefix}.ssh_target")),
        container_id=container_id,
        remote_owner=remote_owner,
        architecture=selected_architecture,
        checkout=str(config.require(f"{prefix}.vscode_checkout")),
        node_root=str(config.require(f"{prefix}.node_root")).rstrip("/"),
        artifact_directory=str(config.require(f"{prefix}.artifact_directory")).rstrip(
            "/"
        ),
        node_version=str(config.require("toolchain.node_version")),
        cc=str(config.get(f"{prefix}.cc", "gcc")),
        cxx=str(config.get(f"{prefix}.cxx", "g++")),
        apt_repositories=config.string_tuple(f"{prefix}.apt_repositories"),
    )


def run_proxmox_host_command(
    builder: ProxmoxBuilder,
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


def run_container_script(
    builder: ProxmoxBuilder,
    runner: CommandRunner,
    script: str,
    *,
    name: str,
) -> None:
    safe_name = re.sub(r"[^A-Za-z0-9_.-]", "-", name)
    host_path = f"/tmp/{safe_name}"
    container_path = f"/root/{safe_name}"
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
                f"{builder.ssh_target}:{host_path}",
            ]
        )
        command = (
            f"sudo pct push {builder.container_id} {shlex.quote(host_path)} "
            f"{shlex.quote(container_path)} && "
            f"sudo pct exec {builder.container_id} -- chmod +x "
            f"{shlex.quote(container_path)} && "
            f"sudo pct exec {builder.container_id} -- {shlex.quote(container_path)}"
        )
        run_proxmox_host_command(builder, runner, command)
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()
