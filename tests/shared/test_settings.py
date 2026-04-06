from __future__ import annotations

from pathlib import Path

from ksef_link.shared.settings import env_flag, load_environment


def test_load_environment_reads_dotenv_and_merges_environment(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("A=1\nB=2\n", encoding="utf-8")

    result = load_environment(env_file, {"B": "override", "C": "3"})

    assert result == {"A": "1", "B": "override", "C": "3"}


def test_load_environment_ignores_missing_file() -> None:
    result = load_environment(Path("missing.env"), {"A": "1"})

    assert result == {"A": "1"}


def test_env_flag_interprets_truthy_and_falsy_values() -> None:
    assert env_flag("true") is True
    assert env_flag(" YES ") is True
    assert env_flag("0") is False
    assert env_flag(None) is False
