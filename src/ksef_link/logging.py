from __future__ import annotations

import logging

LOGGER_NAME = "ksef_link"


def get_logger() -> logging.Logger:
    """Return the application logger."""
    return logging.getLogger(LOGGER_NAME)


def configure_logging(debug: bool = False) -> None:
    """Configure application logging."""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")
