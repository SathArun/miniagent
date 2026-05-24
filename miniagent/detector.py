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
