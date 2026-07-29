from pathlib import Path

from sprouted_build.config import BuildConfig
from sprouted_build.manifest import PatchSource, ReleaseManifest
from sprouted_build.wsl import WslBuilder
from sprouted_build.wsl_source import build_wsl_prepare_script, windows_path_to_wsl


def test_windows_path_to_wsl_maps_drive_letter_path() -> None:
    path = Path(r"C:\Users\builder\patches\fix.patch")

    assert windows_path_to_wsl(path) == "/mnt/c/Users/builder/patches/fix.patch"


def test_prepare_script_uses_exact_manifest_commits_and_local_patch(
    tmp_path: Path,
) -> None:
    patch = tmp_path / "patches" / "local.patch"
    patch.parent.mkdir()
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
        base_commit="base-sha",
        base_branch="main",
        patches=(
            PatchSource("Local", "repo", "patches/local.patch", None),
        ),
    )
    builder = WslBuilder("Ubuntu", "arm64", "~/repos/vscode", "24.18.0")

    script = build_wsl_prepare_script(config, manifest, builder)

    assert "git switch -C sprouted-code/2026.07.0 base-sha" in script
    assert "git fetch https://example.test/microsoft/vscode.git main" in script
    assert "merge --no-edit" not in script
    assert windows_path_to_wsl(patch) in script
    assert "Refusing to prepare a dirty VS Code checkout" in script
