from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from .commands import CommandRunner
from .config import BuildConfig, ConfigError


_VERSION_PATTERN = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)")


@dataclass(frozen=True)
class WindowsToolchain:
    checkout: Path
    node_directory: Path
    node_version: str
    npm_command: Path
    visual_studio_path: Path | None
    signtool_directory: Path | None
    environment: dict[str, str]


def parse_version(value: str) -> tuple[int, int, int]:
    match = _VERSION_PATTERN.match(value.strip())
    if not match:
        raise ConfigError(f"Unable to parse version: {value!r}")
    return tuple(int(part) for part in match.groups())


def _node_candidates(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    candidates = [
        path
        for path in root.iterdir()
        if path.is_dir()
        and path.name.startswith("node-v24.")
        and (path / "node.exe").is_file()
    ]

    def version_key(path: Path) -> tuple[int, int, int]:
        match = re.search(r"node-v(\d+\.\d+\.\d+)", path.name)
        return parse_version(match.group(1)) if match else (0, 0, 0)

    return sorted(candidates, key=version_key, reverse=True)


def _resolve_node_directory(config: BuildConfig) -> Path:
    explicit = config.get("builders.windows.node_path")
    if explicit:
        path = Path(str(explicit)).expanduser().resolve()
        if not (path / "node.exe").is_file():
            raise ConfigError(f"Configured Node path does not contain node.exe: {path}")
        return path

    root = config.resolve_path("builders.windows.node_root")
    candidates = _node_candidates(root)
    if not candidates:
        raise ConfigError(
            f"No side-by-side Node 24 installation found under {root}; "
            "set builders.windows.node_path in sprouted-build.local.yaml"
        )
    return candidates[0]


def _resolve_visual_studio(config: BuildConfig) -> Path | None:
    explicit = config.get("builders.windows.visual_studio_path")
    if explicit:
        path = Path(str(explicit)).expanduser().resolve()
        if not path.is_dir():
            raise ConfigError(f"Configured Visual Studio path not found: {path}")
        return path

    candidates = (
        Path(r"C:\Program Files\Microsoft Visual Studio\18\Enterprise"),
        Path(r"C:\Program Files\Microsoft Visual Studio\18\Professional"),
        Path(r"C:\Program Files\Microsoft Visual Studio\18\Community"),
        Path(r"C:\Program Files\Microsoft Visual Studio\2022\Enterprise"),
        Path(r"C:\Program Files\Microsoft Visual Studio\2022\Professional"),
        Path(r"C:\Program Files\Microsoft Visual Studio\2022\Community"),
        Path(r"C:\Program Files (x86)\Microsoft Visual Studio\2022\Enterprise"),
        Path(r"C:\Program Files (x86)\Microsoft Visual Studio\2022\Professional"),
        Path(r"C:\Program Files (x86)\Microsoft Visual Studio\2022\Community"),
    )
    return next((path for path in candidates if path.is_dir()), None)


def _resolve_signtool_directory() -> Path | None:
    kits_root = Path(r"C:\Program Files (x86)\Windows Kits\10\bin")
    if not kits_root.is_dir():
        return None
    architecture = (
        "arm64" if os.environ.get("PROCESSOR_ARCHITECTURE") == "ARM64" else "x64"
    )
    for version_directory in sorted(kits_root.iterdir(), reverse=True):
        candidate = version_directory / architecture
        if (candidate / "signtool.exe").is_file():
            return candidate
    return None


def resolve_windows_toolchain(
    config: BuildConfig,
    runner: CommandRunner,
) -> WindowsToolchain:
    checkout = config.resolve_path("builders.windows.vscode_checkout")
    nvmrc = checkout / ".nvmrc"
    if not nvmrc.is_file():
        raise ConfigError(f"VS Code .nvmrc not found: {nvmrc}")
    required_node = nvmrc.read_text(encoding="utf-8").strip()

    node_directory = _resolve_node_directory(config)
    npm_command = node_directory / "npm.cmd"
    if not npm_command.is_file():
        raise ConfigError(f"npm.cmd not found in Node installation: {npm_command}")

    visual_studio_path = _resolve_visual_studio(config)
    signtool_directory = _resolve_signtool_directory()
    environment = dict(os.environ)
    path_entries = [str(node_directory)]
    if signtool_directory:
        path_entries.append(str(signtool_directory))
    path_entries.append(environment.get("PATH", ""))
    environment["PATH"] = os.pathsep.join(path_entries)
    if visual_studio_path:
        environment["vs2022_install"] = str(visual_studio_path)

    node_result = runner.run(
        [str(node_directory / "node.exe"), "--version"],
        env=environment,
        capture_output=True,
    )
    assert node_result is not None
    actual_node = node_result.stdout.strip()
    required_version = parse_version(required_node)
    actual_version = parse_version(actual_node)
    if actual_version[0] != required_version[0] or actual_version < required_version:
        raise ConfigError(
            f"VS Code requires Node {required_node} or newer on major version "
            f"{required_version[0]}; selected Node is {actual_node}"
        )

    npm_result = runner.run(
        [str(npm_command), "--version"],
        env=environment,
        capture_output=True,
    )
    assert npm_result is not None
    if shutil.which("git", path=environment["PATH"]) is None:
        raise ConfigError("Required command not found on PATH: git")

    return WindowsToolchain(
        checkout=checkout,
        node_directory=node_directory,
        node_version=actual_node,
        npm_command=npm_command,
        visual_studio_path=visual_studio_path,
        signtool_directory=signtool_directory,
        environment=environment,
    )


def preflight_windows(config: BuildConfig, runner: CommandRunner) -> WindowsToolchain:
    toolchain = resolve_windows_toolchain(config, runner)
    details = [
        f"Node {toolchain.node_version} from {toolchain.node_directory}",
        f"Visual Studio at {toolchain.visual_studio_path}"
        if toolchain.visual_studio_path
        else "Visual Studio not found",
        f"signtool at {toolchain.signtool_directory}"
        if toolchain.signtool_directory
        else "signtool not found",
    ]
    print("Windows preflight OK:")
    for detail in details:
        print(f"  {detail}")
    return toolchain
