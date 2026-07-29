from pathlib import Path

from sprouted_build.config import BuildConfig
from sprouted_build.manifest import PatchSource, ReleaseManifest
from sprouted_build.proxmox import ProxmoxBuilder
from sprouted_build.proxmox_source import build_proxmox_prepare_script


def test_prepare_script_embeds_exact_manifest_patch_queue(tmp_path: Path) -> None:
    patch = tmp_path / "patches" / "fix.patch"
    patch.parent.mkdir()
    patch.write_text("patch contents", encoding="utf-8")
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
        tmp_path / "manifest.json",
        "2026.07.0",
        "microsoft/vscode",
        "base-sha",
        "main",
        (
            PatchSource("Local", "repo", "patches/fix.patch", None),
        ),
    )
    builder = ProxmoxBuilder(
        "builder@host",
        303,
        "builder",
        "x64",
        "/root/build/vscode",
        "/root/.local",
        "/root/artifacts",
        "24.18.0",
    )

    script = build_proxmox_prepare_script(config, manifest, builder)

    assert "git switch -C sprouted-code/2026.07.0 base-sha" in script
    assert "git fetch https://example.test/microsoft/vscode.git main" in script
    assert "merge --no-edit" not in script
    assert "base64 -d > /root/sprouted/patches/fix.patch" in script
    assert "Refusing to prepare a dirty VS Code checkout" in script
