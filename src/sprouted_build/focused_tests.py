from __future__ import annotations

from collections.abc import Mapping

from .commands import CommandRunner
from .config import BuildConfig, ConfigError
from .windows import WindowsToolchain, resolve_windows_toolchain


FOCUSED_BYOK_TESTS = (
    "src/extension/byok/common/test/byokProvider.spec.ts",
    "src/extension/byok/vscode-node/test/byokPolicy.spec.ts",
)


def run_focused_windows_tests(
    config: BuildConfig,
    runner: CommandRunner,
    *,
    toolchain: WindowsToolchain | None = None,
    environment: Mapping[str, str] | None = None,
) -> None:
    toolchain = toolchain or resolve_windows_toolchain(config, runner)
    copilot_path = toolchain.checkout / "extensions" / "copilot"
    vitest = copilot_path / "node_modules" / ".bin" / "vitest.cmd"
    if not runner.dry_run and not vitest.is_file():
        raise ConfigError(
            f"Vitest command not found: {vitest}; run npm ci in the VS Code checkout"
        )

    for test_path in FOCUSED_BYOK_TESTS:
        runner.run(
            [str(vitest), "--run", "--pool=forks", test_path],
            cwd=copilot_path,
            env=environment if environment is not None else toolchain.environment,
        )
