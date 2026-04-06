from __future__ import annotations

import logging
from pathlib import Path

import pytest

from ksef_link.application.commands import CliOptions, InvoicesCommandOptions, RuntimeOptions
from ksef_link.bootstrap import build_application_context


def _build_cli_options() -> CliOptions:
    return CliOptions(
        runtime=RuntimeOptions(
            base_url="https://api.ksef.mf.gov.pl/v2",
            timeout=30.0,
            debug=False,
            env_file=Path(".env"),
        ),
        command=InvoicesCommandOptions(
            access_token="access",
            refresh_token=None,
            ksef_token=None,
            context_type=None,
            context_value=None,
            subject_type="Subject2",
            date_type="PermanentStorage",
            date_from="2026-04-01T00:00:00+02:00",
            date_to="2026-04-06T10:15:00+02:00",
            sort_order="Asc",
            page_size=250,
            restrict_to_hwm=False,
            ksef_number=None,
            invoice_number=None,
            seller_nip=None,
            download_dir=None,
            poll_interval=1.0,
            wait_timeout=60.0,
        ),
    )


def test_build_application_context_wires_adapters(monkeypatch: pytest.MonkeyPatch) -> None:
    created: dict[str, object] = {}

    class FakeHttpClient:
        def __init__(self, *, base_url: str, timeout: float, logger: logging.Logger) -> None:
            created["base_url"] = base_url
            created["timeout"] = timeout
            created["logger"] = logger

        def __enter__(self) -> object:
            created["entered"] = True
            return self

        def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
            created["exited"] = True

    class FakeAuthService:
        def __init__(self, http_client: object) -> None:
            created["auth_http_client"] = http_client

    class FakeInvoiceGateway:
        def __init__(self, http_client: object) -> None:
            created["invoice_http_client"] = http_client

    class FakeStorage:
        def __init__(self, logger: logging.Logger) -> None:
            created["storage_created"] = True
            created["storage_logger"] = logger

    monkeypatch.setattr("ksef_link.bootstrap.KsefHttpClient", FakeHttpClient)
    monkeypatch.setattr("ksef_link.bootstrap.KsefAuthService", FakeAuthService)
    monkeypatch.setattr("ksef_link.bootstrap.KsefInvoiceGateway", FakeInvoiceGateway)
    monkeypatch.setattr("ksef_link.bootstrap.FileInvoiceStorage", FakeStorage)

    logger = logging.getLogger("test")
    environment = {"KSEF_DEBUG": "true"}

    with build_application_context(_build_cli_options(), environment, logger) as context:
        assert context.environment == environment
        assert created["entered"] is True
        assert context.auth_port is not None
        assert context.invoice_port is not None
        assert context.invoice_storage is not None

    assert created["base_url"] == "https://api.ksef.mf.gov.pl/v2"
    assert created["timeout"] == 30.0
    assert created["logger"] is logger
    assert created["auth_http_client"] is created["invoice_http_client"]
    assert created["storage_created"] is True
    assert created["storage_logger"] is logger
    assert created["exited"] is True
