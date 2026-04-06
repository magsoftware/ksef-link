from __future__ import annotations

import logging

import pytest

from ksef_link.shared.logging import LOGGER_NAME, configure_logging, get_logger


def test_get_logger_uses_project_logger_name() -> None:
    assert get_logger().name == LOGGER_NAME


def test_configure_logging_passes_expected_level(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[dict[str, object]] = []
    monkeypatch.setattr(
        "logging.basicConfig",
        lambda **kwargs: captured.append(kwargs),
    )

    configure_logging(debug=True)
    configure_logging(debug=False)

    assert captured[0]["level"] == logging.DEBUG
    assert captured[1]["level"] == logging.INFO
