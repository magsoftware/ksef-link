from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from ksef_link.adapters.filesystem.invoice_storage import FileInvoiceStorage
from ksef_link.application.commands import InvoicesCommandOptions
from ksef_link.application.invoice_handlers import (
    build_invoice_filters,
    current_month_range_warsaw,
    handle_invoices_command,
    resolve_access_token,
    resolve_auth_context,
)
from ksef_link.domain.auth import (
    AuthChallenge,
    AuthenticatedSession,
    AuthenticationMethodInfo,
    AuthInitResult,
    AuthStatus,
    AuthTokens,
    PublicKeyCertificate,
    StatusInfo,
    TokenInfo,
)
from ksef_link.domain.invoices import InvoiceDownload, InvoiceQueryFilters, InvoiceQueryResult
from ksef_link.shared.errors import ConfigurationError


class StubAuthService:
    def __init__(self) -> None:
        self.refresh_calls: list[str] = []
        self.auth_calls: list[tuple[str, str, str]] = []

    def refresh_access_token(self, *, refresh_token: str) -> TokenInfo:
        self.refresh_calls.append(refresh_token)
        return TokenInfo(token="refreshed-access", valid_until="2026-04-06T12:00:00+02:00")

    def authenticate_with_ksef_token(
        self,
        *,
        ksef_token: str,
        context_type: str,
        context_value: str,
        authorization_policy: dict[str, Any] | None = None,
        timeout_seconds: float,
        poll_interval: float,
    ) -> AuthenticatedSession:
        self.auth_calls.append((ksef_token, context_type, context_value))
        return AuthenticatedSession(
            challenge=AuthChallenge(
                challenge="challenge",
                timestamp="2026-04-06T00:00:00+02:00",
                timestamp_ms=1,
                client_ip="127.0.0.1",
            ),
            certificate=PublicKeyCertificate(
                certificate="certificate",
                valid_from="2026-04-01T00:00:00+02:00",
                valid_to="2027-04-01T00:00:00+02:00",
                usage=["KsefTokenEncryption"],
            ),
            init_result=AuthInitResult(
                reference_number="reference",
                authentication_token=TokenInfo(token="auth-token", valid_until="2026-04-06T12:00:00+02:00"),
            ),
            status=AuthStatus(
                start_date="2026-04-06T00:00:00+02:00",
                authentication_method="Token",
                authentication_method_info=AuthenticationMethodInfo(
                    category="Token",
                    code="token.ksef",
                    display_name="Token KSeF",
                ),
                status=StatusInfo(code=200, description="ok"),
            ),
            tokens=AuthTokens(
                access_token=TokenInfo(token="authenticated-access", valid_until="2026-04-06T12:00:00+02:00"),
                refresh_token=TokenInfo(token="refresh", valid_until="2026-04-06T12:00:00+02:00"),
            ),
        )


class StubInvoiceService:
    def query_all_invoice_metadata(
        self,
        *,
        access_token: str,
        filters: InvoiceQueryFilters,
        sort_order: str,
        page_size: int,
    ) -> InvoiceQueryResult:
        return InvoiceQueryResult(
            has_more=False,
            is_truncated=False,
            permanent_storage_hwm_date="hwm",
            pages_fetched=1,
            invoices=[{"ksefNumber": "1"}],
        )

    def download_invoice(self, *, access_token: str, ksef_number: str) -> InvoiceDownload:
        return InvoiceDownload(ksef_number=ksef_number, content_hash="hash", content=b"<xml>1</xml>")


def build_invoices_command() -> InvoicesCommandOptions:
    return InvoicesCommandOptions(
        access_token=None,
        refresh_token=None,
        ksef_token=None,
        context_type=None,
        context_value=None,
        subject_type="Subject2",
        date_type="PermanentStorage",
        date_from=None,
        date_to=None,
        sort_order="Asc",
        page_size=250,
        restrict_to_hwm=False,
        ksef_number=None,
        invoice_number=None,
        seller_nip=None,
        download_dir=None,
        poll_interval=1.0,
        wait_timeout=60.0,
    )


def test_build_invoice_filters_uses_current_month_in_warsaw_timezone() -> None:
    command = build_invoices_command()

    filters = build_invoice_filters(command, now=datetime.fromisoformat("2026-04-06T10:15:00+02:00"))

    assert filters["subjectType"] == "Subject2"
    assert filters["dateRange"]["from"] == "2026-04-01T00:00:00+02:00"
    assert filters["dateRange"]["to"] == "2026-04-06T10:15:00+02:00"


