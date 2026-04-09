"""Helpers for loading dotenv files and environment flags."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from dotenv import dotenv_values


def _read_env_file(path: Path) -> dict[str, str]:
    """Read values from a dotenv file.

    Args:
        path: Dotenv file path.

    Returns:
        Mapping of keys to non-null string values.
    """
    if not path.exists():
        return {}

    loaded_values = dotenv_values(path)
    return {key: value for key, value in loaded_values.items() if value is not None}


def load_environment(env_file: Path, environment: Mapping[str, str] | None = None) -> dict[str, str]:
    """Load environment values from dotenv and process environment.

    Args:
        env_file: Path to the dotenv file.
        environment: Optional environment override used mainly by tests.

    Returns:
        Merged environment with OS values taking precedence over dotenv values.
    """
    merged_environment = _read_env_file(env_file)
    source_environment = dict(os.environ) if environment is None else dict(environment)
    merged_environment.update(source_environment)
    return merged_environment


def env_flag(value: str | None) -> bool:
    """Interpret common textual boolean values.

    Args:
        value: Raw string value from configuration.

    Returns:
        ``True`` when the value matches a common truthy token.
    """
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}
