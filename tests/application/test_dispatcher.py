from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest

from ksef_link.adapters.filesystem.invoice_storage import FileInvoiceStorage
from ksef_link.application.commands import (
    AuthenticateCommandOptions,
    CliOptions,
    InvoicesCommandOptions,
    RefreshCommandOptions,
    RuntimeOptions,
)
from ksef_link.application.context import ApplicationContext
from ksef_link.application.dispatcher import execute_command
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
from ksef_link.domain.invoices import InvoiceDownload, InvoiceQueryResult
from ksef_link.shared.errors import ConfigurationError


class StubAuthService:
    def refresh_access_token(self, *, refresh_token: str) -> TokenInfo:
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
        filters: dict[str, Any],
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
        return InvoiceDownload(ksef_number=ksef_number, content=b"<xml>1</xml>", content_hash="hash")


def test_execute_command_routes_to_each_command_type() -> None:
    runtime = RuntimeOptions(base_url="https://api.ksef.mf.gov.pl/v2", timeout=30.0, debug=False, env_file=Path(".env"))
    context = ApplicationContext(
        environment={},
        auth_port=StubAuthService(),
        invoice_port=StubInvoiceService(),
        invoice_storage=FileInvoiceStorage(logging.getLogger("test")),
    )

    auth_result = execute_command(
        CliOptions(
            runtime=runtime,
            command=AuthenticateCommandOptions(
                ksef_token="token",
                context_type="Nip",
                context_value="6771086988",
                poll_interval=1.0,
                wait_timeout=60.0,
                allowed_ipv4=(),
                allowed_ipv4_range=(),
                allowed_ipv4_mask=(),
            ),
        ),
        context,
    )
    refresh_result = execute_command(
        CliOptions(runtime=runtime, command=RefreshCommandOptions(refresh_token="refresh")),
        context,
    )
    invoices_result = execute_command(
        CliOptions(
            runtime=runtime,
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
        ),
        context,
    )

    assert auth_result["tokens"]["refreshToken"]["token"] == "refresh"
    assert refresh_result["accessToken"]["token"] == "refreshed-access"
    assert invoices_result["summary"]["count"] == 1


def test_execute_command_raises_for_unsupported_command_type() -> None:
    runtime = RuntimeOptions(base_url="https://api.ksef.mf.gov.pl/v2", timeout=30.0, debug=False, env_file=Path(".env"))

    with pytest.raises(ConfigurationError):
        execute_command(
            CliOptions(runtime=runtime, command=object()),  # type: ignore[arg-type]
            ApplicationContext(
                environment={},
                auth_port=StubAuthService(),
                invoice_port=StubInvoiceService(),
                invoice_storage=FileInvoiceStorage(logging.getLogger("test")),
            ),
        )
