import json
from datetime import datetime, timezone
from pathlib import Path


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


class RunLogger:
    def __init__(self, log_dir: Path):
        log_dir.mkdir(parents=True, exist_ok=True)
        ts = _timestamp()
        self._json_path = log_dir / f"run_{ts}.json"
        self._txt_path = log_dir / f"run_{ts}.txt"
        self._events: list[dict] = []

    def log(self, event: dict) -> None:
        event = {"ts": _now_iso(), **event}
        self._events.append(event)
        self._json_path.write_text(json.dumps(self._events, indent=2))
        with self._txt_path.open("a") as f:
            f.write(f"[{event['ts']}] {json.dumps({k: v for k, v in event.items() if k != 'ts'})}\n")

    def close(self) -> None:
        pass


class AgentLogger:
    def __init__(self, log_dir: Path):
        log_dir.mkdir(parents=True, exist_ok=True)
        self._path = log_dir / f"agent_{_timestamp()}.log"

    def _write(self, level: str, message: str) -> None:
        line = f"[{_now_iso()}] {level}: {message}\n"
        with self._path.open("a") as f:
            f.write(line)

    def info(self, message: str) -> None:
        self._write("INFO", message)

    def error(self, message: str) -> None:
        self._write("ERROR", message)

    def close(self) -> None:
        pass
