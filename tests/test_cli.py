from __future__ import annotations

from pathlib import Path

import pytest

from ksef_link.cli import parse_arguments
from ksef_link.models import AuthenticateCommandOptions, InvoicesCommandOptions, RefreshCommandOptions


def test_parse_invoices_arguments_uses_purchase_invoice_defaults() -> None:
    options = parse_arguments(["invoices"])

    assert isinstance(options.command, InvoicesCommandOptions)
    assert options.command.subject_type == "Subject2"
    assert options.command.date_type == "PermanentStorage"
    assert options.runtime.base_url == "https://api.ksef.mf.gov.pl/v2"
    assert options.runtime.env_file == Path(".env")


def test_parse_authenticate_arguments_collects_authorization_policy_inputs() -> None:
    options = parse_arguments(
        [
            "--debug",
            "authenticate",
            "--context-type",
            "Nip",
            "--context-value",
            "6771086988",
            "--allowed-ipv4",
            "203.0.113.10",
            "--allowed-ipv4-mask",
            "172.16.0.0/16",
        ]
    )

    assert isinstance(options.command, AuthenticateCommandOptions)
    assert options.runtime.debug is True
    assert options.command.allowed_ipv4 == ("203.0.113.10",)
    assert options.command.allowed_ipv4_mask == ("172.16.0.0/16",)


def test_parse_refresh_arguments() -> None:
    options = parse_arguments(["refresh", "--refresh-token", "refresh-token"])

    assert isinstance(options.command, RefreshCommandOptions)
    assert options.command.refresh_token == "refresh-token"


def test_parse_invoices_arguments_with_download_dir() -> None:
    options = parse_arguments(
        [
            "--env-file",
            "custom.env",
            "invoices",
            "--download-dir",
            "downloads",
            "--ksef-number",
            "ksef-number",
            "--invoice-number",
            "invoice-number",
            "--seller-nip",
            "1234567890",
            "--restrict-to-hwm",
        ]
    )

    assert isinstance(options.command, InvoicesCommandOptions)
    assert options.runtime.env_file == Path("custom.env")
    assert options.command.download_dir == Path("downloads")
    assert options.command.ksef_number == "ksef-number"
    assert options.command.restrict_to_hwm is True


def test_parse_arguments_requires_command() -> None:
    with pytest.raises(SystemExit):
        parse_arguments([])
