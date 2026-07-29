from __future__ import annotations

import shlex
import uuid
from dataclasses import dataclass
from pathlib import Path

from .artifacts import sha256_file, write_checksums
from .commands import CommandRunner
from .config import BuildConfig, ConfigError
from .flavors import artifact_flavor_suffix, gulp_target, validate_build_flavor
from .macos import (
    MacOSBuilder,
    preflight_macos,
    run_macos_host_command,
    run_macos_script,
)
from .manifest import ReleaseManifest
from .provenance import (
    BuildProvenance,
    expected_provenance,
    shell_checkout_gate,
    shell_verify_output_provenance,
    shell_write_output_provenance,
)

MACOS_BUNDLE_IDENTIFIER = "org.kernel-seeds.sprouted-code"
MACOS_CLI_NAME = "sprouted-code"


@dataclass(frozen=True)
class MacOSBuildResult:
    artifact_path: Path | None


def macos_artifact_name(
    release: str,
    architecture: str,
    flavor: str = "release",
) -> str:
    if architecture != "arm64":
        raise ConfigError(f"Unsupported macOS architecture: {architecture}")
    return (
        f"sprouted-code-{release}-darwin-{architecture}"
        f"{artifact_flavor_suffix(flavor)}.zip"
    )


def build_macos_build_script(
    builder: MacOSBuilder,
    *,
    release_name: str,
    provenance: BuildProvenance,
    flavor: str,
    skip_install: bool,
    skip_tests: bool,
    skip_gulp: bool,
    no_archive: bool,
) -> str:
    validate_build_flavor(flavor)
    commands: list[str] = []
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
        commands.extend(
            (
                'rm -rf "$output_dir"',
                f"npm run gulp -- {provenance.gulp_target}",
                shell_checkout_gate(provenance.source_tree),
                shell_write_output_provenance(provenance),
            )
        )
    if not no_archive:
        commands.extend(
            (
                shell_checkout_gate(provenance.source_tree),
                shell_verify_output_provenance(provenance),
                'app_path="$output_dir/Sprouted Code.app"',
                'if [ ! -d "$app_path" ]; then\n'
                '  echo "Expected packaged application not found: $app_path" >&2\n'
                "  exit 2\nfi",
                'executable_name="$(/usr/libexec/PlistBuddy -c '
                "'Print :CFBundleExecutable' "
                '"$app_path/Contents/Info.plist")"',
                'if [ ! -x "$app_path/Contents/MacOS/$executable_name" ]; then\n'
                '  echo "Packaged application executable not found: '
                '$executable_name" >&2\n'
                "  exit 2\nfi",
                'bundle_identifier="$(/usr/libexec/PlistBuddy -c '
                "'Print :CFBundleIdentifier' "
                '"$app_path/Contents/Info.plist")"',
                f'if [ "$bundle_identifier" != "{MACOS_BUNDLE_IDENTIFIER}" ]; then\n'
                '  echo "Unexpected application bundle identifier: '
                '$bundle_identifier" >&2\n'
                "  exit 2\nfi",
                f'cli_path="$app_path/Contents/Resources/app/bin/{MACOS_CLI_NAME}"',
                'if [ ! -x "$cli_path" ]; then\n'
                '  echo "Packaged command-line launcher not found: '
                '$cli_path" >&2\n'
                "  exit 2\nfi",
                'codesign --force --deep --sign - --timestamp=none "$app_path"',
                'codesign --verify --deep --strict --verbose=2 "$app_path"',
                'signature_details="$(codesign -dv --verbose=4 "$app_path" 2>&1)"',
                "if ! printf '%s\\n' \"$signature_details\" | "
                "grep -q '^Signature=adhoc$'; then\n"
                '  echo "Packaged application does not have the expected '
                'ad-hoc signature" >&2\n'
                "  exit 2\nfi",
                'mkdir -p "$artifact_dir"',
                'artifact_path="$artifact_dir/${release_name}.zip"',
                'rm -f "$artifact_path" "$artifact_path.sha256"',
                '(cd "$output_dir" && zip -Xqry "$artifact_path" '
                '"Sprouted Code.app" ".sprouted-build-provenance.json")',
                'shasum -a 256 "$artifact_path" > "$artifact_path.sha256"',
                'echo "Built artifact: $artifact_path"',
            )
        )
    body = "\n".join(commands) or ":"
    ci_environment = "export CI=1\n" if flavor == "release" else ""
    return f"""
#!/usr/bin/env bash
set -euo pipefail
checkout={shlex.quote(builder.checkout)}
checkout="${{checkout/#\\~/$HOME}}"
output_dir="$(dirname "$checkout")/VSCode-darwin-{builder.architecture}"
node_dir={shlex.quote(builder.node_directory)}
node_dir="${{node_dir/#\\~/$HOME}}"
artifact_dir={shlex.quote(builder.artifact_directory)}
artifact_dir="${{artifact_dir/#\\~/$HOME}}"
release_name={shlex.quote(release_name)}
export PATH="$node_dir/bin:$PATH"
{ci_environment}cd "$checkout"
{shell_checkout_gate(provenance.source_tree)}
{body}
""".strip()


