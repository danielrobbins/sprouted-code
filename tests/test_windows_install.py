from pathlib import Path
import zipfile

import pytest

from sprouted_build.config import BuildConfig, ConfigError
from sprouted_build.manifest import ReleaseManifest
from sprouted_build.windows_install import (
    build_windows_launch_command,
    install_windows_artifact,
    resolve_windows_artifact,
    windows_portable_paths,
)


def _config(tmp_path: Path, install_directory: Path) -> BuildConfig:
    return BuildConfig(
        data={
            "paths": {"artifacts": str(tmp_path / "artifacts")},
            "builders": {"windows": {"install_dir": str(install_directory)}},
        },
        repo_root=tmp_path,
        sources=(),
    )


def _artifact(path: Path, *, unsafe_name: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("Sprouted Code.exe", b"new executable")
        archive.writestr("bin/sprouted-code.cmd", b"launch")
        if unsafe_name:
            archive.writestr(unsafe_name, b"escape")


def test_install_replaces_application_and_preserves_portable_data(
    tmp_path: Path,
) -> None:
    install = tmp_path / "tools" / "Sprouted Code"
    install.mkdir(parents=True)
    (install / "old.txt").write_text("old", encoding="utf-8")
    (install / "data" / "user-data").mkdir(parents=True)
    (install / "data" / "user-data" / "state.json").write_text("state")
    (install / "extensions").mkdir()
    (install / "extensions" / "legacy.txt").write_text("extension")
    artifact = tmp_path / "artifact.zip"
    _artifact(artifact)

    paths = install_windows_artifact(
        _config(tmp_path, install), artifact, preserve_user_data=True
    )

    assert paths.executable.read_bytes() == b"new executable"
    assert not (install / "old.txt").exists()
    assert (install / "data" / "user-data" / "state.json").read_text() == "state"
    assert (install / "extensions" / "legacy.txt").read_text() == "extension"


def test_install_rejects_archive_path_traversal_before_replacing_install(
    tmp_path: Path,
) -> None:
    install = tmp_path / "tools" / "Sprouted Code"
    install.mkdir(parents=True)
    marker = install / "still-here.txt"
    marker.write_text("safe", encoding="utf-8")
    artifact = tmp_path / "unsafe.zip"
    _artifact(artifact, unsafe_name="../escaped.txt")

    with pytest.raises(ConfigError, match="unsafe path"):
        install_windows_artifact(_config(tmp_path, install), artifact)

    assert marker.read_text(encoding="utf-8") == "safe"
    assert not (tmp_path / "escaped.txt").exists()


def test_install_reports_invalid_zip_without_replacing_install(tmp_path: Path) -> None:
    install = tmp_path / "tools" / "Sprouted Code"
    install.mkdir(parents=True)
    marker = install / "still-here.txt"
    marker.write_text("safe", encoding="utf-8")
    artifact = tmp_path / "invalid.zip"
    artifact.write_bytes(b"not a zip")

    with pytest.raises(ConfigError, match="Invalid Windows artifact ZIP"):
        install_windows_artifact(_config(tmp_path, install), artifact)

    assert marker.read_text(encoding="utf-8") == "safe"


@pytest.mark.parametrize("unsafe_name", [r"..\escaped.txt", "C:/escaped.txt"])
def test_install_rejects_windows_specific_unsafe_paths(
    tmp_path: Path, unsafe_name: str
) -> None:
    install = tmp_path / "tools" / "Sprouted Code"
    install.mkdir(parents=True)
    artifact = tmp_path / "unsafe.zip"
    _artifact(artifact, unsafe_name=unsafe_name)

    with pytest.raises(ConfigError, match="unsafe path"):
        install_windows_artifact(_config(tmp_path, install), artifact)


def test_launch_command_uses_portable_directories_and_extra_arguments(
    tmp_path: Path,
) -> None:
    install = tmp_path / "tools" / "Sprouted Code"
    paths = windows_portable_paths(_config(tmp_path, install))

    command = build_windows_launch_command(
        paths,
        disable_workspace_trust=True,
        extra_arguments=("--new-window", str(tmp_path / "workspace")),
    )

    assert command == [
        str(install / "bin" / "sprouted-code.cmd"),
        "--user-data-dir",
        str(install / "data" / "user-data"),
        "--extensions-dir",
        str(install / "data" / "extensions"),
        "--disable-workspace-trust",
        "--new-window",
        str(tmp_path / "workspace"),
    ]


def test_resolve_artifact_requires_exact_release_and_architecture(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path, tmp_path / "tools" / "Sprouted Code")
    manifest = ReleaseManifest(
        path=tmp_path / "manifest.json",
        release="2026.07.0",
        base_repo="upstream",
        base_commit="abc",
        base_branch="main",
        patches=(),
    )
    artifact = tmp_path / "artifacts" / "sprouted-code-2026.07.0-win32-x64.zip"
    _artifact(artifact)

    assert (
        resolve_windows_artifact(config, manifest, architecture="x64")
        == artifact.resolve()
    )
