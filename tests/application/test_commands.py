from __future__ import annotations

from pathlib import Path

from ksef_link.application.commands import CliOptions, RuntimeOptions


def test_runtime_and_cli_options_store_values() -> None:
    runtime = RuntimeOptions(base_url="https://api.ksef.mf.gov.pl/v2", timeout=30.0, debug=True, env_file=Path(".env"))
    cli_options = CliOptions(runtime=runtime, command="command")  # type: ignore[arg-type]

    assert cli_options.runtime.debug is True
