import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RunResult:
    exit_code: int
    stdout: str
    stderr: str
    success: bool


def run(command: str, cwd: Path, timeout: int, error_patterns: list[str]) -> RunResult:
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        combined = result.stdout + result.stderr
        pattern_found = any(p in combined for p in error_patterns)
        success = result.returncode == 0 and not pattern_found
        return RunResult(
            exit_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            success=success,
        )
    except subprocess.TimeoutExpired as e:
        stdout = e.stdout if isinstance(e.stdout, str) else (e.stdout.decode(errors="replace") if e.stdout else "")
        return RunResult(
            exit_code=-1,  # -1 signals timeout (not a real process exit code)
            stdout=stdout,
            stderr="Timeout expired",
            success=False,
        )
