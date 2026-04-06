from __future__ import annotations

from pathlib import Path

from ksef_link.cli import parse_arguments
from ksef_link.models import AuthenticateCommandOptions, InvoicesCommandOptions


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
