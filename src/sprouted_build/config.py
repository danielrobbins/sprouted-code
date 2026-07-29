from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml


DEFAULT_CONFIG_NAME = "sprouted-build.yaml"
LOCAL_CONFIG_NAME = "sprouted-build.local.yaml"


class ConfigError(ValueError):
    """Raised when build configuration is missing or malformed."""


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ConfigError(
            f"Unable to read configuration file {path}: {error}"
        ) from error
    except yaml.YAMLError as error:
        raise ConfigError(f"Invalid YAML in {path}: {error}") from error

    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise ConfigError(f"Configuration root must be a mapping: {path}")
    return loaded


def _deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    merged = deepcopy(dict(base))
    for key, value in override.items():
        current = merged.get(key)
        if isinstance(current, Mapping) and isinstance(value, Mapping):
            merged[key] = _deep_merge(current, value)
        else:
            merged[key] = deepcopy(value)
    return merged


@dataclass(frozen=True)
class BuildConfig:
    data: dict[str, Any]
    repo_root: Path
    sources: tuple[Path, ...]

    def get(self, dotted_key: str, default: Any = None) -> Any:
        value: Any = self.data
        for part in dotted_key.split("."):
            if not isinstance(value, Mapping) or part not in value:
                return default
            value = value[part]
        return value

    def require(self, dotted_key: str) -> Any:
        value = self.get(dotted_key)
        if value is None or value == "":
            raise ConfigError(f"Required configuration value is not set: {dotted_key}")
        return value

    def string_tuple(self, dotted_key: str) -> tuple[str, ...]:
        value = self.get(dotted_key)
        if value is None:
            return ()
        if not isinstance(value, list) or not all(
            isinstance(item, str) and item for item in value
        ):
            raise ConfigError(
                f"Configuration value must be a list of non-empty strings: {dotted_key}"
            )
        return tuple(value)

    def resolve_path(self, dotted_key: str) -> Path:
        raw_value = self.require(dotted_key)
        if not isinstance(raw_value, str):
            raise ConfigError(
                f"Configuration value must be a path string: {dotted_key}"
            )
        path = Path(raw_value).expanduser()
        if not path.is_absolute():
            path = self.repo_root / path
        return path.resolve()


def load_build_config(
    repo_root: Path,
    *,
    local_config: Path | None = None,
    include_local: bool = True,
) -> BuildConfig:
    repo_root = repo_root.resolve()
    defaults_path = repo_root / DEFAULT_CONFIG_NAME
    if not defaults_path.is_file():
        raise ConfigError(f"Default build configuration not found: {defaults_path}")

    data = _load_yaml(defaults_path)
    sources = [defaults_path]

    if include_local:
        selected_local = local_config or (repo_root / LOCAL_CONFIG_NAME)
        selected_local = selected_local.resolve()
        if local_config is not None and not selected_local.is_file():
            raise ConfigError(f"Local build configuration not found: {selected_local}")
        if selected_local.is_file():
            data = _deep_merge(data, _load_yaml(selected_local))
            sources.append(selected_local)

    schema_version = data.get("schema_version")
    if schema_version != 1:
        raise ConfigError(f"Unsupported or missing schema_version: {schema_version!r}")
    if not isinstance(data.get("builders"), dict):
        raise ConfigError("Configuration must contain a builders mapping")

    return BuildConfig(data=data, repo_root=repo_root, sources=tuple(sources))
