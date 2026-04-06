from __future__ import annotations

from pathlib import Path

from ksef_link.config import env_flag, load_environment


def test_load_environment_merges_dotenv_with_process_environment(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("KSEF_TOKEN=file-token\nKSEF_DEBUG=false\n", encoding="utf-8")

    loaded = load_environment(
        env_file,
        environment={
            "KSEF_DEBUG": "true",
            "KSEF_ACCESS_TOKEN": "env-token",
        },
    )

    assert loaded["KSEF_TOKEN"] == "file-token"
    assert loaded["KSEF_ACCESS_TOKEN"] == "env-token"
    assert loaded["KSEF_DEBUG"] == "true"


def test_env_flag_recognizes_truthy_values() -> None:
    assert env_flag("true") is True
    assert env_flag("1") is True
    assert env_flag("yes") is True
    assert env_flag("false") is False
    assert env_flag(None) is False
