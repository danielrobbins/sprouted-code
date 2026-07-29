import json
import re
from pathlib import Path

from sprouted_build.config import load_build_config


REPO_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_CONFIG = REPO_ROOT / "sprouted-build.yaml"
LOCAL_CONFIG_EXAMPLE = REPO_ROOT / "sprouted-build.local.yaml.example"
RELEASE_MANIFEST = REPO_ROOT / "manifests" / "sprouted-code-2026.07.0.json"


def test_public_configuration_does_not_contain_private_builder_identity() -> None:
    contents = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (PUBLIC_CONFIG, LOCAL_CONFIG_EXAMPLE)
    )
    forbidden_patterns = {
        "Windows user profile": r"(?i)C:\\Users\\",
        "RFC1918 address": r"(?:10\.|192\.168\.|172\.(?:1[6-9]|2\d|3[01])\.)",
        "SSH user and numeric host": r"(?i)[a-z0-9._-]+@(?:\d{1,3}\.){3}\d{1,3}",
        "known personal account": r"(?i)drobbins",
    }

    failures = [
        label
        for label, pattern in forbidden_patterns.items()
        if re.search(pattern, contents)
    ]
    assert not failures, f"Public build defaults contain: {', '.join(failures)}"


def test_local_configuration_example_covers_supported_builder_lanes() -> None:
    config = load_build_config(REPO_ROOT, local_config=LOCAL_CONFIG_EXAMPLE)

    assert config.get("builders.windows.vscode_checkout")
    for backend in ("wsl", "proxmox"):
        for architecture in ("arm64", "x64"):
            assert config.get(f"builders.{backend}.{architecture}")
    assert config.get("builders.macos.arm64")


def test_public_defaults_enable_gallery_without_signature_verification() -> None:
    config = load_build_config(REPO_ROOT, include_local=False)

    assert config.get("source.upstream_remote") is None
    assert config.get("source.upstream_url") == "https://github.com/microsoft/vscode.git"
    assert config.get("source.contribution_remote") is None
    assert config.get("source.contribution_url") is None
    assert config.get("product.extension_gallery.enabled") is True
    assert config.get("product.extension_gallery.verify_signatures") is False
    assert config.get("builders.macos.default_architecture") == "arm64"
    assert config.get("builders.macos.arm64.ssh_target") is None


def test_release_manifest_declares_every_patch_file() -> None:
    manifest = json.loads(RELEASE_MANIFEST.read_text(encoding="utf-8"))
    declared = {
        patch["source_ref"]
        for patch in manifest["patches"]
        if patch["source_ref"].endswith(".patch")
    }
    present = {
        path.relative_to(REPO_ROOT).as_posix()
        for path in (REPO_ROOT / "patches").glob("*.patch")
    }

    assert declared == present
    gallery = manifest["product"]["extension_gallery"]
    assert gallery["patch"] in declared
    assert gallery["signature_policy_patch"] in declared
