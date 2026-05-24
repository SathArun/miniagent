# miniagent

A Python CLI that automatically fixes broken projects using an LLM. Point it at any project folder — it detects how to run it, executes it, and iteratively applies LLM-generated patches until the project runs successfully.

## How It Works

```
miniagent /path/to/broken-project --iterations 5
```

On each iteration:
1. Runs the project via subprocess
2. If it fails, extracts filenames from the error output and reads those files
3. Sends the error context + relevant source files to an LLM
4. Applies the patches the LLM returns
5. Repeats until success or the iteration limit is reached

On first run, the agent auto-detects the project type and caches metadata in `<project>/.miniagent/`. Subsequent runs use the cache — no re-detection.

## Supported Project Types

| Runtime | Detection signal | Default run command |
|---------|-----------------|---------------------|
| Python | `requirements.txt` or `*.py` present | `python <entry_point>` |
| Node.js | `package.json` present | `npm start` or `node <entry_point>` |
| Docker | `Dockerfile` present | `docker build … && docker run …` |

Detection priority: Dockerfile > package.json > Python files.

## Installation

Requires Python 3.11+.

```bash
pip install -e ".[dev]"
```

Set your LLM provider API key as an environment variable (e.g. `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`).

## Usage

```bash
# Fix a project with default settings (5 iterations, Anthropic/claude-sonnet-4-6)
python -m miniagent /path/to/project

# Override iteration count
python -m miniagent /path/to/project --iterations 10

# Use a custom config file
python -m miniagent /path/to/project --config my_config.toml
```

## Configuration

Edit `agent_config.toml` to change the LLM provider, model, error detection patterns, or timeout:

```toml
[llm]
provider = "anthropic"          # or "openai"
model = "claude-sonnet-4-6"
api_key_env = "ANTHROPIC_API_KEY"

[runner]
error_patterns = ["Error", "Exception", "FAILED", "Traceback", "npm ERR"]
timeout_seconds = 60
```

## Logs

Two separate log streams are written per run:

- **`miniagent/logs/agent_<ts>.log`** — operational log of the agent itself (detection result, LLM call outcomes, errors)
- **`<project>/.miniagent/logs/run_<ts>.json`** and **`run_<ts>.txt`** — per-iteration log of what happened inside the target project (command, stdout/stderr, patches applied)

## Development

```bash
# Run all tests
pytest

# Run a single test file
pytest tests/test_fixer.py

# Run a single test by name
pytest tests/test_fixer.py::test_parse_patches_single_file
```

## Architecture

The codebase is five focused modules:

| Module | Responsibility |
|--------|---------------|
| `cli.py` | Entry point, argument parsing, main fix loop |
| `detector.py` | Infers runtime, entry point, and run command from project files |
| `runner.py` | Executes the run command, captures output, judges success/failure |
| `fixer.py` | LLM client (Anthropic + OpenAI), patch parsing and application |
| `logger.py` | Dual JSON + text log writer |

Success requires both exit code 0 **and** none of the configured `error_patterns` appearing in combined stdout+stderr.
