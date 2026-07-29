from pathlib import Path

from sprouted_build.config import BuildConfig
from sprouted_build.wsl import WslBuilder
from sprouted_build.wsl_provision import build_wsl_provision_script


def test_wsl_provision_script_uses_configured_repositories(tmp_path: Path) -> None:
    config = BuildConfig(
        data={
            "source": {
                "upstream_url": "https://example.test/upstream.git",
            }
        },
        repo_root=tmp_path,
        sources=(),
    )
    builder = WslBuilder(
        "Ubuntu",
        "arm64",
        "~/build/vscode",
        "24.18.0",
        cc="gcc-11",
        cxx="g++-11",
        apt_repositories=("ppa:ubuntu-toolchain-r/test",),
        user="root",
    )

    script = build_wsl_provision_script(
        config,
        builder,
        install_packages=True,
        install_node=True,
        clone=True,
    )

    assert "apt-get install" in script
    assert "add-apt-repository -y ppa:ubuntu-toolchain-r/test" in script
    assert "sudo add-apt-repository" not in script
    assert "gcc-11 g++-11" in script
    assert "node-v${node_version}-linux-arm64.tar.xz" in script
    assert "git clone https://example.test/upstream.git" in script
    assert "git remote set-url origin https://example.test/upstream.git" in script
    assert "contribution" not in script


def test_wsl_provision_can_be_a_noop(tmp_path: Path) -> None:
    config = BuildConfig(
        data={
            "source": {
                "upstream_url": "upstream",
            }
        },
        repo_root=tmp_path,
        sources=(),
    )
    builder = WslBuilder("Ubuntu", "arm64", "~/build/vscode", "24.18.0")

    script = build_wsl_provision_script(
        config,
        builder,
        install_packages=False,
        install_node=False,
        clone=False,
    )

    assert "\n:\n" in script
