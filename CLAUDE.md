# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Does

`miniagent` is a Python CLI that takes an arbitrary project folder, detects how to run it, executes it, and uses an LLM to fix errors — repeating until the project runs successfully or a max iteration count is reached. It is an agent that fixes *other* projects, not itself.

## Commands

```bash
# Run all tests
pytest

# Run a single test file
pytest tests/test_fixer.py

# Run a single test by name
pytest tests/test_fixer.py::test_parse_patches_single_file

# Install in editable mode (required before running tests or CLI)
pip install -e ".[dev]"

# Run the CLI against a target project
python -m miniagent /path/to/some/project --iterations 5 --config agent_config.toml
```

## Architecture

The agent runs a loop in `cli.py::run_agent()`:

1. **First run**: `detector.py` inspects the target project folder and returns a `ProjectInfo` (runtime, entry point, run command). The LLM then generates a `project_info.md` summary. Both are cached in `<target-project>/.miniagent/`.
2. **Subsequent runs**: cached `project_info.md` and `run_command.txt` are read directly — no re-detection.
3. **Each iteration**: `runner.py` executes the command via `subprocess.run`. Success requires exit code 0 **and** none of the configured `error_patterns` appearing in combined stdout+stderr.
4. **On failure**: `fixer.py` extracts filenames from the error output (regex on stderr), reads those files, and sends them with the full error context to the LLM. The LLM returns patches in a structured format that `fixer.py` parses and applies.

### LLM Patch Format

The LLM is prompted to return fixes in exactly this format — any deviation means no patches are applied:

```
<<<FILE: relative/path/to/file.py>>>
<full corrected file content>
<<<END>>>
```

`parse_patches()` in `fixer.py` uses a regex to extract these. Multiple files can be patched in one response. Patch paths are validated against the project root to prevent path traversal.

### Two Distinct Log Streams

- **Agent log** (`miniagent/logs/agent_<ts>.log`): operational log of the miniagent process itself — config loaded, detection result, LLM call outcomes, agent-level errors.
- **Run log** (`<target-project>/.miniagent/logs/run_<ts>.json` + `.txt`): per-iteration structured log of what happened inside the target project — command run, stdout/stderr, patches applied.

### LLM Provider Abstraction

`LLMClient` in `fixer.py` supports `anthropic` and `openai` providers, selected by `agent_config.toml`. The SDK is imported lazily at init time. Both providers use the same two-method interface: `generate_project_info()` and `fix_code()`.

## Key Design Constraints

- **Stateless agent**: all per-project state lives inside `<target-project>/.miniagent/`, so the agent can be pointed at any number of projects without configuration changes.
- **Full file replacement**: patches overwrite entire files — no diff parsing. This keeps `fixer.py` simple but means the LLM must return complete file contents.
- **Relevant-files-only context**: only files whose names appear in the error output are sent to the LLM, limiting token usage.
- **Detection priority**: Dockerfile > `package.json` > `*.py` / `requirements.txt`. See `detector.py` for the exact order.
