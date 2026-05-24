---
name: iterateandfixagent
description: Detect how to run a project in the current directory, execute it, and use Claude to fix errors — repeating until success or max iterations reached. Mirrors the miniagent Python CLI using Claude's native tools.
---

# iterateandfixagent

You are running an automated fix loop on the project in the current working directory. Follow these steps in order.

## Step 1: Ask for max iterations

Ask the user: "How many fix iterations should I try? (press Enter for default: 5)"

Wait for their response. If they press Enter or give no specific number, use 5. Store this as MAX_ITERATIONS.

## Step 2: Load configuration

Check if `agent_config.toml` exists in the CWD using Read or Bash.

If it exists, read it and extract:
- `runner.error_patterns` — list of strings that indicate failure even when exit code is 0
- `runner.timeout_seconds` — command timeout in seconds

If absent or keys are missing, use these defaults:
- error_patterns: `["Error", "Exception", "Traceback", "FAILED", "error:"]`
- timeout_seconds: `30`

## Step 3: Check cache

Check whether BOTH of these files exist in the CWD:
- `.iterateandfixagent/run_command.txt`
- `.iterateandfixagent/project_info.md`

If both exist: read the command from `run_command.txt` (strip leading/trailing whitespace). Skip to Step 5.

If either is missing: proceed to Step 4.

## Step 4: Detect project type and write cache

Inspect the CWD files in this priority order:

1. **`Dockerfile` present** → command: `docker build -t iterateandfixagent-target . && docker run iterateandfixagent-target`
2. **`package.json` present** → read it; if a `start` script exists: `npm install && npm start`; otherwise: `npm install && node index.js`
3. **`requirements.txt` OR any `.py` file present** → find entry point in this order: `main.py`, then `app.py`, then the first `.py` file found alphabetically; command: `python <entry>` (prepend `pip install -r requirements.txt && ` if `requirements.txt` exists)
4. **None of the above** → ask the user: "I couldn't detect how to run this project. What command should I use?" and wait for their answer.

Create `.iterateandfixagent/` directory if it doesn't exist.

Write the detected (or user-supplied) command to `.iterateandfixagent/run_command.txt`.

Write a brief project summary to `.iterateandfixagent/project_info.md` covering: detected runtime, entry point filename, and 2-3 sentences describing what the project appears to do based on the files you've seen.

## Step 5: Run the fix loop

Create `.iterateandfixagent/logs/` directory if it doesn't exist.

Get the current timestamp (format: `YYYY-MM-DD_HH-MM-SS`) and create a log file at `.iterateandfixagent/logs/run_<timestamp>.txt`.

Repeat the following up to MAX_ITERATIONS times, keeping track of the current iteration number N (starting at 1):

### Each iteration

**a) Log the start** — append to the log file:
```
=== Iteration N / MAX_ITERATIONS ===
Time: <current timestamp>
Command: <command>
```

**b) Run the command** — execute it via Bash in the CWD. Set a timeout matching `timeout_seconds`.

**c) Check for success** — success means BOTH:
- Exit code is 0
- None of the `error_patterns` strings appear anywhere in the combined stdout+stderr output

If success:
- Append to log: `Result: SUCCESS`
- Tell the user: "✓ Project ran successfully on iteration N of MAX_ITERATIONS."
- Stop the loop immediately.

**d) On failure — find relevant files** — scan the combined stdout+stderr for tokens that look like filenames: any sequence of word characters, dots, and slashes that ends with a known extension (`.py`, `.js`, `.ts`, `.json`, `.toml`, `.txt`, `.sh`, `.rb`, `.go`, `.java`, `.cpp`, `.c`, `.h`). For each candidate filename, check if a file with that name exists anywhere under the project root (excluding `.iterateandfixagent/`). Collect the paths of all that exist and read their contents.

**e) On failure — fix the code** — reason about the error in the context of the relevant files and the project info. Apply fixes using:
- `Edit` tool for surgical changes to existing files (preferred)
- `Write` tool only when creating a new file or when the entire file must change

Do not apply fixes that repeat something already tried in a previous iteration of this run.

**f) Log the outcome** — append to the log file:
```
Exit code: <code>
Stdout (first 500 chars): <text>
Stderr (first 500 chars): <text>
Files modified: <comma-separated list, or "none">
```

### After MAX_ITERATIONS with no success

Append to log: `Result: FAILED after MAX_ITERATIONS iterations`

Tell the user:
- The project could not be fixed within MAX_ITERATIONS iterations
- Show the last error output (stdout + stderr)
- List every file modified across all iterations
- Suggest they review the changes manually or re-invoke with more iterations
