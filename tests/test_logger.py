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
