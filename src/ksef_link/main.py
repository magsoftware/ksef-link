"""Main CLI entrypoint for the ksef-link application."""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping, Sequence
from typing import Any, TextIO

from ksef_link.adapters.cli.parser import parse_arguments
from ksef_link.application.dispatcher import execute_command
from ksef_link.bootstrap import build_application_context
from ksef_link.shared.errors import KsefApiError, KsefLinkError
from ksef_link.shared.logging import configure_logging, get_logger
from ksef_link.shared.settings import env_flag, load_environment


def main(argv: Sequence[str] | None = None, environment: Mapping[str, str] | None = None) -> int:
    """Run the CLI entrypoint.

    Args:
        argv: Optional list of CLI arguments.
        environment: Optional environment override used mainly by tests.

    Returns:
        Process exit code.
    """
    options = parse_arguments(argv)
    merged_environment = load_environment(options.runtime.env_file, environment)
    debug_enabled = options.runtime.debug or env_flag(merged_environment.get("KSEF_DEBUG"))
    configure_logging(debug_enabled)
    logger = get_logger()

    try:
        with build_application_context(options, merged_environment, logger) as context:
            result = execute_command(options, context)
    except KsefLinkError as error:
        if isinstance(error, KsefApiError):
            logger.error("%s | diagnostics=%s", error, error.to_log_payload())
        else:
            logger.error("%s", error)
        _write_json(sys.stderr, _error_payload(error))
        return 1

    _write_json(sys.stdout, result)
    return 0


def entrypoint() -> None:
    """Raise ``SystemExit`` with the CLI exit code."""
    raise SystemExit(main())


def _write_json(stream: TextIO, payload: dict[str, Any]) -> None:
    """Write a JSON payload followed by a trailing newline.

    Args:
        stream: Target text stream.
        payload: JSON-serializable payload to write.
    """
    stream.write(json.dumps(payload, indent=2, ensure_ascii=False))
    stream.write("\n")


def _error_payload(error: KsefLinkError) -> dict[str, Any]:
    """Convert an application error into the stderr payload.

    Args:
        error: Application error raised during command execution.

    Returns:
        Safe, user-facing error payload.
    """
    if isinstance(error, KsefApiError):
        return error.to_payload()

    return {
        "error": str(error),
    }
