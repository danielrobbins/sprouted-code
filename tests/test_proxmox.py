from pathlib import Path

from sprouted_build.commands import CommandRunner
from sprouted_build.config import BuildConfig
from sprouted_build.proxmox import resolve_proxmox_builder, run_container_script


def _config(tmp_path: Path) -> BuildConfig:
    return BuildConfig(
        data={
            "toolchain": {"node_version": "24.18.0"},
            "builders": {
                "proxmox": {
                    "default_architecture": "x64",
                    "x64": {
                        "ssh_target": "builder@example.test",
                        "container_id": 303,
                        "remote_owner": "builder",
                        "vscode_checkout": "/root/build/vscode",
                        "node_root": "/root/.local",
                        "artifact_directory": "/root/artifacts",
                        "apt_repositories": ["ppa:ubuntu-toolchain-r/test"],
                    },
                    "arm64": {
                        "ssh_target": "arm-builder@example.test",
                        "container_id": 304,
                        "remote_owner": "builder",
                        "vscode_checkout": "/root/build/vscode",
                        "node_root": "/root/.local",
                        "artifact_directory": "/root/artifacts",
                    },
                }
            },
        },
        repo_root=tmp_path,
        sources=(),
    )


def test_resolve_proxmox_builder_uses_private_configuration(tmp_path: Path) -> None:
    builder = resolve_proxmox_builder(_config(tmp_path))

    assert builder.ssh_target == "builder@example.test"
    assert builder.container_id == 303
    assert builder.node_directory == "/root/.local/node-v24.18.0-linux-x64"
    assert builder.apt_repositories == ("ppa:ubuntu-toolchain-r/test",)


def test_resolve_proxmox_builder_selects_arm64_configuration(tmp_path: Path) -> None:
    builder = resolve_proxmox_builder(_config(tmp_path), architecture="arm64")

    assert builder.ssh_target == "arm-builder@example.test"
    assert builder.container_id == 304
    assert builder.host_architecture == "aarch64"
    assert builder.node_directory == "/root/.local/node-v24.18.0-linux-arm64"


def test_container_script_uses_scp_pct_push_and_pct_exec(tmp_path: Path) -> None:
    builder = resolve_proxmox_builder(_config(tmp_path))
    runner = CommandRunner(dry_run=True)

    run_container_script(builder, runner, "echo ready", name="preflight")

    assert runner.commands[0][0] == "scp"
    assert runner.commands[0][-1] == "builder@example.test:/tmp/preflight"
    assert runner.commands[1][0] == "ssh"
    assert "sudo pct push 303" in runner.commands[1][-1]
    assert "sudo pct exec 303" in runner.commands[1][-1]
