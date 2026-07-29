from __future__ import annotations

import hashlib
import shlex
import uuid
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
from .proxmox import (
    ProxmoxBuilder,
    resolve_proxmox_builder,
    run_container_script,
    run_proxmox_host_command,
)
from .wsl_build import linux_artifact_name


@dataclass(frozen=True)
class ProxmoxBuildResult:
    artifact_path: Path | None


def build_proxmox_preflight_script(builder: ProxmoxBuilder) -> str:
    return f"""
#!/usr/bin/env bash
set -euo pipefail
checkout={shlex.quote(builder.checkout)}
node_dir={shlex.quote(builder.node_directory)}
expected_arch={shlex.quote(builder.host_architecture)}
if [ "$(uname -m)" != "$expected_arch" ]; then
  echo "Linux {builder.architecture} builds require $expected_arch; found $(uname -m)" >&2
  exit 2
fi
if [ ! -d "$checkout/.git" ]; then
  echo "Proxmox VS Code checkout not found: $checkout" >&2
  exit 2
fi
export PATH="$node_dir/bin:$PATH"
for command in git python3 {shlex.quote(builder.cc)} {shlex.quote(builder.cxx)} make pkg-config tar sha256sum node npm; do
  command -v "$command" >/dev/null 2>&1 || {{ echo "Missing required command: $command" >&2; exit 2; }}
done
case "$(node --version)" in
  v24.*) ;;
  *) echo "Wrong Node major: $(node --version); expected Node 24.x" >&2; exit 2 ;;
esac
echo "Proxmox preflight OK: container={builder.container_id} arch=$(uname -m) node=$(node --version) npm=$(npm --version) checkout=$checkout"
""".strip()


def preflight_proxmox(
    config: BuildConfig,
    runner: CommandRunner,
    *,
    architecture: str | None = None,
) -> ProxmoxBuilder:
    builder = resolve_proxmox_builder(config, architecture=architecture)
    run_container_script(
        builder,
        runner,
        build_proxmox_preflight_script(builder),
        name=f"sprouted-preflight-linux-proxmox-{builder.architecture}",
    )
    return builder


def build_proxmox_build_script(
    builder: ProxmoxBuilder,
    *,
    release_name: str,
    provenance: BuildProvenance,
    flavor: str,
    skip_install: bool,
    skip_tests: bool,
    skip_gulp: bool,
    no_archive: bool,
) -> str:
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
                f"artifact_dir={shlex.quote(builder.artifact_directory)}",
                f"release_name={shlex.quote(release_name)}",
                'mkdir -p "$artifact_dir"',
                'artifact_path="$artifact_dir/${release_name}.tar.gz"',
                'rm -f "$artifact_path" "$artifact_path.sha256"',
                'tar -czf "$artifact_path" -C "$(dirname "$output_dir")" '
                '"$(basename "$output_dir")"',
                'sha256sum "$artifact_path" > "$artifact_path.sha256"',
                'echo "Built artifact: $artifact_path"',
            )
        )
    body = "\n".join(commands) or ":"
    ci_environment = "export CI=1\n" if flavor == "release" else ""
    return f"""
#!/usr/bin/env bash
set -euo pipefail
export LANG=C.UTF-8
export LC_ALL=C.UTF-8
checkout={shlex.quote(builder.checkout)}
output_dir="$(dirname "$checkout")/VSCode-linux-{builder.architecture}"
node_dir={shlex.quote(builder.node_directory)}
export PATH="$node_dir/bin:$PATH"
export CC={shlex.quote(builder.cc)}
export CXX={shlex.quote(builder.cxx)}
export VSCODE_REMOTE_CC={shlex.quote(builder.cc)}
export VSCODE_REMOTE_CXX={shlex.quote(builder.cxx)}
{ci_environment}cd "$checkout"
{shell_checkout_gate(provenance.source_tree)}
{body}
""".strip()


def _pull_artifact(
    builder: ProxmoxBuilder,
    runner: CommandRunner,
    remote_path: str,
    local_path: Path,
) -> None:
    host_path = f"/tmp/sprouted-pull-{uuid.uuid4().hex}-{local_path.name}"
    command = (
        f"sudo rm -f {shlex.quote(host_path)} && "
        f"sudo pct pull {builder.container_id} {shlex.quote(remote_path)} "
        f"{shlex.quote(host_path)} && sudo chown {builder.remote_owner} "
        f"{shlex.quote(host_path)} && test -s {shlex.quote(host_path)}"
    )
    run_proxmox_host_command(builder, runner, command)
    temporary = local_path.with_suffix(local_path.suffix + ".tmp")
    if temporary.exists():
        temporary.unlink()
    try:
        runner.run(
            [
                "scp",
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=10",
                f"{builder.ssh_target}:{host_path}",
                str(temporary),
            ]
        )
        if not runner.dry_run:
            temporary.replace(local_path)
    finally:
        run_proxmox_host_command(builder, runner, f"rm -f {shlex.quote(host_path)}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_proxmox(
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
) -> ProxmoxBuildResult:
    builder = preflight_proxmox(config, runner, architecture=architecture)
    validate_build_flavor(flavor)
    release_name = (
        f"sprouted-code-{manifest.release}-linux-{architecture}"
        f"{artifact_flavor_suffix(flavor)}"
    )
    target = gulp_target("linux", architecture, flavor)
    provenance = expected_provenance(
        manifest,
        platform="linux",
        architecture=architecture,
        flavor=flavor,
        gulp_target=target,
    )
    script = build_proxmox_build_script(
        builder,
        release_name=release_name,
        provenance=provenance,
        flavor=flavor,
        skip_install=skip_install,
        skip_tests=skip_tests,
        skip_gulp=skip_gulp,
        no_archive=no_archive,
    )
    run_container_script(
        builder,
        runner,
        script,
        name=f"sprouted-build-linux-proxmox-{builder.architecture}",
    )
    if runner.dry_run or no_archive or no_pull:
        return ProxmoxBuildResult(artifact_path=None)

    artifact_directory = config.resolve_path("paths.artifacts")
    artifact_directory.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_directory / linux_artifact_name(
        manifest.release, architecture, flavor
    )
    remote_path = f"{builder.artifact_directory}/{artifact_path.name}"
    _pull_artifact(builder, runner, remote_path, artifact_path)
    checksum_path = artifact_path.with_suffix(artifact_path.suffix + ".sha256")
    _pull_artifact(builder, runner, remote_path + ".sha256", checksum_path)
    if not artifact_path.is_file():
        raise ConfigError(f"Expected pulled Linux artifact not found: {artifact_path}")
    try:
        expected_hash = checksum_path.read_text(encoding="utf-8").split()[0].lower()
        actual_hash = _sha256(artifact_path)
        if actual_hash != expected_hash:
            raise ConfigError(
                f"Pulled artifact checksum mismatch: expected {expected_hash}, "
                f"calculated {actual_hash}"
            )
    finally:
        checksum_path.unlink(missing_ok=True)
    write_checksums(artifact_directory)
    return ProxmoxBuildResult(artifact_path=artifact_path)
