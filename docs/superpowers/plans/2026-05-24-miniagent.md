# miniagent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI tool that auto-detects, runs, and LLM-fixes code projects in a loop until they succeed or a max iteration limit is reached.

**Architecture:** Small package (`miniagent/`) with five focused modules — `detector`, `runner`, `fixer`, `logger`, `cli` — each with one responsibility. `cli.py` owns the main loop and wires the others together. Each input project stores its own cache and logs under `.miniagent/` inside the project folder.

**Tech Stack:** Python 3.11+, `tomllib` (stdlib), `anthropic` SDK, `openai` SDK, `pytest` for tests.

---

## File Map

| File | Responsibility |
|------|---------------|
| `pyproject.toml` | Package metadata, dependencies, entry point |
| `agent_config.toml` | Default LLM + runner config (committed to repo) |
| `miniagent/__init__.py` | Empty package marker |
| `miniagent/logger.py` | Dual JSON + text log writer, agent operational log |
| `miniagent/detector.py` | Project type detection, entry point inference, `ProjectInfo` dataclass |
| `miniagent/runner.py` | Subprocess execution, success judgment, `RunResult` dataclass |
| `miniagent/fixer.py` | LLM client abstraction, patch parsing, patch application, file extraction |
| `miniagent/cli.py` | Arg parsing, config loading, main loop |
| `tests/test_logger.py` | Logger unit tests |
| `tests/test_detector.py` | Detector unit tests |
| `tests/test_runner.py` | Runner unit tests |
| `tests/test_fixer.py` | Fixer unit tests |
| `tests/test_cli.py` | CLI integration tests (subprocess + LLM mocked) |

---

## Task 1: Project Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `agent_config.toml`
- Create: `miniagent/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "miniagent"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "anthropic>=0.25.0",
    "openai>=1.30.0",
]

[project.scripts]
miniagent = "miniagent.cli:main"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Create `agent_config.toml`**

```toml
[llm]
provider = "anthropic"
model = "claude-sonnet-4-6"
api_key_env = "ANTHROPIC_API_KEY"

[runner]
error_patterns = ["Error", "Exception", "FAILED", "Traceback", "npm ERR"]
timeout_seconds = 60
```

- [ ] **Step 3: Create empty package markers**

```python
# miniagent/__init__.py
# (empty)
```

```python
# tests/__init__.py
# (empty)
```

- [ ] **Step 4: Install in dev mode**

```bash
pip install -e ".[dev]" 2>/dev/null || pip install -e .
pip install pytest
```

Expected: no errors, `miniagent` command available.

- [ ] **Step 5: Commit**

```bash
git init
git add pyproject.toml agent_config.toml miniagent/__init__.py tests/__init__.py
git commit -m "chore: project scaffold"
```

---

## Task 2: `logger.py` — Dual Log Writer

**Files:**
- Create: `miniagent/logger.py`
- Create: `tests/test_logger.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_logger.py
import json
import re
from pathlib import Path
from miniagent.logger import RunLogger, AgentLogger


def test_run_logger_writes_json_event(tmp_path):
    logger = RunLogger(log_dir=tmp_path)
    logger.log({"event": "run_start", "iteration": 1, "command": "python main.py"})
    logger.close()

    json_files = list(tmp_path.glob("run_*.json"))
    assert len(json_files) == 1
    events = json.loads(json_files[0].read_text())
    assert events[0]["event"] == "run_start"
    assert events[0]["iteration"] == 1
    assert "ts" in events[0]


def test_run_logger_writes_text_event(tmp_path):
    logger = RunLogger(log_dir=tmp_path)
    logger.log({"event": "run_start", "iteration": 1, "command": "python main.py"})
    logger.close()

    txt_files = list(tmp_path.glob("run_*.txt"))
    assert len(txt_files) == 1
    content = txt_files[0].read_text()
    assert "run_start" in content
    assert re.search(r"\[\d{4}-\d{2}-\d{2}", content)


def test_run_logger_multiple_events(tmp_path):
    logger = RunLogger(log_dir=tmp_path)
    logger.log({"event": "run_start", "iteration": 1, "command": "python main.py"})
    logger.log({"event": "success", "iteration": 1})
    logger.close()

    json_files = list(tmp_path.glob("run_*.json"))
    events = json.loads(json_files[0].read_text())
    assert len(events) == 2
    assert events[1]["event"] == "success"


