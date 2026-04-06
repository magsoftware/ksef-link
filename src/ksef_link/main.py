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
    """Run the CLI entrypoint."""
    options = parse_arguments(argv)
    merged_environment = load_environment(options.runtime.env_file, environment)
    debug_enabled = options.runtime.debug or env_flag(merged_environment.get("KSEF_DEBUG"))
    configure_logging(debug_enabled)
    logger = get_logger()

    try:
        with build_application_context(options, merged_environment, logger) as context:
            result = execute_command(options, context)
    except KsefLinkError as error:
        logger.error("%s", error)
        _write_json(sys.stderr, _error_payload(error))
        return 1

    _write_json(sys.stdout, result)
    return 0


def entrypoint() -> None:
    """Console script entrypoint."""
    raise SystemExit(main())


def _write_json(stream: TextIO, payload: dict[str, Any]) -> None:
    stream.write(json.dumps(payload, indent=2, ensure_ascii=False))
    stream.write("\n")


def _error_payload(error: KsefLinkError) -> dict[str, Any]:
    if isinstance(error, KsefApiError):
        return error.to_payload()

    return {
        "error": str(error),
    }
