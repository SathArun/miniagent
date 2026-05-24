import argparse
import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    raise RuntimeError("Python 3.11+ required")

from miniagent.detector import detect
from miniagent.runner import run
from miniagent.fixer import LLMClient, parse_patches, apply_patches, extract_relevant_files
from miniagent.logger import RunLogger, AgentLogger


def _load_config(config_path: Path) -> dict:
    with open(config_path, "rb") as f:
        return tomllib.load(f)


def _file_listing(project_folder: Path) -> str:
    return "\n".join(
        str(p.relative_to(project_folder))
        for p in sorted(project_folder.rglob("*"))
        if p.is_file() and ".miniagent" not in p.parts
    )


def run_agent(project_folder: Path, iterations: int, config: dict, agent_log_dir: Path) -> bool:
    agent_log = AgentLogger(log_dir=agent_log_dir)
    agent_log.info(f"Starting run: project={project_folder}, iterations={iterations}")

    llm = LLMClient(config["llm"])
    miniagent_dir = project_folder / ".miniagent"
    info_path = miniagent_dir / "project_info.md"
    cmd_path = miniagent_dir / "run_command.txt"

    if not info_path.exists() or not cmd_path.exists():
        agent_log.info("First run — detecting project and generating project_info")
        miniagent_dir.mkdir(parents=True, exist_ok=True)
        info = detect(project_folder)
        project_info_md = llm.generate_project_info(_file_listing(project_folder))
        info_path.write_text(project_info_md)
        cmd_path.write_text(info.run_command)
        agent_log.info(f"Detected runtime={info.runtime}, command={info.run_command}")
    else:
        agent_log.info("Cached run — reading project_info and run_command")

    project_info = info_path.read_text()
    command = cmd_path.read_text().strip()
    run_log = RunLogger(log_dir=miniagent_dir / "logs")
    error_patterns = config["runner"]["error_patterns"]
    timeout = config["runner"]["timeout_seconds"]

    try:
        for i in range(1, iterations + 1):
            agent_log.info(f"Iteration {i}: running `{command}`")
            run_log.log({"event": "run_start", "iteration": i, "command": command})

            result = run(command=command, cwd=project_folder, timeout=timeout, error_patterns=error_patterns)
            run_log.log({
                "event": "run_result",
                "iteration": i,
                "exit_code": result.exit_code,
                "stdout": result.stdout,
                "stderr": result.stderr,
            })

            if result.success:
                run_log.log({"event": "success", "iteration": i})
                agent_log.info(f"Success on iteration {i}")
                return True

            agent_log.info(f"Iteration {i} failed — requesting LLM fix")
            relevant_paths = extract_relevant_files(result.stderr + result.stdout, project_folder)
            relevant_files = {}
            for p in relevant_paths:
                try:
                    relevant_files[str(p.relative_to(project_folder))] = p.read_text(errors="replace")
                except Exception:
                    pass

            llm_response = llm.fix_code(
                project_info=project_info,
                command=command,
                stdout=result.stdout,
                stderr=result.stderr,
                relevant_files=relevant_files,
            )
            patches = parse_patches(llm_response)
            if patches:
                apply_patches(patches, project_folder)
                run_log.log({
                    "event": "fix_applied",
                    "iteration": i,
                    "files_changed": list(patches.keys()),
                    "llm_reasoning": llm_response[:500],
                })
                agent_log.info(f"Applied patches to: {list(patches.keys())}")
            else:
                agent_log.error(f"Iteration {i}: LLM returned no parseable patches")
                run_log.log({"event": "agent_error", "iteration": i, "reason": "LLM returned no parseable patches"})

        run_log.log({"event": "failure", "iteration": iterations, "reason": "max iterations reached"})
        agent_log.info(f"Failed after {iterations} iterations")
        return False
    finally:
        run_log.close()
        agent_log.close()


def main():
    parser = argparse.ArgumentParser(description="miniagent — auto code-fixing agent")
    parser.add_argument("project_folder", type=Path, help="Path to the project folder")
    parser.add_argument("--iterations", type=int, default=5, help="Max fix iterations (default: 5)")

    _default_config = Path(__file__).parent.parent / "agent_config.toml"
    if not _default_config.exists():
        _default_config = Path.cwd() / "agent_config.toml"

    parser.add_argument(
        "--config",
        type=Path,
        default=_default_config,
        help="Path to agent_config.toml",
    )
    args = parser.parse_args()

    config = _load_config(args.config)
    agent_log_dir = Path(__file__).parent.parent / "logs"
    if not agent_log_dir.parent.exists():
        agent_log_dir = Path.cwd() / "logs"
    success = run_agent(
        project_folder=args.project_folder.resolve(),
        iterations=args.iterations,
        config=config,
        agent_log_dir=agent_log_dir,
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
