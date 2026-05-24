# miniagent — Auto Code-Fixing Agent Design Spec

**Date:** 2026-05-24  
**Status:** Approved

---

## Overview

`miniagent` is a Python CLI tool that takes a project folder as input, determines how to run it, executes it, detects failures, and uses an LLM to fix the code — repeating until the project runs successfully or a maximum iteration count is reached. Everything the agent does is logged completely.

---

## Package Structure

```
miniagent/                           ← agent source (this repo)
├── miniagent/
│   ├── __init__.py
│   ├── cli.py          # entry point, arg parsing, main loop
│   ├── detector.py     # project type detection (Python / Node.js / Docker)
│   ├── runner.py       # subprocess execution + success/failure judgment
│   ├── fixer.py        # LLM client abstraction + patch application
│   └── logger.py       # dual JSON + text log writer
├── logs/
│   └── agent_<timestamp>.log        ← miniagent operational log
├── agent_config.toml   # LLM provider, model, error patterns, timeout
└── pyproject.toml      # dependencies
```

Each input project stores its own cached metadata and run logs:

```
/path/to/input-project/              ← user-provided folder
├── .miniagent/
│   ├── project_info.md              ← LLM-generated: runtime, entry point, functionality summary
│   ├── run_command.txt              ← exact command used to run the project
│   └── logs/
│       ├── run_<timestamp>.json     ← structured log of this run
│       └── run_<timestamp>.txt      ← human-readable log of this run
└── ... (project's own files)
```

This design keeps the agent stateless: each project folder is self-contained and the agent can be pointed at any number of different projects without configuration changes.

---

## Invocation

```bash
python -m miniagent /path/to/project --iterations 5
```

---

## Core Loop

```
1. Parse CLI args: folder path, --iterations N
2. Load agent_config.toml (LLM provider, model, API key env var, error patterns, timeout)
3. If project/.miniagent/ does not exist:
   a. detector.py → detect runtime + entry point from project files
   b. fixer.py (LLM) → generate project_info.md (runtime, entry point, functionality summary)
   c. Write project_info.md and run_command.txt to project/.miniagent/
4. Else: read cached project_info.md and run_command.txt
5. For iteration i in 1..N:
   a. runner.py → execute project via subprocess, capture stdout/stderr, exit code
   b. logger.py → log run attempt (command, output, exit code)
   c. If success (exit code 0 AND no error patterns in output) → log success, exit 0
   d. fixer.py → send error context + relevant code files to LLM, receive file patches
   e. Apply patches (overwrite modified files)
   f. logger.py → log which files were changed and the LLM's reasoning
6. If still failing after N iterations → log final failure summary, exit non-zero
```

---

## Module Responsibilities

### `cli.py`
- Parses `--iterations` and folder path via `argparse`
- Loads `agent_config.toml`
- Owns the main loop, calls all other modules in sequence
- Initializes both the agent-level logger and the run-level logger

### `detector.py`
- Inspects project files to determine runtime:
  - `requirements.txt` or `*.py` → Python
  - `package.json` → Node.js
  - `Dockerfile` → Docker
- Infers likely entry point (`main.py`, `index.js`, `app.py`, `server.js`, etc.)
- Returns a `ProjectInfo` dataclass: `{runtime, entry_point, run_command}`

### `runner.py`
- Executes the run command via `subprocess.run` with configurable timeout
- Captures stdout and stderr
- Applies success judgment: exit code 0 AND none of the configured error patterns appear in combined output
- Returns a `RunResult` dataclass: `{exit_code, stdout, stderr, success}`

### `fixer.py`
- Provider-agnostic LLM client: reads `provider` from config, instantiates the correct SDK client (Anthropic or OpenAI)
- On first run: sends project file listing to LLM, asks for `project_info.md` content
- On failure: sends `project_info.md` + failed command + stdout/stderr + contents of files named in the error output → asks LLM to return patches
- Parses LLM patch response (see Patch Format below)
- Applies patches by overwriting files

