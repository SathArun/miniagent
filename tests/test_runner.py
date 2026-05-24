import sys
import pytest
from miniagent.runner import run, RunResult


def test_run_success_exit_zero(tmp_path):
    result = run(
        command=f"{sys.executable} -c \"print('hello')\"",
        cwd=tmp_path,
        timeout=10,
        error_patterns=[],
    )
    assert result.exit_code == 0
    assert result.success is True
    assert "hello" in result.stdout


def test_run_failure_nonzero_exit(tmp_path):
    result = run(
        command=f"{sys.executable} -c \"import sys; sys.exit(1)\"",
        cwd=tmp_path,
        timeout=10,
        error_patterns=[],
    )
    assert result.exit_code == 1
    assert result.success is False


def test_run_failure_error_pattern_in_output(tmp_path):
    result = run(
        command=f"{sys.executable} -c \"print('Error: something went wrong')\"",
        cwd=tmp_path,
        timeout=10,
        error_patterns=["Error"],
    )
    assert result.exit_code == 0
    assert result.success is False


def test_run_captures_stderr(tmp_path):
    result = run(
        command=f"{sys.executable} -c \"import sys; sys.stderr.write('oops')\"",
        cwd=tmp_path,
        timeout=10,
        error_patterns=[],
    )
    assert "oops" in result.stderr


def test_run_timeout(tmp_path):
    result = run(
        command=f"{sys.executable} -c \"import time; time.sleep(10)\"",
        cwd=tmp_path,
        timeout=1,
        error_patterns=[],
    )
    assert result.success is False
    assert result.exit_code == -1


def test_run_returns_run_result_dataclass(tmp_path):
    result = run(
        command=f"{sys.executable} -c \"print('ok')\"",
        cwd=tmp_path,
        timeout=10,
        error_patterns=[],
    )
    assert isinstance(result, RunResult)
    assert hasattr(result, "exit_code")
    assert hasattr(result, "stdout")
    assert hasattr(result, "stderr")
    assert hasattr(result, "success")
