from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Mapping, Sequence

from .jsonio import write_json
from .model import CommandResult


class CommandRunner:
    def __init__(self, log_directory: Path, environment: Mapping[str, str]) -> None:
        self.log_directory = log_directory
        self.environment = dict(environment)
        self.counter = 0

    def run(
        self,
        argv: Sequence[str | Path],
        *,
        cwd: Path,
        label: str,
        timeout_seconds: int = 120,
    ) -> CommandResult:
        normalized = tuple(str(value) for value in argv)
        started = time.monotonic()
        timed_out = False
        try:
            completed = subprocess.run(
                normalized,
                cwd=cwd,
                env=self.environment,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=timeout_seconds,
                check=False,
            )
            returncode = completed.returncode
            stdout = completed.stdout
            stderr = completed.stderr
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            returncode = 124
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")

        result = CommandResult(
            argv=normalized,
            cwd=str(cwd.resolve()),
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
            duration_ms=round((time.monotonic() - started) * 1000),
            timed_out=timed_out,
        )
        self.counter += 1
        safe_label = "".join(
            character if character.isalnum() or character in "-_." else "_"
            for character in label
        )
        write_json(
            self.log_directory / f"{self.counter:03d}-{safe_label}.json",
            result.as_dict(),
        )
        return result

