from pathlib import Path

from sprouted_build.config import BuildConfig
from sprouted_build.macos import MacOSBuilder
from sprouted_build.macos_provision import build_macos_provision_script


def test_macos_provision_installs_pinned_node_and_clones(tmp_path: Path) -> None:
    config = BuildConfig(
        data={
            "source": {
                "upstream_url": "https://example.com/upstream.git",
            }
        },
        repo_root=tmp_path,
        sources=(),
    )
    builder = MacOSBuilder(
        "builder@mac",
        "arm64",
        "/Users/builder/repos/vscode",
        "/Users/builder/.local",
        "/Users/builder/artifacts",
        "24.18.0",
    )

    script = build_macos_provision_script(
        config,
        builder,
        install_node=True,
        clone=True,
    )

    assert "node-v${node_version}-darwin-arm64.tar.gz" in script
    assert "git clone https://example.com/upstream.git" in script
    assert "git remote set-url origin https://example.com/upstream.git" in script
