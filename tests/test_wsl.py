from pathlib import Path

import pytest

from sprouted_build.commands import CommandRunner
from sprouted_build.config import BuildConfig, ConfigError
from sprouted_build.wsl import (
    build_wsl_preflight_script,
    preflight_wsl,
    resolve_wsl_builder,
)


def _config(tmp_path: Path, *, architecture: str = "arm64") -> BuildConfig:
    return BuildConfig(
        data={
            "toolchain": {"node_version": "24.18.0"},
            "builders": {
                "wsl": {
                    "default_architecture": architecture,
                    "arm64": {
                        "distro": "Ubuntu-Test",
                        "vscode_checkout": "~/repos/vscode",
                        "apt_repositories": ["ppa:ubuntu-toolchain-r/test"],
                        "user": "builder",
                    },
                    "x64": {
                        "distro": "Ubuntu-Test-x64",
                        "vscode_checkout": "~/src/vscode",
                    },
                }
            },
        },
        repo_root=tmp_path,
        sources=(),
    )


def test_resolve_wsl_builder_uses_configured_values(tmp_path: Path) -> None:
    builder = resolve_wsl_builder(_config(tmp_path))

    assert builder.distro == "Ubuntu-Test"
    assert builder.architecture == "arm64"
    assert builder.node_platform_architecture == "arm64"
    assert builder.checkout == "~/repos/vscode"
    assert builder.apt_repositories == ("ppa:ubuntu-toolchain-r/test",)
    assert builder.user == "builder"


def test_resolve_wsl_builder_rejects_unsupported_architecture(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="Unsupported WSL architecture"):
        resolve_wsl_builder(_config(tmp_path, architecture="mips"))


def test_x64_preflight_requires_x86_64_and_x64_node(tmp_path: Path) -> None:
    builder = resolve_wsl_builder(_config(tmp_path), architecture="x64")
    script = build_wsl_preflight_script(builder)

    assert builder.distro == "Ubuntu-Test-x64"
    assert builder.checkout == "~/src/vscode"
    assert "expected_host=x86_64" in script
    assert "node-v${node_version}-linux-x64" in script


def test_preflight_invokes_configured_distro_without_executing(tmp_path: Path) -> None:
    runner = CommandRunner(dry_run=True)

    preflight_wsl(_config(tmp_path), runner)

    command = runner.commands[0]
    assert command == (
        "wsl.exe",
        "-d",
        "Ubuntu-Test",
        "-u",
        "builder",
        "--",
        "bash",
        "-c",
        "tr -d '\\r' | bash",
    )
