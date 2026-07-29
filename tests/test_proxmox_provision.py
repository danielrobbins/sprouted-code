from pathlib import Path

from sprouted_build.config import BuildConfig
from sprouted_build.proxmox import ProxmoxBuilder
from sprouted_build.proxmox_provision import build_proxmox_provision_script


def test_provision_script_installs_and_clones(tmp_path: Path) -> None:
    config = BuildConfig(
        data={
            "source": {
                "upstream_url": "https://example.test/upstream.git",
            }
        },
        repo_root=tmp_path,
        sources=(),
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
        cc="gcc-11",
        cxx="g++-11",
        apt_repositories=("ppa:ubuntu-toolchain-r/test",),
    )

    script = build_proxmox_provision_script(
        config,
        builder,
        install_packages=True,
        install_node=True,
        clone=True,
    )

    assert "apt-get install" in script
    assert "add-apt-repository -y ppa:ubuntu-toolchain-r/test" in script
    assert "gcc-11 g++-11" in script
    assert "node_arch=x64" in script
    assert "node-v${node_version}-linux-${node_arch}.tar.xz" in script
    assert "git clone https://example.test/upstream.git" in script
    assert "git remote set-url origin https://example.test/upstream.git" in script
    assert "contribution" not in script
