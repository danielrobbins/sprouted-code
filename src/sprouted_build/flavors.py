from __future__ import annotations

from collections.abc import Mapping

from .config import ConfigError


BUILD_FLAVORS = ("release", "diagnostic")


def validate_build_flavor(flavor: str) -> str:
    if flavor not in BUILD_FLAVORS:
        raise ConfigError(
            f"Unsupported build flavor: {flavor}. "
            f"Expected one of: {', '.join(BUILD_FLAVORS)}"
        )
    return flavor


def gulp_target(platform: str, architecture: str, flavor: str) -> str:
    validate_build_flavor(flavor)
    suffix = "-min" if flavor == "release" else ""
    return f"vscode-{platform}-{architecture}{suffix}"


def artifact_flavor_suffix(flavor: str) -> str:
    validate_build_flavor(flavor)
    return "" if flavor == "release" else "-diagnostic"


def environment_for_flavor(
    environment: Mapping[str, str], flavor: str
) -> dict[str, str]:
    """Return the command environment for a release or diagnostic build."""
    validate_build_flavor(flavor)
    result = dict(environment)
    if flavor == "release":
        result["CI"] = "1"
    return result