def test_agent_logger_writes_to_file(tmp_path):
    logger = AgentLogger(log_dir=tmp_path)
    logger.info("config loaded")
    logger.error("bad api key")
    logger.close()

    log_files = list(tmp_path.glob("agent_*.log"))
    assert len(log_files) == 1
    content = log_files[0].read_text()
    assert "config loaded" in content
    assert "bad api key" in content
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_logger.py -v
```

Expected: `ImportError: cannot import name 'RunLogger' from 'miniagent.logger'`

- [ ] **Step 3: Implement `miniagent/logger.py`**

```python
import json
from datetime import datetime, timezone
from pathlib import Path


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


class RunLogger:
    def __init__(self, log_dir: Path):
        log_dir.mkdir(parents=True, exist_ok=True)
        ts = _timestamp()
        self._json_path = log_dir / f"run_{ts}.json"
        self._txt_path = log_dir / f"run_{ts}.txt"
        self._events: list[dict] = []

    def log(self, event: dict) -> None:
        event = {"ts": _now_iso(), **event}
        self._events.append(event)
        self._json_path.write_text(json.dumps(self._events, indent=2))
        with self._txt_path.open("a") as f:
            f.write(f"[{event['ts']}] {json.dumps({k: v for k, v in event.items() if k != 'ts'})}\n")

    def close(self) -> None:
        pass


class AgentLogger:
    def __init__(self, log_dir: Path):
        log_dir.mkdir(parents=True, exist_ok=True)
        self._path = log_dir / f"agent_{_timestamp()}.log"

    def _write(self, level: str, message: str) -> None:
        line = f"[{_now_iso()}] {level}: {message}\n"
        with self._path.open("a") as f:
            f.write(line)

    def info(self, message: str) -> None:
        self._write("INFO", message)

    def error(self, message: str) -> None:
        self._write("ERROR", message)

    def close(self) -> None:
        pass
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_logger.py -v
```

Expected: 4 tests PASSED.

- [ ] **Step 5: Commit**

```bash
git add miniagent/logger.py tests/test_logger.py
git commit -m "feat: add dual JSON+text run logger and agent logger"
```

---

## Task 3: `detector.py` — Project Type Detection

**Files:**
- Create: `miniagent/detector.py`
- Create: `tests/test_detector.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_detector.py
import pytest
from pathlib import Path
from miniagent.detector import detect, ProjectInfo


def make_project(tmp_path: Path, files: dict[str, str]) -> Path:
    for name, content in files.items():
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    return tmp_path


def test_detect_python_via_requirements(tmp_path):
    make_project(tmp_path, {"requirements.txt": "requests", "main.py": "print('hi')"})
    info = detect(tmp_path)
    assert info.runtime == "python"
    assert info.entry_point == "main.py"
    assert info.run_command == "python main.py"


def test_detect_python_via_py_files(tmp_path):
    make_project(tmp_path, {"app.py": "print('hi')"})
    info = detect(tmp_path)
    assert info.runtime == "python"
    assert info.entry_point == "app.py"


def test_detect_python_entry_point_preference(tmp_path):
    make_project(tmp_path, {
        "requirements.txt": "",
        "main.py": "",
        "other.py": "",
    })
    info = detect(tmp_path)
    assert info.entry_point == "main.py"


def test_detect_nodejs(tmp_path):
    make_project(tmp_path, {"package.json": '{"main": "index.js", "scripts": {"start": "node index.js"}}'})
    info = detect(tmp_path)
    assert info.runtime == "nodejs"
    assert info.run_command == "npm start"


def test_detect_nodejs_no_start_script(tmp_path):
    make_project(tmp_path, {"package.json": '{"main": "server.js"}', "server.js": ""})
    info = detect(tmp_path)
    assert info.runtime == "nodejs"
    assert info.run_command == "node server.js"


def test_detect_docker(tmp_path):
    make_project(tmp_path, {"Dockerfile": "FROM python:3.11"})
    info = detect(tmp_path)
    assert info.runtime == "docker"
    assert "docker build" in info.run_command


def test_detect_docker_takes_priority(tmp_path):
    make_project(tmp_path, {"Dockerfile": "FROM node:18", "package.json": "{}"})
    info = detect(tmp_path)
    assert info.runtime == "docker"


