from pathlib import Path

import pytest

from sprouted_build.config import ConfigError, load_build_config


def write_config(path: Path, contents: str) -> None:
    path.write_text(contents, encoding="utf-8")


def test_local_configuration_deeply_overrides_defaults(tmp_path: Path) -> None:
    write_config(
        tmp_path / "sprouted-build.yaml",
        """
schema_version: 1
paths:
  artifacts: artifacts
builders:
  windows:
    vscode_checkout: null
    node_root: 'C:\\Tools\\Node'
""".lstrip(),
    )
    write_config(
        tmp_path / "sprouted-build.local.yaml",
        """
builders:
  windows:
    vscode_checkout: 'D:\\src\\vscode'
""".lstrip(),
    )

    config = load_build_config(tmp_path)

    assert config.get("builders.windows.vscode_checkout") == "D:\\src\\vscode"
    assert config.get("builders.windows.node_root") == "C:\\Tools\\Node"
    assert len(config.sources) == 2


def test_missing_required_value_has_clear_error(tmp_path: Path) -> None:
    write_config(
        tmp_path / "sprouted-build.yaml",
        "schema_version: 1\nbuilders:\n  proxmox:\n    ssh_target: null\n",
    )

    config = load_build_config(tmp_path, include_local=False)

    with pytest.raises(ConfigError, match="builders.proxmox.ssh_target"):
        config.require("builders.proxmox.ssh_target")


def test_relative_path_is_resolved_from_repository_root(tmp_path: Path) -> None:
    write_config(
        tmp_path / "sprouted-build.yaml",
        "schema_version: 1\npaths:\n  artifacts: artifacts\nbuilders: {}\n",
    )

    config = load_build_config(tmp_path, include_local=False)

    assert config.resolve_path("paths.artifacts") == (tmp_path / "artifacts").resolve()


def test_rejects_unsupported_schema(tmp_path: Path) -> None:
    write_config(tmp_path / "sprouted-build.yaml", "schema_version: 2\nbuilders: {}\n")

    with pytest.raises(ConfigError, match="schema_version"):
        load_build_config(tmp_path, include_local=False)
