from __future__ import annotations

from pathlib import Path

import pytest

from ksef_link.application.commands import CliOptions, InvoicesCommandOptions, RuntimeOptions
from ksef_link.main import main
from ksef_link.shared.errors import KsefApiError, KsefLinkError


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
        lambda options, context: {"ok": True},
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
        lambda options, context: (_ for _ in ()).throw(
            KsefApiError("boom", status_code=403)
        ),
    )

    exit_code = main([])

    assert exit_code == 1
    assert '"statusCode": 403' in capsys.readouterr().err


def test_main_uses_env_debug_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    debug_values: list[bool] = []
    monkeypatch.setattr("ksef_link.main.parse_arguments", lambda argv=None: build_cli_options())
    monkeypatch.setattr("ksef_link.main.load_environment", lambda env_file, environment=None: {"KSEF_DEBUG": "true"})
    monkeypatch.setattr("ksef_link.main.configure_logging", lambda debug: debug_values.append(debug))
    monkeypatch.setattr(
        "ksef_link.main.execute_command",
        lambda options, context: {"ok": True},
    )

    exit_code = main([])

    assert exit_code == 0
    assert debug_values == [True]


def test_main_writes_generic_error_payload_for_non_api_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("ksef_link.main.parse_arguments", lambda argv=None: build_cli_options())
    monkeypatch.setattr("ksef_link.main.load_environment", lambda env_file, environment=None: {})
    monkeypatch.setattr(
        "ksef_link.main.execute_command",
        lambda options, context: (_ for _ in ()).throw(KsefLinkError("boom")),
    )

    exit_code = main([])

    assert exit_code == 1
    assert '"error": "boom"' in capsys.readouterr().err
