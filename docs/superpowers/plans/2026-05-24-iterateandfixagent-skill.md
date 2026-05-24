# iterateandfixagent Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Write a global Claude Code skill that detects how to run a project in the CWD, executes it, and iteratively fixes errors using Claude's native tools until success or max iterations.

**Architecture:** A single markdown skill file installed at `~/.claude/skills/iterateandfixagent.md`. When invoked as `/iterateandfixagent`, Claude follows the skill's natural-language instructions, using Bash/Glob/Read/Edit/Write natively — no Python, no SDK, no custom patch format. A reference copy is committed to the miniagent repo at `.claude/skills/iterateandfixagent.md`.

**Tech Stack:** Claude Code skill markdown, Bash tool, Read/Edit/Write tools, Glob tool.

---

### Task 1: Write the skill file

**Files:**
- Create: `~/.claude/skills/iterateandfixagent.md`

- [ ] **Step 1: Create the global skills directory if it doesn't exist**

Run:
```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.claude\skills"
```
Expected: directory exists (no error if already present)

- [ ] **Step 2: Write the skill file**

Write the following content exactly to `~/.claude/skills/iterateandfixagent.md`:

````markdown
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
````

- [ ] **Step 3: Verify the file was written**

Run:
```powershell
Get-Content "$env:USERPROFILE\.claude\skills\iterateandfixagent.md" | Select-Object -First 5
```
Expected: first 5 lines including the frontmatter `---` and `name: iterateandfixagent`

---

### Task 2: Commit reference copy to repo

**Files:**
- Create: `.claude/skills/iterateandfixagent.md` (copy of the skill, tracked in git)

- [ ] **Step 1: Create the local skills directory**

Run:
```powershell
New-Item -ItemType Directory -Force "C:\Arun\miniagent\.claude\skills"
```

- [ ] **Step 2: Copy the skill file into the repo**

```powershell
Copy-Item "$env:USERPROFILE\.claude\skills\iterateandfixagent.md" "C:\Arun\miniagent\.claude\skills\iterateandfixagent.md"
```

- [ ] **Step 3: Verify the copy**

Run:
```powershell
Test-Path "C:\Arun\miniagent\.claude\skills\iterateandfixagent.md"
```
Expected: `True`

- [ ] **Step 4: Commit**

```bash
cd C:\Arun\miniagent
git add .claude/skills/iterateandfixagent.md
git commit -m "feat: add iterateandfixagent global skill (reference copy)"
```

---

### Task 3: Smoke test against sample project

The repo contains `tests/sample_project/main.py` which has intentional errors — it's the perfect target.

**Files:**
- Read: `tests/sample_project/main.py` (verify it has errors before testing)
- Observe: `.iterateandfixagent/` created under `tests/sample_project/`

- [ ] **Step 1: Verify the sample project has errors**

Run:
```bash
cd C:\Arun\miniagent\tests\sample_project && python main.py
```
Expected: non-zero exit code or error output — confirming it's a valid broken target.

- [ ] **Step 2: Check the sample project has no leftover cache**

Run:
```powershell
Test-Path "C:\Arun\miniagent\tests\sample_project\.iterateandfixagent"
```
Expected: `False` (clean state for first-run test). If `True`, delete it:
```powershell
Remove-Item -Recurse -Force "C:\Arun\miniagent\tests\sample_project\.iterateandfixagent"
```

- [ ] **Step 3: Invoke the skill manually (simulate what Claude does)**

Open a Claude Code session with CWD set to `C:\Arun\miniagent\tests\sample_project` and run `/iterateandfixagent`.

Verify:
1. Claude asks for iteration count
2. Claude detects Python (finds `main.py` or `requirements.txt`)
3. `.iterateandfixagent/run_command.txt` is created with a `python main.py` style command
4. `.iterateandfixagent/project_info.md` is created with a project summary
5. `.iterateandfixagent/logs/run_<timestamp>.txt` is created and updated each iteration
6. Claude applies fixes using `Edit`/`Write`
7. Claude reports success or failure at the end

- [ ] **Step 4: Verify cache files were created**

Run:
```powershell
Get-ChildItem "C:\Arun\miniagent\tests\sample_project\.iterateandfixagent" -Recurse
```
Expected: `run_command.txt`, `project_info.md`, and at least one file under `logs/`

- [ ] **Step 5: Test second invocation uses cache**

Re-invoke `/iterateandfixagent` in the same CWD (after restoring `main.py` to its broken state if fixed).

Verify Claude skips detection and reads from `run_command.txt` directly (confirm in its output that it says something about reading cached command).

- [ ] **Step 6: Test agent_config.toml is read**

Create a minimal `agent_config.toml` in the sample project:
```toml
[runner]
error_patterns = ["SyntaxError", "NameError", "FAIL"]
timeout_seconds = 20
```

Re-invoke `/iterateandfixagent` and verify Claude uses these patterns instead of the defaults (it should mention them when describing its configuration).

Remove the test `agent_config.toml` when done:
```powershell
Remove-Item "C:\Arun\miniagent\tests\sample_project\agent_config.toml"
```

- [ ] **Step 7: Cleanup .iterateandfixagent from sample project**

```powershell
Remove-Item -Recurse -Force "C:\Arun\miniagent\tests\sample_project\.iterateandfixagent"
```

This keeps the sample project clean for the existing Python agent tests (`test_cli.py` etc.).
