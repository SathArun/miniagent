import os
import re
from pathlib import Path

_PATCH_RE = re.compile(r"<<<FILE:\s*(.+?)>>>\n(.*?)<<<END>>>", re.DOTALL)
_FILENAME_RE = re.compile(r'[\w./\\-]+\.\w+')


def parse_patches(response: str) -> dict[str, str]:
    return {m.group(1).strip(): m.group(2) for m in _PATCH_RE.finditer(response)}


def apply_patches(patches: dict[str, str], project_folder: Path) -> None:
    resolved_root = project_folder.resolve()
    for rel_path, content in patches.items():
        target = (project_folder / rel_path).resolve()
        if not str(target).startswith(str(resolved_root) + ("/" if "/" in str(resolved_root) else "\\")):
            raise ValueError(f"Patch path escapes project folder: {rel_path}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)


def extract_relevant_files(error_output: str, project_folder: Path) -> list[Path]:
    candidates = set(_FILENAME_RE.findall(error_output))
    found = []
    for name in candidates:
        path = project_folder / name
        if path.exists():
            found.append(path)
    return found


class LLMClient:
    def __init__(self, config: dict):
        self._provider = config["provider"]
        self._model = config["model"]
        api_key = os.environ[config["api_key_env"]]

        if self._provider == "anthropic":
            import anthropic
            self._client = anthropic.Anthropic(api_key=api_key)
        elif self._provider == "openai":
            import openai
            self._client = openai.OpenAI(api_key=api_key)
        else:
            raise ValueError(f"Unsupported LLM provider: {self._provider}")

    def generate_project_info(self, file_listing: str) -> str:
        prompt = (
            f"You are analyzing a code project. Here are its files:\n\n{file_listing}\n\n"
            "Write a concise project_info.md covering: runtime, entry point, and what the project does."
        )
        return self._chat(prompt)

    def fix_code(
        self,
        project_info: str,
        command: str,
        stdout: str,
        stderr: str,
        relevant_files: dict[str, str],
    ) -> str:
        files_block = "\n\n".join(
            f"=== {path} ===\n{content}" for path, content in relevant_files.items()
        )
        prompt = (
            f"Project info:\n{project_info}\n\n"
            f"Failed command: {command}\n\n"
            f"stdout:\n{stdout}\n\nstderr:\n{stderr}\n\n"
            f"Relevant files:\n{files_block}\n\n"
            "Fix the code. Return ONLY the fixed files using this format:\n"
            "<<<FILE: relative/path/to/file>>>\n<full file content>\n<<<END>>>"
        )
        return self._chat(prompt)

    def _chat(self, prompt: str) -> str:
        if self._provider == "anthropic":
            response = self._client.messages.create(
                model=self._model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        else:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.choices[0].message.content
