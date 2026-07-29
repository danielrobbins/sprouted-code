from __future__ import annotations

import os
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence


def format_command(arguments: Sequence[str]) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline(list(arguments))
    return shlex.join(arguments)


@dataclass
class CommandRunner:
    dry_run: bool = False
    commands: list[tuple[str, ...]] = field(default_factory=list)

    def run(
        self,
        arguments: Sequence[str],
        *,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        input_text: str | None = None,
        capture_output: bool = False,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str] | None:
        command = tuple(str(argument) for argument in arguments)
        if not command:
            raise ValueError("Command cannot be empty")
        self.commands.append(command)

        location = f" (cwd: {cwd})" if cwd else ""
        print(f"+ {format_command(command)}{location}")
        if self.dry_run:
            return None

        return subprocess.run(
            command,
            cwd=cwd,
            env=dict(env) if env is not None else None,
            check=check,
            text=True,
            input=input_text,
            capture_output=capture_output,
        )
