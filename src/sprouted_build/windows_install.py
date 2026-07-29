from __future__ import annotations

import shutil
import subprocess
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Sequence

from .config import BuildConfig, ConfigError
from .manifest import ReleaseManifest
from .windows_build import WINDOWS_ARCHITECTURES, windows_artifact_name


@dataclass(frozen=True)
class WindowsPortablePaths:
    install_directory: Path
    executable: Path
    cli: Path
    user_data_directory: Path
    extensions_directory: Path


def windows_portable_paths(
    config: BuildConfig,
    *,
    user_data_directory: Path | None = None,
    extensions_directory: Path | None = None,
) -> WindowsPortablePaths:
    install_directory = config.resolve_path("builders.windows.install_dir")
    return WindowsPortablePaths(
        install_directory=install_directory,
        executable=install_directory / "Sprouted Code.exe",
        cli=install_directory / "bin" / "sprouted-code.cmd",
        user_data_directory=(
            user_data_directory.resolve()
            if user_data_directory
            else install_directory / "data" / "user-data"
        ),
        extensions_directory=(
            extensions_directory.resolve()
            if extensions_directory
            else install_directory / "data" / "extensions"
        ),
    )


def resolve_windows_artifact(
    config: BuildConfig,
    manifest: ReleaseManifest,
    *,
    architecture: str,
    flavor: str = "release",
    artifact_path: Path | None = None,
) -> Path:
    if architecture not in WINDOWS_ARCHITECTURES:
        raise ConfigError(f"Unsupported Windows architecture: {architecture}")
    selected = (
        artifact_path.expanduser().resolve()
        if artifact_path
        else config.resolve_path("paths.artifacts")
        / windows_artifact_name(manifest.release, architecture, flavor)
    )
    if not selected.is_file():
        raise FileNotFoundError(
            f"Windows artifact not found: {selected}. Build it first or pass --artifact."
        )
    return selected


def _validate_install_target(target: Path) -> None:
    resolved = target.resolve()
    anchor = Path(resolved.anchor)
    if resolved == anchor or resolved == Path.home().resolve():
        raise ConfigError(f"Refusing to replace unsafe install path: {resolved}")
    if len(resolved.parts) < 3:
        raise ConfigError(f"Refusing to replace shallow install path: {resolved}")
    if not resolved.parent.is_dir():
        raise ConfigError(f"Install directory parent does not exist: {resolved.parent}")


def _validated_zip_members(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    members = archive.infolist()
    for member in members:
        normalized_name = member.filename.replace("\\", "/")
        path = PurePosixPath(normalized_name)
        has_drive = bool(path.parts and path.parts[0].endswith(":"))
        if path.is_absolute() or has_drive or ".." in path.parts:
            raise ConfigError(f"Artifact contains an unsafe path: {member.filename}")
    return members


def _remove_generated_directory(path: Path, *, parent: Path) -> None:
    resolved = path.resolve()
    if resolved.parent != parent.resolve():
        raise ConfigError(f"Refusing to remove unexpected generated path: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)


def install_windows_artifact(
    config: BuildConfig,
    artifact_path: Path,
    *,
    preserve_user_data: bool = False,
) -> WindowsPortablePaths:
    paths = windows_portable_paths(config)
    target = paths.install_directory
    _validate_install_target(target)

    suffix = uuid.uuid4().hex
    staging = target.parent / f".{target.name}.staging-{suffix}"
    backup = target.parent / f".{target.name}.backup-{suffix}"

    try:
        staging.mkdir()
        try:
            with zipfile.ZipFile(artifact_path) as archive:
                members = _validated_zip_members(archive)
                archive.extractall(staging, members=members)
        except zipfile.BadZipFile as error:
            raise ConfigError(
                f"Invalid Windows artifact ZIP: {artifact_path}"
            ) from error

        staged_executable = staging / "Sprouted Code.exe"
        staged_cli = staging / "bin" / "sprouted-code.cmd"
        if not staged_executable.is_file():
            raise ConfigError(
                f"Artifact does not contain Sprouted Code.exe at its root: {artifact_path}"
            )
        if not staged_cli.is_file():
            raise ConfigError(
                f"Artifact does not contain bin/sprouted-code.cmd: {artifact_path}"
            )

        if target.exists():
            target.rename(backup)
        preserved: list[tuple[Path, Path]] = []
        try:
            staging.rename(target)
            if preserve_user_data and backup.exists():
                for relative in (Path("data"), Path("extensions")):
                    source = backup / relative
                    destination = target / relative
                    if source.exists():
                        if destination.exists():
                            shutil.rmtree(destination)
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        source.rename(destination)
                        preserved.append((source, destination))
        except Exception:
            for source, destination in reversed(preserved):
                source.parent.mkdir(parents=True, exist_ok=True)
                destination.rename(source)
            if target.exists():
                _remove_generated_directory(target, parent=target.parent)
            if backup.exists():
                backup.rename(target)
            raise

        if backup.exists():
            _remove_generated_directory(backup, parent=target.parent)
    finally:
        if staging.exists():
            _remove_generated_directory(staging, parent=target.parent)

    print(f"Installed Sprouted Code: {paths.executable}")
    return paths


def build_windows_launch_command(
    paths: WindowsPortablePaths,
    *,
    disable_workspace_trust: bool = False,
    extra_arguments: Sequence[str] = (),
) -> list[str]:
    command = [
        str(paths.cli),
        "--user-data-dir",
        str(paths.user_data_directory),
        "--extensions-dir",
        str(paths.extensions_directory),
    ]
    if disable_workspace_trust:
        command.append("--disable-workspace-trust")
    command.extend(extra_arguments)
    return command


def launch_windows(
    config: BuildConfig,
    *,
    user_data_directory: Path | None = None,
    extensions_directory: Path | None = None,
    disable_workspace_trust: bool = False,
    extra_arguments: Sequence[str] = (),
) -> subprocess.Popen[bytes]:
    paths = windows_portable_paths(
        config,
        user_data_directory=user_data_directory,
        extensions_directory=extensions_directory,
    )
    if not paths.executable.is_file():
        raise FileNotFoundError(
            f"Sprouted Code executable not found: {paths.executable}. Install it first."
        )
    if not paths.cli.is_file():
        raise FileNotFoundError(
            f"Sprouted Code CLI shim not found: {paths.cli}. Install it first."
        )

    paths.user_data_directory.mkdir(parents=True, exist_ok=True)
    paths.extensions_directory.mkdir(parents=True, exist_ok=True)
    command = build_windows_launch_command(
        paths,
        disable_workspace_trust=disable_workspace_trust,
        extra_arguments=extra_arguments,
    )
    print(f"Launching {paths.executable}")
    print(f"  user-data-dir: {paths.user_data_directory}")
    print(f"  extensions-dir: {paths.extensions_directory}")

    creation_flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    return subprocess.Popen(command, creationflags=creation_flags)
