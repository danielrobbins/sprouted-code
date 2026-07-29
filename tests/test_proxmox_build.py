from pathlib import Path

from sprouted_build.proxmox import ProxmoxBuilder
from sprouted_build.proxmox_build import (
    _sha256,
    build_proxmox_build_script,
    build_proxmox_preflight_script,
)
from sprouted_build.provenance import BuildProvenance, PROVENANCE_FILE


def _builder() -> ProxmoxBuilder:
    return ProxmoxBuilder(
        "builder@host",
        303,
        "builder",
        "x64",
        "/root/build/vscode",
        "/root/.local",
        "/root/artifacts",
        "24.18.0",
    )


def _provenance(architecture: str, flavor: str = "release") -> BuildProvenance:
    suffix = "-min" if flavor == "release" else ""
    return BuildProvenance(
        schema_version=1,
        release="2026.07.0",
        source_tree="a" * 40,
        platform="linux",
        architecture=architecture,
        flavor=flavor,
        gulp_target=f"vscode-linux-{architecture}{suffix}",
    )


def test_preflight_requires_configured_architecture_and_node_24() -> None:
    script = build_proxmox_preflight_script(_builder())

    assert "expected_arch=x86_64" in script
    assert "v24.*" in script


def test_build_script_runs_tests_gulp_and_archive() -> None:
    builder = ProxmoxBuilder(
        "builder@host",
        303,
        "builder",
        "x64",
        "/root/build/vscode",
        "/root/.local",
        "/root/artifacts",
        "24.18.0",
        cc="gcc-11",
        cxx="g++-11",
    )
    script = build_proxmox_build_script(
        builder,
        release_name="sprouted-code-2026.07.0-linux-x64",
        provenance=_provenance("x64"),
        flavor="release",
        skip_install=False,
        skip_tests=False,
        skip_gulp=False,
        no_archive=False,
    )

    assert "npm ci" in script
    assert "export CI=1" in script
    assert "export CC=gcc-11" in script
    assert "export VSCODE_REMOTE_CXX=g++-11" in script
    assert "byokProvider.spec.ts" in script
    assert "byokPolicy.spec.ts" in script
    assert "npm run gulp -- vscode-linux-x64-min" in script
    assert "sha256sum" in script
    assert "git status --porcelain" in script
    assert 'rm -rf "$output_dir"' in script
    assert PROVENANCE_FILE in script


def test_build_script_uses_arm64_gulp_target_and_output() -> None:
    builder = ProxmoxBuilder(
        "builder@host",
        304,
        "builder",
        "arm64",
        "/root/build/vscode",
        "/root/.local",
        "/root/artifacts",
        "24.18.0",
    )
    script = build_proxmox_build_script(
        builder,
        release_name="sprouted-code-2026.07.0-linux-arm64",
        provenance=_provenance("arm64", "diagnostic"),
        flavor="diagnostic",
        skip_install=True,
        skip_tests=True,
        skip_gulp=False,
        no_archive=False,
    )

    assert "npm run gulp -- vscode-linux-arm64" in script
    assert "vscode-linux-arm64-min" not in script
    assert "export CI=1" not in script
    assert "VSCode-linux-arm64" in script


def test_sha256_reads_artifact_in_blocks(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.tar.gz"
    artifact.write_bytes(b"sprouted")

    assert _sha256(artifact) == (
        "c8021e607211bebdb0e9450b502e3fd73361b205a8bf3171a26bbabe40ea0a73"
    )
