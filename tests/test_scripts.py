import os
import sys
from pathlib import Path

import pytest

SCRIPTS = sorted((Path(__file__).resolve().parents[1] / "scripts").glob("*.sh"))


def test_there_are_shell_scripts_to_check() -> None:
    assert SCRIPTS


@pytest.mark.skipif(sys.platform == "win32", reason="Windows has no executable bit")
@pytest.mark.parametrize("script", SCRIPTS, ids=lambda path: path.name)
def test_shell_scripts_are_executable(script: Path) -> None:
    # docs/install.md runs ./scripts/install-linux-dependencies.sh directly.
    assert script.read_text(encoding="utf-8").startswith("#!")
    assert os.access(script, os.X_OK), (
        f"{script.name} has a shebang but is not executable"
    )
