from pathlib import Path

import pytest

from sprouted_build.config import BuildConfig, ConfigError
from sprouted_build.manifest import PatchSource, ReleaseManifest
from sprouted_build.patches import resolve_build_patches


def _manifest(tmp_path: Path, *extra_patch_names: str) -> ReleaseManifest:
    patches = [PatchSource("Local", "repo", "patches/local.patch", None)]
    patches.extend(
        PatchSource(name, "repo", f"patches/{name}", None) for name in extra_patch_names
    )
    return ReleaseManifest(
        tmp_path / "manifest.json",
        "2026.07.0",
        "microsoft/vscode",
        "base-sha",
        "main",
        tuple(patches),
    )


def test_gallery_patch_is_enabled_by_configuration(tmp_path: Path) -> None:
    patch_dir = tmp_path / "patches"
    patch_dir.mkdir()
    (patch_dir / "local.patch").write_text("local", encoding="utf-8")
    (patch_dir / "gallery.patch").write_text("gallery", encoding="utf-8")
    (patch_dir / "signature-policy.patch").write_text("policy", encoding="utf-8")
    config = BuildConfig(
        data={
            "product": {
                "extension_gallery": {
                    "enabled": True,
                    "patch": "patches/gallery.patch",
                    "verify_signatures": False,
                    "signature_policy_patch": "patches/signature-policy.patch",
                }
            }
        },
        repo_root=tmp_path,
        sources=(),
    )

    patches = resolve_build_patches(
        config,
        _manifest(tmp_path, "gallery.patch", "signature-policy.patch"),
    )

    assert [path.name for path in patches] == [
        "local.patch",
        "gallery.patch",
        "signature-policy.patch",
    ]


def test_gallery_patch_can_be_disabled(tmp_path: Path) -> None:
    patch_dir = tmp_path / "patches"
    patch_dir.mkdir()
    (patch_dir / "local.patch").write_text("local", encoding="utf-8")
    config = BuildConfig(
        data={"product": {"extension_gallery": {"enabled": False}}},
        repo_root=tmp_path,
        sources=(),
    )

    patches = resolve_build_patches(config, _manifest(tmp_path))

    assert [path.name for path in patches] == ["local.patch"]


def test_enabled_gallery_requires_a_patch(tmp_path: Path) -> None:
    patch_dir = tmp_path / "patches"
    patch_dir.mkdir()
    (patch_dir / "local.patch").write_text("local", encoding="utf-8")
    config = BuildConfig(
        data={"product": {"extension_gallery": {"enabled": True}}},
        repo_root=tmp_path,
        sources=(),
    )

    with pytest.raises(ConfigError, match="patch is required"):
        resolve_build_patches(config, _manifest(tmp_path))


def test_enabled_gallery_patch_must_be_declared_in_manifest(tmp_path: Path) -> None:
    patch_dir = tmp_path / "patches"
    patch_dir.mkdir()
    (patch_dir / "local.patch").write_text("local", encoding="utf-8")
    (patch_dir / "gallery.patch").write_text("gallery", encoding="utf-8")
    config = BuildConfig(
        data={
            "product": {
                "extension_gallery": {
                    "enabled": True,
                    "patch": "patches/gallery.patch",
                }
            }
        },
        repo_root=tmp_path,
        sources=(),
    )

    with pytest.raises(ConfigError, match="must be declared"):
        resolve_build_patches(config, _manifest(tmp_path))


def test_disabled_signature_verification_requires_policy_patch(tmp_path: Path) -> None:
    patch_dir = tmp_path / "patches"
    patch_dir.mkdir()
    (patch_dir / "local.patch").write_text("local", encoding="utf-8")
    (patch_dir / "gallery.patch").write_text("gallery", encoding="utf-8")
    config = BuildConfig(
        data={
            "product": {
                "extension_gallery": {
                    "enabled": True,
                    "patch": "patches/gallery.patch",
                    "verify_signatures": False,
                }
            }
        },
        repo_root=tmp_path,
        sources=(),
    )

    with pytest.raises(ConfigError, match="signature_policy_patch is required"):
        resolve_build_patches(config, _manifest(tmp_path, "gallery.patch"))
