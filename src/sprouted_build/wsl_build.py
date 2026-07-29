from __future__ import annotations

import shlex
from dataclasses import dataclass
from pathlib import Path

from .artifacts import write_checksums
from .commands import CommandRunner
from .config import BuildConfig, ConfigError
from .flavors import artifact_flavor_suffix, gulp_target, validate_build_flavor
from .manifest import ReleaseManifest
from .provenance import (
    BuildProvenance,
    expected_provenance,
    shell_checkout_gate,
    shell_verify_output_provenance,
    shell_write_output_provenance,
)
from .wsl import WslBuilder, preflight_wsl, run_wsl_script
from .wsl_source import windows_path_to_wsl


@dataclass(frozen=True)
class WslBuildResult:
    artifact_path: Path | None


def linux_artifact_name(
    release: str, architecture: str, flavor: str = "release"
) -> str:
    if architecture not in ("arm64", "x64"):
        raise ConfigError(f"Unsupported Linux architecture: {architecture}")
    return (
        f"sprouted-code-{release}-linux-{architecture}"
        f"{artifact_flavor_suffix(flavor)}.tar.gz"
    )


def build_wsl_build_script(
    builder: WslBuilder,
    *,
    artifact_directory: str,
    release_name: str,
    provenance: BuildProvenance,
    flavor: str,
    skip_install: bool,
    skip_tests: bool,
    skip_gulp: bool,
    no_archive: bool,
) -> str:
    checkout = shlex.quote(builder.checkout)
    node_arch = shlex.quote(builder.node_platform_architecture)
    commands: list[str] = []
    validate_build_flavor(flavor)
    if not skip_install:
        commands.append("npm ci")
    if not skip_tests:
        commands.extend(
            (
                "cd extensions/copilot",
                "./node_modules/.bin/vitest --run --pool=forks "
                "src/extension/byok/common/test/byokProvider.spec.ts",
                "./node_modules/.bin/vitest --run --pool=forks "
                "src/extension/byok/vscode-node/test/byokPolicy.spec.ts",
                "cd ../..",
            )
        )
    if not skip_gulp:
        commands.append('rm -rf "$output_dir"')
        commands.append(
            f"npm run gulp -- {gulp_target('linux', builder.architecture, flavor)}"
        )
        commands.append(shell_checkout_gate(provenance.source_tree))
        commands.append(shell_write_output_provenance(provenance))
    if not no_archive:
        commands.extend(
            (
                shell_checkout_gate(provenance.source_tree),
                shell_verify_output_provenance(provenance),
                'if [ ! -e "$output_dir/sprouted-code" ]; then\n'
                '  echo "Expected packaged executable not found: '
                '$output_dir/sprouted-code" >&2\n  exit 2\nfi',
                f"artifact_dir={shlex.quote(artifact_directory)}",
                f"release_name={shlex.quote(release_name)}",
                'mkdir -p "$artifact_dir"',
                'artifact_path="$artifact_dir/${release_name}.tar.gz"',
                'rm -f "$artifact_path"',
                'tar -czf "$artifact_path" -C "$(dirname "$output_dir")" '
                '"$(basename "$output_dir")"',
                'echo "Built artifact: $artifact_path"',
            )
        )
    body = "\n".join(commands) or ":"
    ci_environment = "export CI=1\n" if flavor == "release" else ""
    return f"""
set -euo pipefail
checkout={checkout}
checkout="${{checkout/#\\~/$HOME}}"
output_dir="$(dirname "$checkout")/VSCode-linux-{builder.architecture}"
node_dir="$HOME/.local/node-v{shlex.quote(builder.node_version)}-linux-{node_arch}"
clean_path="$(printf '%s' "$PATH" | tr ':' '\n' | grep -v '^/mnt/c/' | paste -sd: -)"
export PATH="$node_dir/bin:$clean_path"
export CC={shlex.quote(builder.cc)}
export CXX={shlex.quote(builder.cxx)}
export VSCODE_REMOTE_CC={shlex.quote(builder.cc)}
export VSCODE_REMOTE_CXX={shlex.quote(builder.cxx)}
{ci_environment}cd "$checkout"
{shell_checkout_gate(provenance.source_tree)}
{body}
""".strip()


def build_wsl(
    config: BuildConfig,
    manifest: ReleaseManifest,
    runner: CommandRunner,
    *,
    architecture: str,
    flavor: str = "release",
    skip_install: bool = False,
    skip_tests: bool = False,
    skip_gulp: bool = False,
    no_archive: bool = False,
) -> WslBuildResult:
    builder = preflight_wsl(config, runner, architecture=architecture)
    validate_build_flavor(flavor)
    artifact_directory = config.resolve_path("paths.artifacts")
    artifact_directory.mkdir(parents=True, exist_ok=True)
    release_name = (
        f"sprouted-code-{manifest.release}-linux-{architecture}"
        f"{artifact_flavor_suffix(flavor)}"
    )
    artifact_path = artifact_directory / linux_artifact_name(
        manifest.release, architecture, flavor
    )
    target = gulp_target("linux", architecture, flavor)
    provenance = expected_provenance(
        manifest,
        platform="linux",
        architecture=architecture,
        flavor=flavor,
        gulp_target=target,
    )
    script = build_wsl_build_script(
        builder,
        artifact_directory=windows_path_to_wsl(artifact_directory),
        release_name=release_name,
        provenance=provenance,
        flavor=flavor,
        skip_install=skip_install,
        skip_tests=skip_tests,
        skip_gulp=skip_gulp,
        no_archive=no_archive,
    )
    run_wsl_script(builder, runner, script)

    if runner.dry_run or no_archive:
        return WslBuildResult(artifact_path=None)
    if not artifact_path.is_file():
        raise ConfigError(f"Expected Linux artifact not found: {artifact_path}")
    write_checksums(artifact_directory)
    return WslBuildResult(artifact_path=artifact_path)
