from __future__ import annotations

from pathlib import Path

from .commands import CommandRunner
from .config import BuildConfig, ConfigError
from .manifest import ReleaseManifest
from .patches import resolve_build_patches


def prepare_windows_checkout(
    config: BuildConfig,
    manifest: ReleaseManifest,
    runner: CommandRunner,
    *,
    skip_fetch: bool = False,
) -> Path:
    checkout = config.resolve_path("builders.windows.vscode_checkout")
    if not (checkout / ".git").exists():
        raise ConfigError(f"VS Code Git checkout not found: {checkout}")

    status = runner.run(
        ["git", "status", "--porcelain"],
        cwd=checkout,
        capture_output=True,
    )
    if status is not None and status.stdout.strip():
        raise ConfigError(
            f"Refusing to prepare a dirty VS Code checkout: {checkout}. "
            "Use a dedicated clean build checkout."
        )

    upstream_url = str(config.require("source.upstream_url"))
    branch_prefix = str(config.require("source.build_branch_prefix")).rstrip("/")
    build_branch = f"{branch_prefix}/{manifest.release}"

    file_patches = resolve_build_patches(config, manifest)

    if not skip_fetch:
        runner.run(
            ["git", "fetch", upstream_url, manifest.base_branch],
            cwd=checkout,
        )

    runner.run(
        ["git", "switch", "-C", build_branch, manifest.base_commit],
        cwd=checkout,
    )

    for patch in file_patches:
        print(f"Applying Sprouted patch: {patch.name}")
        runner.run(
            ["git", "apply", "--ignore-whitespace", "--check", str(patch)],
            cwd=checkout,
        )
        runner.run(
            ["git", "apply", "--ignore-whitespace", str(patch)],
            cwd=checkout,
        )

    if file_patches:
        runner.run(["git", "add", "--all"], cwd=checkout)
        runner.run(
            [
                "git",
                "-c",
                "user.name=Sprouted Code Build",
                "-c",
                "user.email=sprouted-code-build@localhost",
                "commit",
                "-m",
                "Apply Sprouted Code local patch queue",
            ],
            cwd=checkout,
        )

    runner.run(["git", "status", "--short", "--branch"], cwd=checkout)
    return checkout