def test_detect_unknown_raises(tmp_path):
    make_project(tmp_path, {"README.md": "hello"})
    with pytest.raises(ValueError, match="Unsupported project type"):
        detect(tmp_path)


def test_detect_returns_project_info_dataclass(tmp_path):
    make_project(tmp_path, {"main.py": ""})
    info = detect(tmp_path)
    assert isinstance(info, ProjectInfo)
    assert info.runtime
    assert info.run_command
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_detector.py -v
```

Expected: `ImportError: cannot import name 'detect' from 'miniagent.detector'`

- [ ] **Step 3: Implement `miniagent/detector.py`**

```python
import json
from dataclasses import dataclass
from pathlib import Path

_PYTHON_ENTRY_POINTS = ["main.py", "app.py", "run.py", "server.py", "src/main.py"]
_NODE_ENTRY_POINTS = ["index.js", "server.js", "app.js", "src/index.js"]


@dataclass
class ProjectInfo:
    runtime: str
    entry_point: str
    run_command: str


def detect(project_folder: Path) -> ProjectInfo:
    if (project_folder / "Dockerfile").exists():
        return ProjectInfo(
            runtime="docker",
            entry_point="Dockerfile",
            run_command="docker build -t miniagent_run . && docker run miniagent_run",
        )

    if (project_folder / "package.json").exists():
        return _detect_nodejs(project_folder)

    if (project_folder / "requirements.txt").exists() or list(project_folder.glob("*.py")):
        return _detect_python(project_folder)

    raise ValueError(f"Unsupported project type in {project_folder}")


def _detect_python(project_folder: Path) -> ProjectInfo:
    entry = _find_entry(project_folder, _PYTHON_ENTRY_POINTS, "*.py")
    return ProjectInfo(runtime="python", entry_point=entry, run_command=f"python {entry}")


def _detect_nodejs(project_folder: Path) -> ProjectInfo:
    pkg = project_folder / "package.json"
    try:
        data = json.loads(pkg.read_text())
        if "start" in data.get("scripts", {}):
            return ProjectInfo(runtime="nodejs", entry_point="package.json", run_command="npm start")
        main = data.get("main")
        if main:
            return ProjectInfo(runtime="nodejs", entry_point=main, run_command=f"node {main}")
    except (json.JSONDecodeError, KeyError):
        pass
    entry = _find_entry(project_folder, _NODE_ENTRY_POINTS, "*.js")
    return ProjectInfo(runtime="nodejs", entry_point=entry, run_command=f"node {entry}")


def _find_entry(folder: Path, candidates: list[str], glob: str) -> str:
    for name in candidates:
        if (folder / name).exists():
            return name
    found = list(folder.glob(glob))
    if found:
        return found[0].name
    return "main"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_detector.py -v
```

Expected: 9 tests PASSED.

- [ ] **Step 5: Commit**

```bash
git add miniagent/detector.py tests/test_detector.py
git commit -m "feat: add project type detector for Python, Node.js, and Docker"
```

---

## Task 4: `runner.py` — Subprocess Execution

**Files:**
- Create: `miniagent/runner.py`
- Create: `tests/test_runner.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_runner.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_runner.py -v
```

Expected: `ImportError: cannot import name 'run' from 'miniagent.runner'`

- [ ] **Step 3: Implement `miniagent/runner.py`**

```python
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
    except subprocess.TimeoutExpired:
        return RunResult(exit_code=-1, stdout="", stderr="Timeout expired", success=False)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_runner.py -v
```

Expected: 6 tests PASSED.

- [ ] **Step 5: Commit**

```bash
git add miniagent/runner.py tests/test_runner.py
git commit -m "feat: add subprocess runner with success judgment and timeout"
```

---

## Task 5: `fixer.py` — LLM Client, Patch Parsing, Patch Application

**Files:**
- Create: `miniagent/fixer.py`
- Create: `tests/test_fixer.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_fixer.py
import re
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from miniagent.fixer import parse_patches, apply_patches, extract_relevant_files, LLMClient


def test_parse_patches_single_file():
    response = "<<<FILE: src/main.py>>>\nprint('fixed')\n<<<END>>>"
    patches = parse_patches(response)
    assert patches == {"src/main.py": "print('fixed')\n"}