### `logger.py`
- Accepts structured event dicts and writes them simultaneously to:
  - JSON log (append to array in `run_<timestamp>.json`)
  - Text log (formatted lines in `run_<timestamp>.txt`)
- Events: `run_start`, `run_result`, `fix_applied`, `success`, `failure`, `agent_error`

---

## LLM Configuration (`agent_config.toml`)

```toml
[llm]
provider = "anthropic"          # or "openai"
model = "claude-sonnet-4-6"
api_key_env = "ANTHROPIC_API_KEY"   # name of the environment variable holding the key

[runner]
error_patterns = ["Error", "Exception", "FAILED", "Traceback", "npm ERR"]
timeout_seconds = 60
```

---

## LLM Patch Format

The LLM is instructed to return fixes in this exact format:

```
<<<FILE: relative/path/to/file.py>>>
<full corrected file content>
<<<END>>>
```

Multiple files can be patched in a single response. `fixer.py` parses this format and overwrites each named file. Full file replacement (no diff parsing) keeps the implementation simple and unambiguous.

**Context sent to LLM on failure:**
- Contents of `project_info.md`
- The failed run command
- Full stdout + stderr
- Contents of source files whose names appear in the error output — extracted via regex (`[\w/\\]+\.\w+`) matched against files that exist in the project folder

This limits token usage to relevant files only rather than sending the entire project tree.

---

## Logging Format

### Run JSON log (`project/.miniagent/logs/run_<timestamp>.json`)

```json
[
  {"ts": "2026-05-24T10:00:00", "event": "run_start", "iteration": 1, "command": "python main.py"},
  {"ts": "2026-05-24T10:00:02", "event": "run_result", "iteration": 1, "exit_code": 1, "stdout": "...", "stderr": "..."},
  {"ts": "2026-05-24T10:00:03", "event": "fix_applied", "iteration": 1, "files_changed": ["src/main.py"], "llm_reasoning": "..."},
  {"ts": "2026-05-24T10:00:05", "event": "run_result", "iteration": 2, "exit_code": 0, "stdout": "..."},
  {"ts": "2026-05-24T10:00:05", "event": "success", "iteration": 2}
]
```

### Run text log (`project/.miniagent/logs/run_<timestamp>.txt`)

```
[2026-05-24 10:00:00] ITERATION 1 — Running: python main.py
[2026-05-24 10:00:02] FAILED (exit code 1)
  stderr: ModuleNotFoundError: No module named 'requests'
[2026-05-24 10:00:03] FIX APPLIED — Modified: src/main.py
  Reason: Added missing 'requests' import
[2026-05-24 10:00:05] ITERATION 2 — Running: python main.py
[2026-05-24 10:00:05] SUCCESS
```

### Agent operational log (`miniagent/logs/agent_<timestamp>.log`)

Plain text. Logs: config loaded, target folder, detected project type, agent-level errors (bad API key, unparseable LLM response, unsupported project type, subprocess timeout).

---

## Success Criteria

A run is considered successful when **both** conditions are met:
1. Process exits with code 0
2. Combined stdout + stderr contains none of the configured `error_patterns`

---

## Supported Project Types

| Runtime   | Detection signal                        | Default run command         |
|-----------|-----------------------------------------|-----------------------------|
| Python    | `requirements.txt` or `*.py` present   | `python <entry_point>`      |
| Node.js   | `package.json` present                  | `npm start` or `node <entry_point>` |
| Docker    | `Dockerfile` present                    | `docker build -t miniagent_run . && docker run miniagent_run` |

If no supported runtime is detected, the agent logs an error and exits with a clear message.

---

## Dependencies

- `tomllib` (stdlib in Python 3.11+) — config parsing
- `anthropic` — Anthropic SDK (optional, loaded only if provider is `anthropic`)
- `openai` — OpenAI SDK (optional, loaded only if provider is `openai`)
- No other third-party dependencies