def test_build_invoice_filters_respects_optional_filters() -> None:
    command = InvoicesCommandOptions(
        access_token=None,
        refresh_token=None,
        ksef_token=None,
        context_type=None,
        context_value=None,
        subject_type="Subject1",
        date_type="PermanentStorage",
        date_from="2026-04-01T00:00:00+02:00",
        date_to="2026-04-06T10:15:00+02:00",
        sort_order="Asc",
        page_size=250,
        restrict_to_hwm=True,
        ksef_number="ksef",
        invoice_number="invoice",
        seller_nip="1234567890",
        download_dir=Path("downloads"),
        poll_interval=1.0,
        wait_timeout=60.0,
    )

    filters = build_invoice_filters(command)

    assert filters["dateRange"]["restrictToPermanentStorageHwmDate"] is True
    assert filters["ksefNumber"] == "ksef"
    assert filters["invoiceNumber"] == "invoice"
    assert filters["sellerNip"] == "1234567890"


def test_resolve_access_token_prefers_existing_access_token() -> None:
    auth_service = StubAuthService()

    token = resolve_access_token(build_invoices_command(), {"KSEF_ACCESS_TOKEN": "existing-access"}, auth_service)

    assert token == "existing-access"
    assert auth_service.refresh_calls == []
    assert auth_service.auth_calls == []


def test_resolve_access_token_uses_refresh_token_when_access_token_is_missing() -> None:
    auth_service = StubAuthService()

    token = resolve_access_token(build_invoices_command(), {"KSEF_REFRESH_TOKEN": "refresh-token"}, auth_service)

    assert token == "refreshed-access"
    assert auth_service.refresh_calls == ["refresh-token"]


def test_resolve_access_token_ignores_legacy_environment_aliases() -> None:
    with pytest.raises(ConfigurationError):
        resolve_access_token(
            build_invoices_command(),
            {
                "ACCESS_TOKEN": "legacy-access",
                "REFRESH_TOKEN": "legacy-refresh",
            },
            StubAuthService(),
        )


def test_resolve_access_token_runs_full_authentication_flow_when_needed() -> None:
    auth_service = StubAuthService()

    token = resolve_access_token(
        build_invoices_command(),
        {
            "KSEF_TOKEN": "ksef-token",
            "KSEF_CONTEXT_TYPE": "Nip",
            "KSEF_CONTEXT_VALUE": "6771086988",
        },
        auth_service,
    )

    assert token == "authenticated-access"
    assert auth_service.auth_calls == [("ksef-token", "Nip", "6771086988")]


def test_resolve_auth_context_prefers_command_values() -> None:
    command = InvoicesCommandOptions(
        access_token=None,
        refresh_token=None,
        ksef_token=None,
        context_type="InternalId",
        context_value="context-value",
        subject_type="Subject2",
        date_type="PermanentStorage",
        date_from=None,
        date_to=None,
        sort_order="Asc",
        page_size=250,
        restrict_to_hwm=False,
        ksef_number=None,
        invoice_number=None,
        seller_nip=None,
        download_dir=None,
        poll_interval=1.0,
        wait_timeout=60.0,
    )

    context_type, context_value = resolve_auth_context(command, {"KSEF_CONTEXT_TYPE": "Nip"})

    assert context_type == "InternalId"
    assert context_value == "context-value"


def test_resolve_auth_context_raises_when_missing() -> None:
    with pytest.raises(ConfigurationError):
        resolve_auth_context(build_invoices_command(), {})


def test_resolve_access_token_raises_when_no_authentication_input_is_available() -> None:
    with pytest.raises(ConfigurationError):
        resolve_access_token(build_invoices_command(), {}, StubAuthService())


def test_handle_invoices_command_includes_downloads_when_directory_is_set(tmp_path: Path) -> None:
    command = InvoicesCommandOptions(
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
        download_dir=tmp_path,
        poll_interval=1.0,
        wait_timeout=60.0,
    )

    result = handle_invoices_command(
        command,
        {},
        StubAuthService(),
        StubInvoiceService(),
        FileInvoiceStorage(logging.getLogger("test")),
    )

    assert result["summary"]["count"] == 1
    assert result["downloads"][0]["contentHash"] == "hash"
    assert (tmp_path / "1.xml").read_text(encoding="utf-8") == "<xml>1</xml>"


def test_current_month_range_warsaw_uses_current_time_when_not_provided() -> None:
    start, end = current_month_range_warsaw()

    assert start.endswith("+02:00") or start.endswith("+01:00")
    assert end.endswith("+02:00") or end.endswith("+01:00")
