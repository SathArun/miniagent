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


def test_incomplete_cache_triggers_first_run(tmp_path):
    project = make_python_project(tmp_path)
    miniagent_dir = project / ".miniagent"
    miniagent_dir.mkdir()
    # Only project_info.md exists — run_command.txt is missing (interrupted first run)
    (miniagent_dir / "project_info.md").write_text("# partial cache")
    config = default_config()

    with patch("miniagent.cli.LLMClient") as mock_llm_cls:
        mock_llm = MagicMock()
        mock_llm_cls.return_value = mock_llm
        mock_llm.generate_project_info.return_value = "# regenerated"

        run_agent(project_folder=project, iterations=1, config=config, agent_log_dir=tmp_path / "agent_logs")

    mock_llm.generate_project_info.assert_called_once()
    assert (project / ".miniagent" / "run_command.txt").exists()


def test_no_parseable_patches_logs_agent_error(tmp_path):
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
        mock_llm.fix_code.return_value = "Sorry, I cannot fix this."

        run_agent(project_folder=project, iterations=1, config=config, agent_log_dir=tmp_path / "agent_logs")

    log_files = list((tmp_path / "agent_logs").glob("agent_*.log"))
    assert log_files
    content = log_files[0].read_text()
    assert "no parseable patches" in content


def test_fix_applied_log_includes_llm_reasoning(tmp_path):
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
        return "<<<FILE: main.py>>>\nprint('fixed')\n<<<END>>>"

    with patch("miniagent.cli.LLMClient") as mock_llm_cls:
        mock_llm = MagicMock()
        mock_llm_cls.return_value = mock_llm
        mock_llm.fix_code.side_effect = side_effect

        run_agent(project_folder=project, iterations=3, config=config, agent_log_dir=tmp_path / "agent_logs")

    import json
    log_dir = project / ".miniagent" / "logs"
    json_file = list(log_dir.glob("run_*.json"))[0]
    events = json.loads(json_file.read_text())
    fix_events = [e for e in events if e.get("event") == "fix_applied"]
    assert fix_events
    assert "llm_reasoning" in fix_events[0]


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
