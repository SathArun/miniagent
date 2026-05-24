# iterateandfixagent Skill — Design

**Date:** 2026-05-24
**Status:** Approved

## Overview

A global Claude Code skill that replicates the functionality of the `miniagent` Python CLI using Claude's native tools. Given a project directory, it detects how to run the project, executes it, and uses Claude to fix errors — repeating until the project runs successfully or a max iteration count is reached.

## Invocation

- Skill name: `iterateandfixagent`
- Invoked as: `/iterateandfixagent`
- Installed at: `~/.claude/skills/iterateandfixagent.md`
- On invoke: Claude asks the user for the max iteration count (accepts Enter for default of 5)
- Project root: the current working directory (CWD) at time of invocation

## Configuration

Claude reads `agent_config.toml` from the CWD if present and extracts:
- `runner.error_patterns` — list of strings that indicate failure even when exit code is 0
- `runner.timeout_seconds` — command timeout in seconds

If `agent_config.toml` is absent or the keys are missing, defaults apply:
- `error_patterns`: `["Error", "Exception", "Traceback", "FAILED", "error:"]`
- `timeout_seconds`: 30

## Project Detection

Claude inspects the CWD in this priority order (matching `miniagent/detector.py`):

| Priority | Signal | Run command |
|----------|--------|-------------|
| 1 | `Dockerfile` present | `docker build . && docker run <image>` |
| 2 | `package.json` present | `npm install && npm start` (or `node index.js` if no start script) |
| 3 | `*.py` or `requirements.txt` present | `pip install -r requirements.txt && python <entry>` where entry is `main.py`, `app.py`, or the first `.py` found |
| 4 | Fallback | Ask the user what command to run |

### Caching

On first run, Claude writes to `.iterateandfixagent/` in the project root:
- `run_command.txt` — the detected (or user-supplied) run command
- `project_info.md` — a brief Claude-generated summary of the project

On subsequent runs, Claude reads from cache and skips detection entirely.

## The Fix Loop

Each iteration follows these steps:

1. **Run** — execute the command via `Bash` with the configured timeout
2. **Check success** — exit code 0 AND none of the `error_patterns` appear in combined stdout+stderr
3. **On success** — report how many iterations were needed, stop
4. **On failure** — scan stdout+stderr for filenames (tokens matching `\w+\.\w+`), read those files that exist in the project root, then apply fixes using `Edit`/`Write` directly
5. **Log** — append iteration outcome (command, exit code, files changed) to `.iterateandfixagent/logs/run_<timestamp>.txt`
6. **After max iterations** — report failure with the last error output and suggest next steps

### Key difference from Python agent

The Python agent uses full-file replacement via a custom `<<<FILE:>>>...<<<END>>>` patch format. This skill uses Claude's native `Edit` tool for surgical fixes, which is more precise and preserves unchanged code. Claude also retains full conversation context across iterations, so it can reason about what was tried before and avoid repeating failed fixes.

## Logging

Each run appends a human-readable log to `.iterateandfixagent/logs/run_<timestamp>.txt` containing:
- Timestamp and iteration number
- Command executed
- Exit code
- Whether success or failure
- Files modified (if any)
- Last error output on final failure

This mirrors the run log from the Python agent (`<target>/.miniagent/logs/run_<ts>.txt`).

## What This Replaces

| Python module | Replaced by |
|--------------|-------------|
| `detector.py` | Claude reasoning over `Glob`/`Bash` output |
| `runner.py` | `Bash` tool (handles exit code, stdout/stderr, timeout) |
| `fixer.py` — `LLMClient` | Claude itself (no SDK needed) |
| `fixer.py` — `parse_patches` | Not needed — Claude uses `Edit`/`Write` directly |
| `fixer.py` — `extract_relevant_files` | Claude scans error output for filenames |
| `cli.py` — `run_agent` loop | Skill instructions + Claude's reasoning |

## What This Does NOT Replace

- **Standalone CLI usage**: The Python agent (`python -m miniagent /path`) works without Claude Code. The skill requires Claude Code to be running.
- **OpenAI provider support**: The Python agent supports both Anthropic and OpenAI. The skill runs on Claude only.
- **Agent-level operational log**: The Python agent writes a separate `miniagent/logs/agent_<ts>.log`. The skill does not produce this; Claude's conversation serves as the operational record.

## Files Created/Modified

| Path | Description |
|------|-------------|
| `~/.claude/skills/iterateandfixagent.md` | The skill file (new) |
| `<project>/.iterateandfixagent/run_command.txt` | Cached run command (created by skill at runtime) |
| `<project>/.iterateandfixagent/project_info.md` | Cached project summary (created by skill at runtime) |
| `<project>/.iterateandfixagent/logs/run_<ts>.txt` | Per-run iteration log (created by skill at runtime) |
