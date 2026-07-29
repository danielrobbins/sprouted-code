import zipfile
from pathlib import Path

import pytest

from sprouted_build.commands import CommandRunner
from sprouted_build.config import BuildConfig
from sprouted_build.config import ConfigError
from sprouted_build.manifest import ReleaseManifest
from sprouted_build.windows import WindowsToolchain
from sprouted_build.windows_build import (
    archive_directory,
    build_windows,
    windows_artifact_name,
)


def test_windows_artifact_name_contains_release_and_architecture() -> None:
    assert (
        windows_artifact_name("2026.07.0", "arm64")
        == "sprouted-code-2026.07.0-win32-arm64.zip"
    )


def test_diagnostic_windows_artifact_is_labeled() -> None:
    assert (
        windows_artifact_name("2026.07.0", "x64", "diagnostic")
        == "sprouted-code-2026.07.0-win32-x64-diagnostic.zip"
    )


def test_windows_artifact_name_rejects_unknown_architecture() -> None:
    with pytest.raises(ConfigError, match="Unsupported Windows architecture"):
        windows_artifact_name("2026.07.0", "mips")


def test_archive_contains_directory_contents_without_outer_directory(
    tmp_path: Path,
) -> None:
    package = tmp_path / "VSCode-win32-arm64"
    (package / "bin").mkdir(parents=True)
    (package / "Sprouted Code.exe").write_bytes(b"exe")
    (package / "bin" / "sprouted-code.cmd").write_text("launch", encoding="utf-8")
    destination = tmp_path / "sprouted.zip"

    archive_directory(package, destination)

    with zipfile.ZipFile(destination) as archive:
        assert archive.namelist() == [
            "Sprouted Code.exe",
            "bin/sprouted-code.cmd",
        ]


def test_windows_build_uses_locked_dependency_install(tmp_path: Path) -> None:
    checkout = tmp_path / "vscode"
    npm_command = tmp_path / "npm.cmd"
    config = BuildConfig(
        data={"paths": {"artifacts": "artifacts"}},
        repo_root=tmp_path,
        sources=(),
    )
    manifest = ReleaseManifest(
        path=tmp_path / "manifest.json",
        release="2026.07.0",
        base_repo="microsoft/vscode",
        base_commit="base-commit",
        base_branch="main",
        patches=(),
        source_tree="a" * 40,
    )
    toolchain = WindowsToolchain(
        checkout=checkout,
        node_directory=tmp_path,
        node_version="24.18.0",
        npm_command=npm_command,
        visual_studio_path=None,
        signtool_directory=None,
        environment={},
    )
    runner = CommandRunner(dry_run=True)

    build_windows(
        config,
        manifest,
        toolchain,
        runner,
        architecture="arm64",
        skip_tests=True,
        skip_gulp=True,
        no_archive=True,
    )

    assert runner.commands == [
        ("git", "status", "--porcelain"),
        ("git", "rev-parse", "HEAD^{tree}"),
        (str(npm_command), "ci"),
    ]
