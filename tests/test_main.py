from __future__ import annotations

from pathlib import Path

import pytest

from ksef_link.errors import KsefApiError
from ksef_link.main import main
from ksef_link.models import CliOptions, InvoicesCommandOptions, RuntimeOptions


def build_cli_options() -> CliOptions:
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


def test_main_writes_success_payload_without_error_output(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("ksef_link.main.parse_arguments", lambda argv=None: build_cli_options())
    monkeypatch.setattr("ksef_link.main.load_environment", lambda env_file, environment=None: {})
    monkeypatch.setattr(
        "ksef_link.main.execute_command",
        lambda options, environment, auth_service, invoice_service: {"ok": True},
    )

    exit_code = main([])

    assert exit_code == 0
    assert '"ok": true' in capsys.readouterr().out


def test_main_writes_error_payload_for_application_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("ksef_link.main.parse_arguments", lambda argv=None: build_cli_options())
    monkeypatch.setattr("ksef_link.main.load_environment", lambda env_file, environment=None: {})
    monkeypatch.setattr(
        "ksef_link.main.execute_command",
        lambda options, environment, auth_service, invoice_service: (_ for _ in ()).throw(
            KsefApiError("boom", status_code=403)
        ),
    )

    exit_code = main([])

    assert exit_code == 1
    assert '"statusCode": 403' in capsys.readouterr().err