def _pull_macos_artifact(
    builder: MacOSBuilder,
    runner: CommandRunner,
    remote_path: str,
    local_path: Path,
) -> None:
    transfer_path = f"/tmp/sprouted-pull-{uuid.uuid4().hex}-{local_path.name}"
    prepare = (
        f"source_path={shlex.quote(remote_path)}; "
        'source_path="${source_path/#\\~/$HOME}"; '
        f'cp "$source_path" {shlex.quote(transfer_path)}'
    )
    run_macos_host_command(builder, runner, prepare)
    temporary = local_path.with_suffix(local_path.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    try:
        runner.run(
            [
                "scp",
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=10",
                f"{builder.ssh_target}:{transfer_path}",
                str(temporary),
            ]
        )
        if not runner.dry_run:
            temporary.replace(local_path)
    finally:
        run_macos_host_command(
            builder,
            runner,
            f"rm -f {shlex.quote(transfer_path)}",
        )


def build_macos(
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
    no_pull: bool = False,
) -> MacOSBuildResult:
    builder = preflight_macos(config, runner, architecture=architecture)
    validate_build_flavor(flavor)
    target = gulp_target("darwin", architecture, flavor)
    provenance = expected_provenance(
        manifest,
        platform="darwin",
        architecture=architecture,
        flavor=flavor,
        gulp_target=target,
    )
    release_name = (
        f"sprouted-code-{manifest.release}-darwin-{architecture}"
        f"{artifact_flavor_suffix(flavor)}"
    )
    script = build_macos_build_script(
        builder,
        release_name=release_name,
        provenance=provenance,
        flavor=flavor,
        skip_install=skip_install,
        skip_tests=skip_tests,
        skip_gulp=skip_gulp,
        no_archive=no_archive,
    )
    run_macos_script(
        builder,
        runner,
        script,
        name=f"sprouted-build-macos-{builder.architecture}",
    )
    if runner.dry_run or no_archive or no_pull:
        return MacOSBuildResult(artifact_path=None)

    artifact_directory = config.resolve_path("paths.artifacts")
    artifact_directory.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_directory / macos_artifact_name(
        manifest.release,
        architecture,
        flavor,
    )
    remote_path = f"{builder.artifact_directory}/{artifact_path.name}"
    checksum_path = artifact_path.with_suffix(artifact_path.suffix + ".sha256")
    _pull_macos_artifact(builder, runner, remote_path, artifact_path)
    _pull_macos_artifact(builder, runner, remote_path + ".sha256", checksum_path)
    try:
        expected_hash = checksum_path.read_text(encoding="utf-8").split()[0].lower()
        actual_hash = sha256_file(artifact_path)
        if actual_hash != expected_hash:
            raise ConfigError(
                f"Pulled artifact checksum mismatch: expected {expected_hash}, "
                f"calculated {actual_hash}"
            )
    finally:
        checksum_path.unlink(missing_ok=True)
    write_checksums(artifact_directory)
    return MacOSBuildResult(artifact_path=artifact_path)
