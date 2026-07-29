import pytest

from sprouted_build.config import ConfigError
from sprouted_build.flavors import (
    artifact_flavor_suffix,
    environment_for_flavor,
    gulp_target,
)


def test_release_flavor_uses_minified_target_and_canonical_name() -> None:
    assert gulp_target("win32", "arm64", "release") == "vscode-win32-arm64-min"
    assert artifact_flavor_suffix("release") == ""


def test_diagnostic_flavor_uses_readable_target_and_labeled_name() -> None:
    assert gulp_target("linux", "x64", "diagnostic") == "vscode-linux-x64"
    assert artifact_flavor_suffix("diagnostic") == "-diagnostic"


def test_unknown_flavor_is_rejected() -> None:
    with pytest.raises(ConfigError, match="Unsupported build flavor"):
        gulp_target("linux", "x64", "mystery")


def test_release_flavor_sets_ci_without_mutating_source_environment() -> None:
    source = {"PATH": "toolchain"}

    result = environment_for_flavor(source, "release")

    assert result == {"PATH": "toolchain", "CI": "1"}
    assert source == {"PATH": "toolchain"}


def test_diagnostic_flavor_preserves_environment() -> None:
    assert environment_for_flavor({"PATH": "toolchain"}, "diagnostic") == {
        "PATH": "toolchain"
    }
