from pathlib import Path

import pytest

from sprouted_build.commands import CommandRunner
from sprouted_build.config import BuildConfig, ConfigError
from sprouted_build.macos import (
    MacOSBuilder,
    build_macos_preflight_script,
    resolve_macos_builder,
    run_macos_script,
)


def _config(tmp_path: Path) -> BuildConfig:
    return BuildConfig(
        data={
            "toolchain": {"node_version": "24.18.0"},
            "builders": {
                "macos": {
                    "default_architecture": "arm64",
                    "arm64": {
                        "ssh_target": "builder@mac",
                        "vscode_checkout": "/Users/builder/repos/vscode",
                        "node_root": "/Users/builder/.local",
                        "artifact_directory": "/Users/builder/artifacts",
                    },
                }
            },
        },
        repo_root=tmp_path,
        sources=(),
    )


def test_resolve_macos_builder_uses_native_arm64_configuration(
    tmp_path: Path,
) -> None:
    builder = resolve_macos_builder(_config(tmp_path))

    assert builder.architecture == "arm64"
    assert builder.node_directory.endswith("node-v24.18.0-darwin-arm64")


def test_macos_builder_rejects_unsupported_architecture(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="Unsupported macOS architecture"):
        resolve_macos_builder(_config(tmp_path), architecture="x64")


def test_macos_preflight_requires_xcode_and_exact_node() -> None:
    builder = MacOSBuilder(
        "builder@mac",
        "arm64",
        "/Users/builder/repos/vscode",
        "/Users/builder/.local",
        "/Users/builder/artifacts",
        "24.18.0",
    )

    script = build_macos_preflight_script(builder)

    assert 'uname -m)" != "arm64"' in script
    assert "xcode-select -p" in script
    assert '$(node --version)" != "v24.18.0"' in script
    assert "xcrun --find clang" in script


def test_macos_runner_dry_run_uses_ssh(tmp_path: Path) -> None:
    builder = resolve_macos_builder(_config(tmp_path))
    runner = CommandRunner(dry_run=True)

    from sprouted_build.macos import run_macos_host_command

    run_macos_host_command(builder, runner, "true")

    assert runner.commands[0][0] == "ssh"
    assert "builder@mac" in runner.commands[0]


def test_macos_script_wrapper_avoids_reserved_zsh_status(
    tmp_path: Path,
) -> None:
    builder = resolve_macos_builder(_config(tmp_path))
    runner = CommandRunner(dry_run=True)

    run_macos_script(builder, runner, "true", name="test")

    remote_command = runner.commands[1][-1]
    assert "sprouted_status=$?" in remote_command
    assert "; status=$?" not in remote_command