def test_parse_patches_multiple_files():
    response = (
        "<<<FILE: a.py>>>\nline1\n<<<END>>>\n"
        "<<<FILE: b.py>>>\nline2\n<<<END>>>"
    )
    patches = parse_patches(response)
    assert patches == {"a.py": "line1\n", "b.py": "line2\n"}


def test_parse_patches_empty_response():
    patches = parse_patches("No patches here, just text.")
    assert patches == {}


def test_apply_patches_overwrites_file(tmp_path):
    (tmp_path / "main.py").write_text("old content")
    apply_patches({"main.py": "new content"}, project_folder=tmp_path)
    assert (tmp_path / "main.py").read_text() == "new content"


def test_apply_patches_creates_missing_file(tmp_path):
    apply_patches({"src/new.py": "content"}, project_folder=tmp_path)
    assert (tmp_path / "src" / "new.py").read_text() == "content"


def test_extract_relevant_files_from_traceback(tmp_path):
    (tmp_path / "main.py").write_text("")
    (tmp_path / "utils.py").write_text("")
    stderr = 'File "main.py", line 5, in <module>\n  File "utils.py", line 12'
    files = extract_relevant_files(stderr, project_folder=tmp_path)
    names = [f.name for f in files]
    assert "main.py" in names
    assert "utils.py" in names


def test_extract_relevant_files_skips_nonexistent(tmp_path):
    (tmp_path / "main.py").write_text("")
    stderr = 'File "main.py", line 5\nFile "ghost.py", line 1'
    files = extract_relevant_files(stderr, project_folder=tmp_path)
    names = [f.name for f in files]
    assert "ghost.py" not in names


def test_llm_client_anthropic_generate_project_info():
    config = {"provider": "anthropic", "model": "claude-sonnet-4-6", "api_key_env": "ANTHROPIC_API_KEY"}
    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
        with patch("anthropic.Anthropic") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.return_value = MagicMock(
                content=[MagicMock(text="Project summary here")]
            )
            client = LLMClient(config)
            result = client.generate_project_info(file_listing="main.py\nutils.py")
            assert "Project summary here" in result
            mock_client.messages.create.assert_called_once()


def test_llm_client_openai_fix_code():
    config = {"provider": "openai", "model": "gpt-4o", "api_key_env": "OPENAI_API_KEY"}
    with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
        with patch("openai.OpenAI") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_client.chat.completions.create.return_value = MagicMock(
                choices=[MagicMock(message=MagicMock(content="<<<FILE: main.py>>>\nfixed\n<<<END>>>"))]
            )
            client = LLMClient(config)
            result = client.fix_code(
                project_info="Python project",
                command="python main.py",
                stdout="",
                stderr="NameError",
                relevant_files={"main.py": "broken code"},
            )
            assert "<<<FILE:" in result
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_fixer.py -v
```

Expected: `ImportError: cannot import name 'parse_patches' from 'miniagent.fixer'`

- [ ] **Step 3: Implement `miniagent/fixer.py`**

```python
import os
import re
from pathlib import Path

_PATCH_RE = re.compile(r"<<<FILE:\s*(.+?)>>>\n(.*?)<<<END>>>", re.DOTALL)
_FILENAME_RE = re.compile(r'[\w./\\-]+\.\w+')


def parse_patches(response: str) -> dict[str, str]:
    return {m.group(1).strip(): m.group(2) for m in _PATCH_RE.finditer(response)}


def apply_patches(patches: dict[str, str], project_folder: Path) -> None:
    for rel_path, content in patches.items():
        target = project_folder / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)


def extract_relevant_files(error_output: str, project_folder: Path) -> list[Path]:
    candidates = set(_FILENAME_RE.findall(error_output))
    found = []
    for name in candidates:
        path = project_folder / name
        if path.exists():
            found.append(path)
    return found


