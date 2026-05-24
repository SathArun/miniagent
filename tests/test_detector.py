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
