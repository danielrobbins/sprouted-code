from __future__ import annotations

import json
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .artifacts import sha256_file
from .config import ConfigError
from .flavors import gulp_target
from .manifest import ArtifactRecord, ReleaseManifest
from .provenance import BuildProvenance, PROVENANCE_FILE, expected_provenance


@dataclass(frozen=True)
class ReleaseVerification:
    artifacts: tuple[Path, ...]
    warnings: tuple[str, ...]


def _validate_member_name(name: str, artifact: Path) -> None:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        raise ConfigError(f"Unsafe archive member in {artifact}: {name}")


def _read_zip(
    artifact: Path,
    receipt_name: str,
) -> tuple[set[str], bytes | None]:
    try:
        with zipfile.ZipFile(artifact) as archive:
            bad_member = archive.testzip()
            if bad_member:
                raise ConfigError(
                    f"ZIP integrity check failed in {artifact}: {bad_member}"
                )
            names = set(archive.namelist())
            for name in names:
                _validate_member_name(name, artifact)
            receipt_names = [
                name for name in names if PurePosixPath(name).name == PROVENANCE_FILE
            ]
            if receipt_names and receipt_names != [receipt_name]:
                raise ConfigError(
                    f"Artifact provenance receipt is in an unexpected location: "
                    f"{artifact}"
                )
            receipt = archive.read(receipt_name) if receipt_names else None
            return names, receipt
    except (OSError, zipfile.BadZipFile) as error:
        raise ConfigError(
            f"Unable to verify ZIP artifact {artifact}: {error}"
        ) from error


def _read_tar(
    artifact: Path,
    receipt_name: str,
) -> tuple[set[str], bytes | None]:
    names: set[str] = set()
    receipt: bytes | None = None
    try:
        with tarfile.open(artifact, mode="r|gz") as archive:
            for member in archive:
                _validate_member_name(member.name, artifact)
                names.add(member.name)
                if not member.isfile():
                    continue
                source = archive.extractfile(member)
                if source is None:
                    raise ConfigError(
                        f"Unable to read archive member {member.name} in {artifact}"
                    )
                if PurePosixPath(member.name).name == PROVENANCE_FILE:
                    if receipt is not None or member.name != receipt_name:
                        raise ConfigError(
                            f"Artifact provenance receipt is in an unexpected "
                            f"location: {artifact}"
                        )
                    receipt = source.read()
                else:
                    while source.read(1024 * 1024):
                        pass
        return names, receipt
    except (OSError, tarfile.TarError) as error:
        raise ConfigError(
            f"Unable to verify tar artifact {artifact}: {error}"
        ) from error


def _split_platform(record: ArtifactRecord) -> tuple[str, str]:
    try:
        platform, architecture = record.platform.rsplit("-", 1)
    except ValueError as error:
        raise ConfigError(
            f"Invalid build platform in manifest: {record.platform}"
        ) from error
    if platform not in ("win32", "linux", "darwin") or architecture not in (
        "arm64",
        "x64",
    ):
        raise ConfigError(f"Unsupported build platform in manifest: {record.platform}")
    if platform == "darwin" and architecture != "arm64":
        raise ConfigError(f"Unsupported build platform in manifest: {record.platform}")
    return platform, architecture


def _require_archive_contents(
    artifact: Path,
    names: set[str],
    platform: str,
    architecture: str,
) -> None:
    required_suffixes = ("LICENSE.txt", "ThirdPartyNotices.txt")
    for suffix in required_suffixes:
        if not any(PurePosixPath(name).name == suffix for name in names):
            raise ConfigError(f"Artifact is missing {suffix}: {artifact}")

    if platform == "win32":
        expected = "Sprouted Code.exe"
        if expected not in names:
            raise ConfigError(f"Artifact is missing {expected}: {artifact}")
    elif platform == "linux":
        expected = f"VSCode-linux-{architecture}/sprouted-code"
        if expected not in names:
            raise ConfigError(f"Artifact is missing {expected}: {artifact}")
    else:
        expected = "Sprouted Code.app/Contents/MacOS/Sprouted Code"
        if expected not in names:
            raise ConfigError(
                f"Artifact is missing the Sprouted Code application executable: "
                f"{artifact}"
            )


def _verify_receipt(
    artifact: Path,
    receipt: bytes,
    expected: BuildProvenance,
) -> None:
    try:
        data = json.loads(receipt.decode("utf-8"))
        actual = BuildProvenance(**data)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as error:
        raise ConfigError(
            f"Artifact has an invalid provenance receipt: {artifact}"
        ) from error
    if actual != expected:
        raise ConfigError(
            f"Artifact provenance does not match the release manifest: {artifact}"
        )


def verify_release_artifacts(
    artifact_directory: Path,
    manifest: ReleaseManifest,
) -> ReleaseVerification:
    if not manifest.source_tree:
        raise ConfigError(
            "Release manifest build.source_tree is required for release verification"
        )
    if not manifest.builds:
        raise ConfigError("Release manifest contains no build records")

    artifact_directory = artifact_directory.resolve()
    seen_platforms: set[str] = set()
    seen_artifacts: set[str] = set()
    verified: list[Path] = []
    warnings: list[str] = []

    for record in manifest.builds:
        if record.platform in seen_platforms:
            raise ConfigError(
                f"Duplicate build platform in manifest: {record.platform}"
            )
        if record.artifact in seen_artifacts:
            raise ConfigError(
                f"Duplicate build artifact in manifest: {record.artifact}"
            )
        seen_platforms.add(record.platform)
        seen_artifacts.add(record.artifact)

        if Path(record.artifact).name != record.artifact:
            raise ConfigError(
                f"Build artifact must be a plain file name: {record.artifact}"
            )
        artifact = artifact_directory / record.artifact
        if not artifact.is_file():
            raise ConfigError(f"Release artifact not found: {artifact}")
        actual_hash = sha256_file(artifact)
        if actual_hash != record.sha256:
            raise ConfigError(
                f"Artifact checksum mismatch for {artifact}: "
                f"expected {record.sha256}, calculated {actual_hash}"
            )

        platform, architecture = _split_platform(record)
        if platform in ("win32", "darwin"):
            if artifact.suffix != ".zip":
                raise ConfigError(
                    f"{platform} release artifact must be a ZIP: {artifact}"
                )
            receipt_name = PROVENANCE_FILE
            names, receipt = _read_zip(artifact, receipt_name)
        else:
            if not artifact.name.endswith(".tar.gz"):
                raise ConfigError(
                    f"Linux release artifact must be a tar.gz: {artifact}"
                )
            receipt_name = f"VSCode-linux-{architecture}/{PROVENANCE_FILE}"
            names, receipt = _read_tar(artifact, receipt_name)
        _require_archive_contents(artifact, names, platform, architecture)

        expected = expected_provenance(
            manifest,
            platform=platform,
            architecture=architecture,
            flavor=manifest.build_flavor,
            gulp_target=gulp_target(
                platform,
                architecture,
                manifest.build_flavor,
            ),
        )
        if receipt is None:
            if manifest.require_provenance_receipt:
                raise ConfigError(
                    f"Artifact has no embedded provenance receipt: {artifact}"
                )
            warnings.append(
                f"{record.artifact}: no embedded provenance receipt; "
                "rebuild with the current tooling before enabling "
                "build.provenance_receipt"
            )
        else:
            _verify_receipt(artifact, receipt, expected)
        verified.append(artifact)

    return ReleaseVerification(
        artifacts=tuple(verified),
        warnings=tuple(warnings),
    )
