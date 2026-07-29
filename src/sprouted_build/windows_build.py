from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path

from .artifacts import write_checksums
from .commands import CommandRunner
from .config import BuildConfig, ConfigError
from .flavors import (
    artifact_flavor_suffix,
    environment_for_flavor,
    gulp_target,
    validate_build_flavor,
)
from .focused_tests import run_focused_windows_tests
from .manifest import ReleaseManifest
from .provenance import (
    clean_output_directory,
    expected_provenance,
    verify_checkout_provenance,
    verify_output_provenance,
    write_output_provenance,
)
from .windows import WindowsToolchain


WINDOWS_ARCHITECTURES = ("arm64", "x64")


@dataclass(frozen=True)
class WindowsBuildResult:
    output_directory: Path
    artifact_path: Path | None


def windows_artifact_name(
    release: str, architecture: str, flavor: str = "release"
) -> str:
    if architecture not in WINDOWS_ARCHITECTURES:
        raise ConfigError(f"Unsupported Windows architecture: {architecture}")
    return (
        f"sprouted-code-{release}-win32-{architecture}"
        f"{artifact_flavor_suffix(flavor)}.zip"
    )


def archive_directory(source: Path, destination: Path) -> None:
    if not source.is_dir():
        raise FileNotFoundError(f"Package directory not found: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    if temporary.exists():
        temporary.unlink()

    try:
        with zipfile.ZipFile(
            temporary,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
            allowZip64=True,
        ) as archive:
            paths = sorted(
                source.rglob("*"),
                key=lambda path: path.relative_to(source).as_posix(),
            )
            for path in paths:
                if path.is_file():
                    archive.write(path, path.relative_to(source).as_posix())
        temporary.replace(destination)
    finally:
        if temporary.exists():
            temporary.unlink()


def build_windows(
    config: BuildConfig,
    manifest: ReleaseManifest,
    toolchain: WindowsToolchain,
    runner: CommandRunner,
    *,
    architecture: str,
    flavor: str = "release",
    skip_install: bool = False,
    skip_tests: bool = False,
    skip_gulp: bool = False,
    no_archive: bool = False,
) -> WindowsBuildResult:
    if architecture not in WINDOWS_ARCHITECTURES:
        raise ConfigError(f"Unsupported Windows architecture: {architecture}")
    validate_build_flavor(flavor)
    environment = environment_for_flavor(toolchain.environment, flavor)

    checkout = toolchain.checkout
    output_directory = checkout.parent / f"VSCode-win32-{architecture}"
    expected_executable = output_directory / "Sprouted Code.exe"
    artifact_directory = config.resolve_path("paths.artifacts")
    artifact_path = artifact_directory / windows_artifact_name(
        manifest.release,
        architecture,
        flavor,
    )
    target = gulp_target("win32", architecture, flavor)
    provenance = expected_provenance(
        manifest,
        platform="win32",
        architecture=architecture,
        flavor=flavor,
        gulp_target=target,
    )

    verify_checkout_provenance(checkout, manifest, runner)

    if not skip_install:
        runner.run(
            [str(toolchain.npm_command), "ci"],
            cwd=checkout,
            env=environment,
        )

    if not skip_tests:
        run_focused_windows_tests(
            config,
            runner,
            toolchain=toolchain,
            environment=environment,
        )

    if not skip_gulp:
        clean_output_directory(
            output_directory,
            expected_parent=checkout.parent,
            dry_run=runner.dry_run,
        )
        runner.run(
            [
                str(toolchain.npm_command),
                "run",
                "gulp",
                "--",
                target,
            ],
            cwd=checkout,
            env=environment,
        )
        verify_checkout_provenance(checkout, manifest, runner)
        if not runner.dry_run:
            write_output_provenance(output_directory, provenance)

    if runner.dry_run or no_archive:
        return WindowsBuildResult(output_directory=output_directory, artifact_path=None)
    verify_checkout_provenance(checkout, manifest, runner)
    verify_output_provenance(output_directory, provenance)
    if not expected_executable.is_file():
        raise ConfigError(
            f"Expected packaged executable not found: {expected_executable}"
        )

    print(f"Archiving {output_directory} to {artifact_path}")
    archive_directory(output_directory, artifact_path)
    write_checksums(artifact_directory)
    print(f"Built artifact: {artifact_path}")
    return WindowsBuildResult(
        output_directory=output_directory,
        artifact_path=artifact_path,
    )
