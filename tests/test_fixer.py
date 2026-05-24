import re
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from miniagent.fixer import parse_patches, apply_patches, extract_relevant_files, LLMClient


def test_parse_patches_single_file():
    response = "<<<FILE: src/main.py>>>\nprint('fixed')\n<<<END>>>"
    patches = parse_patches(response)
    assert patches == {"src/main.py": "print('fixed')\n"}


def test_parse_patches_multiple_files():
    response = (
        "<<<FILE: a.py>>>\nline1\n<<<END>>>\n"
        "<<<FILE: b.py>>>\nline2\n<<<END>>>"
    )
    patches = parse_patches(response)
    assert patches == {"a.py": "line1\n", "b.py": "line2\n"}


def test_parse_patches_empty_response():
    patches = parse_patches("No patches here, just text.")
    assert patches == {}


def test_apply_patches_overwrites_file(tmp_path):
    (tmp_path / "main.py").write_text("old content")
    apply_patches({"main.py": "new content"}, project_folder=tmp_path)
    assert (tmp_path / "main.py").read_text() == "new content"


def test_apply_patches_creates_missing_file(tmp_path):
    apply_patches({"src/new.py": "content"}, project_folder=tmp_path)
    assert (tmp_path / "src" / "new.py").read_text() == "content"


def test_extract_relevant_files_from_traceback(tmp_path):
    (tmp_path / "main.py").write_text("")
    (tmp_path / "utils.py").write_text("")
    stderr = 'File "main.py", line 5, in <module>\n  File "utils.py", line 12'
    files = extract_relevant_files(stderr, project_folder=tmp_path)
    names = [f.name for f in files]
    assert "main.py" in names
    assert "utils.py" in names


def test_extract_relevant_files_skips_nonexistent(tmp_path):
    (tmp_path / "main.py").write_text("")
    stderr = 'File "main.py", line 5\nFile "ghost.py", line 1'
    files = extract_relevant_files(stderr, project_folder=tmp_path)
    names = [f.name for f in files]
    assert "ghost.py" not in names


def test_apply_patches_rejects_path_traversal(tmp_path):
    with pytest.raises(ValueError, match="escapes project folder"):
        apply_patches({"../evil.py": "bad content"}, project_folder=tmp_path)


def test_llm_client_anthropic_generate_project_info():
    config = {"provider": "anthropic", "model": "claude-sonnet-4-6", "api_key_env": "ANTHROPIC_API_KEY"}
    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
        with patch("anthropic.Anthropic") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.return_value = MagicMock(
                content=[MagicMock(text="Project summary here")]
            )
            client = LLMClient(config)
            result = client.generate_project_info(file_listing="main.py\nutils.py")
            assert "Project summary here" in result
            mock_client.messages.create.assert_called_once()


def test_llm_client_openai_fix_code():
    config = {"provider": "openai", "model": "gpt-4o", "api_key_env": "OPENAI_API_KEY"}
    with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
        with patch("openai.OpenAI") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_client.chat.completions.create.return_value = MagicMock(
                choices=[MagicMock(message=MagicMock(content="<<<FILE: main.py>>>\nfixed\n<<<END>>>"))]
            )
            client = LLMClient(config)
            result = client.fix_code(
                project_info="Python project",
                command="python main.py",
                stdout="",
                stderr="NameError",
                relevant_files={"main.py": "broken code"},
            )
            assert "<<<FILE:" in result