class LLMClient:
    def __init__(self, config: dict):
        self._provider = config["provider"]
        self._model = config["model"]
        api_key = os.environ[config["api_key_env"]]

        if self._provider == "anthropic":
            import anthropic
            self._client = anthropic.Anthropic(api_key=api_key)
        elif self._provider == "openai":
            import openai
            self._client = openai.OpenAI(api_key=api_key)
        else:
            raise ValueError(f"Unsupported LLM provider: {self._provider}")

    def generate_project_info(self, file_listing: str) -> str:
        prompt = (
            f"You are analyzing a code project. Here are its files:\n\n{file_listing}\n\n"
            "Write a concise project_info.md covering: runtime, entry point, and what the project does."
        )
        return self._chat(prompt)

    def fix_code(
        self,
        project_info: str,
        command: str,
        stdout: str,
        stderr: str,
        relevant_files: dict[str, str],
    ) -> str:
        files_block = "\n\n".join(
            f"=== {path} ===\n{content}" for path, content in relevant_files.items()
        )
        prompt = (
            f"Project info:\n{project_info}\n\n"
            f"Failed command: {command}\n\n"
            f"stdout:\n{stdout}\n\nstderr:\n{stderr}\n\n"
            f"Relevant files:\n{files_block}\n\n"
            "Fix the code. Return ONLY the fixed files using this format:\n"
            "<<<FILE: relative/path/to/file>>>\n<full file content>\n<<<END>>>"
        )
        return self._chat(prompt)

    def _chat(self, prompt: str) -> str:
        if self._provider == "anthropic":
            response = self._client.messages.create(
                model=self._model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        else:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.choices[0].message.content
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_fixer.py -v
```

Expected: 9 tests PASSED.

- [ ] **Step 5: Commit**

```bash
git add miniagent/fixer.py tests/test_fixer.py
git commit -m "feat: add LLM fixer with patch parsing, application, and provider abstraction"
```

---

## Task 6: `cli.py` — Main Loop

**Files:**
- Create: `miniagent/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_cli.py
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from miniagent.cli import run_agent


def make_python_project(tmp_path: Path) -> Path:
    (tmp_path / "main.py").write_text("print('hello')")
    return tmp_path


def default_config():
    return {
        "llm": {"provider": "anthropic", "model": "claude-sonnet-4-6", "api_key_env": "ANTHROPIC_API_KEY"},
        "runner": {"error_patterns": ["Error", "Traceback"], "timeout_seconds": 10},
    }


def test_first_run_creates_miniagent_dir(tmp_path):
    project = make_python_project(tmp_path)
    config = default_config()

    with patch("miniagent.cli.LLMClient") as mock_llm_cls:
        mock_llm = MagicMock()
        mock_llm_cls.return_value = mock_llm
        mock_llm.generate_project_info.return_value = "# Project Info\nPython project."

        run_agent(project_folder=project, iterations=1, config=config, agent_log_dir=tmp_path / "agent_logs")

    assert (project / ".miniagent" / "project_info.md").exists()
    assert (project / ".miniagent" / "run_command.txt").exists()


def test_cached_run_skips_llm_project_info(tmp_path):
    project = make_python_project(tmp_path)
    miniagent_dir = project / ".miniagent"
    miniagent_dir.mkdir()
    (miniagent_dir / "project_info.md").write_text("# cached info")
    (miniagent_dir / "run_command.txt").write_text(f"{sys.executable} main.py")
    config = default_config()

    with patch("miniagent.cli.LLMClient") as mock_llm_cls:
        mock_llm = MagicMock()
        mock_llm_cls.return_value = mock_llm

        run_agent(project_folder=project, iterations=1, config=config, agent_log_dir=tmp_path / "agent_logs")

        mock_llm.generate_project_info.assert_not_called()


def test_success_on_first_iteration(tmp_path):
    project = make_python_project(tmp_path)
    miniagent_dir = project / ".miniagent"
    miniagent_dir.mkdir()
    (miniagent_dir / "project_info.md").write_text("# info")
    (miniagent_dir / "run_command.txt").write_text(f"{sys.executable} main.py")
    config = default_config()

    with patch("miniagent.cli.LLMClient") as mock_llm_cls:
        mock_llm = MagicMock()
        mock_llm_cls.return_value = mock_llm
        result = run_agent(project_folder=project, iterations=3, config=config, agent_log_dir=tmp_path / "agent_logs")

    assert result is True
    mock_llm.fix_code.assert_not_called()


def test_fix_applied_on_failure_then_success(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "main.py").write_text("syntax error !!!!")
    miniagent_dir = project / ".miniagent"
    miniagent_dir.mkdir()
    (miniagent_dir / "project_info.md").write_text("# info")
    (miniagent_dir / "run_command.txt").write_text(f"{sys.executable} main.py")
    config = default_config()

    def side_effect(**kwargs):
        (project / "main.py").write_text("print('fixed')")
        return f"<<<FILE: main.py>>>\nprint('fixed')\n<<<END>>>"

    with patch("miniagent.cli.LLMClient") as mock_llm_cls:
        mock_llm = MagicMock()
        mock_llm_cls.return_value = mock_llm
        mock_llm.fix_code.side_effect = side_effect

        result = run_agent(project_folder=project, iterations=3, config=config, agent_log_dir=tmp_path / "agent_logs")

    assert result is True


def test_returns_false_after_max_iterations(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "main.py").write_text("import nonexistent_module")
    miniagent_dir = project / ".miniagent"
    miniagent_dir.mkdir()
    (miniagent_dir / "project_info.md").write_text("# info")
    (miniagent_dir / "run_command.txt").write_text(f"{sys.executable} main.py")
    config = default_config()

    with patch("miniagent.cli.LLMClient") as mock_llm_cls:
        mock_llm = MagicMock()
        mock_llm_cls.return_value = mock_llm
        mock_llm.fix_code.return_value = ""

        result = run_agent(project_folder=project, iterations=2, config=config, agent_log_dir=tmp_path / "agent_logs")

    assert result is False
    assert mock_llm.fix_code.call_count == 2


def test_run_logs_created_in_project_folder(tmp_path):
    project = make_python_project(tmp_path)
    miniagent_dir = project / ".miniagent"
    miniagent_dir.mkdir()
    (miniagent_dir / "project_info.md").write_text("# info")
    (miniagent_dir / "run_command.txt").write_text(f"{sys.executable} main.py")
    config = default_config()

    with patch("miniagent.cli.LLMClient") as mock_llm_cls:
        mock_llm_cls.return_value = MagicMock()
        run_agent(project_folder=project, iterations=1, config=config, agent_log_dir=tmp_path / "agent_logs")

    log_dir = project / ".miniagent" / "logs"
    assert list(log_dir.glob("run_*.json"))
    assert list(log_dir.glob("run_*.txt"))
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_cli.py -v
```

Expected: `ImportError: cannot import name 'run_agent' from 'miniagent.cli'`

- [ ] **Step 3: Implement `miniagent/cli.py`**

```python
import argparse
import os
import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    raise RuntimeError("Python 3.11+ required")

from miniagent.detector import detect
from miniagent.runner import run
from miniagent.fixer import LLMClient, parse_patches, apply_patches, extract_relevant_files
from miniagent.logger import RunLogger, AgentLogger


def _load_config(config_path: Path) -> dict:
    with open(config_path, "rb") as f:
        return tomllib.load(f)


def _file_listing(project_folder: Path) -> str:
    return "\n".join(
        str(p.relative_to(project_folder))
        for p in sorted(project_folder.rglob("*"))
        if p.is_file() and ".miniagent" not in p.parts
    )


def run_agent(project_folder: Path, iterations: int, config: dict, agent_log_dir: Path) -> bool:
    agent_log = AgentLogger(log_dir=agent_log_dir)
    agent_log.info(f"Starting run: project={project_folder}, iterations={iterations}")

    llm = LLMClient(config["llm"])
    miniagent_dir = project_folder / ".miniagent"
    info_path = miniagent_dir / "project_info.md"
    cmd_path = miniagent_dir / "run_command.txt"

    if not miniagent_dir.exists():
        agent_log.info("First run — detecting project and generating project_info")
        miniagent_dir.mkdir(parents=True)
        info = detect(project_folder)
        project_info_md = llm.generate_project_info(_file_listing(project_folder))
        info_path.write_text(project_info_md)
        cmd_path.write_text(info.run_command)
        agent_log.info(f"Detected runtime={info.runtime}, command={info.run_command}")
    else:
        agent_log.info("Cached run — reading project_info and run_command")

    project_info = info_path.read_text()
    command = cmd_path.read_text().strip()
    run_log = RunLogger(log_dir=miniagent_dir / "logs")
    error_patterns = config["runner"]["error_patterns"]
    timeout = config["runner"]["timeout_seconds"]

    for i in range(1, iterations + 1):
        agent_log.info(f"Iteration {i}: running `{command}`")
        run_log.log({"event": "run_start", "iteration": i, "command": command})

        result = run(command=command, cwd=project_folder, timeout=timeout, error_patterns=error_patterns)
        run_log.log({
            "event": "run_result",
            "iteration": i,
            "exit_code": result.exit_code,
            "stdout": result.stdout,
            "stderr": result.stderr,
        })

        if result.success:
            run_log.log({"event": "success", "iteration": i})
            agent_log.info(f"Success on iteration {i}")
            run_log.close()
            agent_log.close()
            return True

        agent_log.info(f"Iteration {i} failed — requesting LLM fix")
        relevant_paths = extract_relevant_files(result.stderr + result.stdout, project_folder)
        relevant_files = {
            str(p.relative_to(project_folder)): p.read_text()
            for p in relevant_paths
        }

        llm_response = llm.fix_code(
            project_info=project_info,
            command=command,
            stdout=result.stdout,
            stderr=result.stderr,
            relevant_files=relevant_files,
        )
        patches = parse_patches(llm_response)
        if patches:
            apply_patches(patches, project_folder)
            run_log.log({
                "event": "fix_applied",
                "iteration": i,
                "files_changed": list(patches.keys()),
            })
            agent_log.info(f"Applied patches to: {list(patches.keys())}")

    run_log.log({"event": "failure", "iteration": iterations, "reason": "max iterations reached"})
    agent_log.info(f"Failed after {iterations} iterations")
    run_log.close()
    agent_log.close()
    return False


def main():
    parser = argparse.ArgumentParser(description="miniagent — auto code-fixing agent")
    parser.add_argument("project_folder", type=Path, help="Path to the project folder")
    parser.add_argument("--iterations", type=int, default=5, help="Max fix iterations (default: 5)")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).parent.parent / "agent_config.toml",
        help="Path to agent_config.toml",
    )
    args = parser.parse_args()

    config = _load_config(args.config)
    agent_log_dir = Path(__file__).parent.parent / "logs"
    success = run_agent(
        project_folder=args.project_folder.resolve(),
        iterations=args.iterations,
        config=config,
        agent_log_dir=agent_log_dir,
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_cli.py -v
```

Expected: 6 tests PASSED.

- [ ] **Step 5: Run full test suite**

```bash
pytest -v
```

Expected: all tests PASSED (25+).

- [ ] **Step 6: Commit**

```bash
git add miniagent/cli.py tests/test_cli.py
git commit -m "feat: add main loop CLI wiring all modules together"
```

---

## Task 7: End-to-End Smoke Test

**Files:**
- Create: `tests/sample_project/main.py` — a deliberately broken Python script for manual testing

- [ ] **Step 1: Create a broken sample project**

```python
# tests/sample_project/main.py
import requests  # intentionally missing from requirements, no requirements.txt
respons = requests.get("https://httpbin.org/get")  # typo: respons
print(respons.status_code)
```

- [ ] **Step 2: Set your API key**

```bash
export ANTHROPIC_API_KEY=your-key-here
```

- [ ] **Step 3: Run miniagent against the sample project**

```bash
python -m miniagent tests/sample_project --iterations 3
```

Expected: agent detects Python project, generates `.miniagent/project_info.md`, runs, fails, sends to LLM, applies fix, runs again. Exit 0 on success.

- [ ] **Step 4: Inspect logs**

```bash
cat tests/sample_project/.miniagent/project_info.md
cat tests/sample_project/.miniagent/run_command.txt
ls tests/sample_project/.miniagent/logs/
```

Expected: `project_info.md` has LLM summary, `run_command.txt` has `python main.py`, logs folder has one JSON and one text file.

- [ ] **Step 5: Commit**

```bash
git add tests/sample_project/
git commit -m "test: add broken sample project for smoke testing"
```

---

## Self-Review Notes

- All spec sections covered: detection (Task 3), running (Task 4), LLM fixing (Task 5), logging (Task 2), main loop (Task 6), first-run caching (Task 6), log locations (Tasks 2 + 6).
- `ProjectInfo` defined in Task 3, used in Task 6 — consistent.
- `RunResult` defined in Task 4, used in Task 6 — consistent.
- `LLMClient` defined in Task 5, imported in Task 6 — consistent.
- `RunLogger` / `AgentLogger` defined in Task 2, used in Task 6 — consistent.
- No TBDs or placeholders remain.
