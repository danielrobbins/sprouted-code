from pathlib import Path

from sprouted_build.config import BuildConfig
from sprouted_build.macos import MacOSBuilder
from sprouted_build.macos_source import build_macos_prepare_script
from sprouted_build.manifest import PatchSource, ReleaseManifest


def test_macos_prepare_uses_exact_commits_and_embeds_file_patches(
    tmp_path: Path,
) -> None:
    patch_dir = tmp_path / "patches"
    patch_dir.mkdir()
    patch = patch_dir / "local.patch"
    patch.write_text("patch", encoding="utf-8")
    config = BuildConfig(
        data={
            "source": {
                "upstream_url": "https://example.test/microsoft/vscode.git",
                "build_branch_prefix": "sprouted-code",
            }
        },
        repo_root=tmp_path,
        sources=(),
    )
    manifest = ReleaseManifest(
        path=tmp_path / "manifest.json",
        release="2026.07.0",
        base_repo="microsoft/vscode",
        base_commit="a" * 40,
        base_branch="main",
        patches=(
            PatchSource("Local", "build", "patches/local.patch", None),
        ),
        source_tree="c" * 40,
    )
    builder = MacOSBuilder(
        "builder@mac",
        "arm64",
        "/Users/builder/repos/vscode",
        "/Users/builder/.local",
        "/Users/builder/artifacts",
        "24.18.0",
    )

    script = build_macos_prepare_script(config, manifest, builder)

    assert "git fetch https://example.test/microsoft/vscode.git main" in script
    assert "merge --no-edit" not in script
    assert "git apply --ignore-whitespace --check" in script
    assert "expected_source_tree=" + '"' + "c" * 40 + '"' in script
