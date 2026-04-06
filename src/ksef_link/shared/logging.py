"""Logging helpers for the ksef-link application."""

from __future__ import annotations

import logging

LOGGER_NAME = "ksef_link"


def get_logger() -> logging.Logger:
    """Return the shared application logger.

    Returns:
        Logger instance used by the application.
    """
    return logging.getLogger(LOGGER_NAME)


def configure_logging(debug: bool = False) -> None:
    """Configure application logging.

    Args:
        debug: Whether to enable verbose debug logging.
    """
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")
