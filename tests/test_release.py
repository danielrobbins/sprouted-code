import zipfile
from pathlib import Path

import pytest

from sprouted_build.artifacts import sha256_file
from sprouted_build.config import ConfigError
from sprouted_build.manifest import ArtifactRecord, ReleaseManifest
from sprouted_build.provenance import PROVENANCE_FILE, expected_provenance
from sprouted_build.release import verify_release_artifacts


def _manifest(
    tmp_path: Path,
    artifact: Path,
    *,
    require_receipt: bool,
) -> ReleaseManifest:
    return ReleaseManifest(
        path=tmp_path / "manifest.json",
        release="2026.07.0",
        base_repo="microsoft/vscode",
        base_commit="base",
        base_branch="main",
        patches=(),
        source_tree="a" * 40,
        require_provenance_receipt=require_receipt,
        builds=(
            ArtifactRecord(
                platform="win32-arm64",
                builder="local",
                product_commit="commit",
                artifact=artifact.name,
                sha256=sha256_file(artifact),
                tests=("tests: pass",),
            ),
        ),
    )


def _write_artifact(
    path: Path,
    manifest: ReleaseManifest | None = None,
) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("Sprouted Code.exe", b"exe")
        archive.writestr("LICENSE.txt", b"MIT")
        archive.writestr("ThirdPartyNotices.txt", b"notices")
        if manifest is not None:
            provenance = expected_provenance(
                manifest,
                platform="win32",
                architecture="arm64",
                flavor="release",
                gulp_target="vscode-win32-arm64-min",
            )
            archive.writestr(PROVENANCE_FILE, provenance.to_json())


def test_release_verifies_hash_contents_and_receipt(tmp_path: Path) -> None:
    artifact = tmp_path / "sprouted.zip"
    seed_manifest = ReleaseManifest(
        path=tmp_path / "manifest.json",
        release="2026.07.0",
        base_repo="microsoft/vscode",
        base_commit="base",
        base_branch="main",
        patches=(),
        source_tree="a" * 40,
    )
    _write_artifact(artifact, seed_manifest)
    manifest = _manifest(tmp_path, artifact, require_receipt=True)

    result = verify_release_artifacts(tmp_path, manifest)

    assert result.artifacts == (artifact,)
    assert result.warnings == ()


def test_release_warns_about_legacy_artifact_without_receipt(tmp_path: Path) -> None:
    artifact = tmp_path / "sprouted.zip"
    _write_artifact(artifact)
    manifest = _manifest(tmp_path, artifact, require_receipt=False)

    result = verify_release_artifacts(tmp_path, manifest)

    assert "no embedded provenance receipt" in result.warnings[0]


def test_release_requires_receipt_when_manifest_enables_it(tmp_path: Path) -> None:
    artifact = tmp_path / "sprouted.zip"
    _write_artifact(artifact)
    manifest = _manifest(tmp_path, artifact, require_receipt=True)

    with pytest.raises(ConfigError, match="no embedded provenance receipt"):
        verify_release_artifacts(tmp_path, manifest)


def test_release_rejects_checksum_mismatch(tmp_path: Path) -> None:
    artifact = tmp_path / "sprouted.zip"
    _write_artifact(artifact)
    manifest = _manifest(tmp_path, artifact, require_receipt=False)
    artifact.write_bytes(artifact.read_bytes() + b"changed")

    with pytest.raises(ConfigError, match="checksum mismatch"):
        verify_release_artifacts(tmp_path, manifest)


def _macos_manifest(tmp_path: Path, artifact: Path) -> ReleaseManifest:
    return ReleaseManifest(
        path=tmp_path / "manifest.json",
        release="2026.07.0",
        base_repo="microsoft/vscode",
        base_commit="base",
        base_branch="main",
        patches=(),
        source_tree="a" * 40,
        require_provenance_receipt=True,
        builds=(
            ArtifactRecord(
                platform="darwin-arm64",
                builder="mac",
                product_commit="commit",
                artifact=artifact.name,
                sha256=sha256_file(artifact),
                tests=("tests: pass",),
            ),
        ),
    )


def test_release_verifies_macos_bundle_and_receipt(tmp_path: Path) -> None:
    artifact = tmp_path / "sprouted-macos.zip"
    seed_manifest = ReleaseManifest(
        path=tmp_path / "manifest.json",
        release="2026.07.0",
        base_repo="microsoft/vscode",
        base_commit="base",
        base_branch="main",
        patches=(),
        source_tree="a" * 40,
    )
    provenance = expected_provenance(
        seed_manifest,
        platform="darwin",
        architecture="arm64",
        flavor="release",
        gulp_target="vscode-darwin-arm64-min",
    )
    with zipfile.ZipFile(artifact, "w") as archive:
        archive.writestr(
            "Sprouted Code.app/Contents/MacOS/Sprouted Code",
            b"mach-o",
        )
        archive.writestr("Sprouted Code.app/Contents/Resources/LICENSE.txt", b"MIT")
        archive.writestr(
            "Sprouted Code.app/Contents/Resources/ThirdPartyNotices.txt",
            b"notices",
        )
        archive.writestr(PROVENANCE_FILE, provenance.to_json())

    result = verify_release_artifacts(
        tmp_path,
        _macos_manifest(tmp_path, artifact),
    )

    assert result.artifacts == (artifact,)
    assert result.warnings == ()


def test_release_rejects_macos_bundle_without_main_executable(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "sprouted-macos.zip"
    with zipfile.ZipFile(artifact, "w") as archive:
        archive.writestr(
            "Sprouted Code.app/Contents/MacOS/Sprouted Code Helper",
            b"mach-o",
        )
        archive.writestr("Sprouted Code.app/Contents/Resources/LICENSE.txt", b"MIT")
        archive.writestr(
            "Sprouted Code.app/Contents/Resources/ThirdPartyNotices.txt",
            b"notices",
        )

    with pytest.raises(ConfigError, match="application executable"):
        verify_release_artifacts(
            tmp_path,
            _macos_manifest(tmp_path, artifact),
        )
