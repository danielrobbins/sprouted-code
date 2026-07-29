from pathlib import Path

import pytest

from sprouted_build.config import ConfigError
from sprouted_build.windows import _node_candidates, parse_version


def test_parse_version_accepts_node_prefix() -> None:
    assert parse_version("v24.18.0") == (24, 18, 0)


def test_parse_version_rejects_invalid_value() -> None:
    with pytest.raises(ConfigError, match="Unable to parse"):
        parse_version("current")


def test_node_candidates_are_sorted_semantically(tmp_path: Path) -> None:
    for name in ("node-v24.9.0-win-arm64", "node-v24.18.0-win-arm64"):
        candidate = tmp_path / name
        candidate.mkdir()
        (candidate / "node.exe").touch()

    candidates = _node_candidates(tmp_path)

    assert candidates[0].name == "node-v24.18.0-win-arm64"
