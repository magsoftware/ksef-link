from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest

from ksef_link.errors import ConfigurationError
from ksef_link.models import (
    AuthChallenge,
    AuthenticateCommandOptions,
    AuthenticatedSession,
    AuthenticationMethodInfo,
    AuthInitResult,
    AuthStatus,
    AuthTokens,
    InvoicesCommandOptions,
    PublicKeyCertificate,
    StatusInfo,
    TokenInfo,
)
from ksef_link.workflows import (
    build_authorization_policy,
    build_invoice_filters,
    resolve_access_token,
)


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


def test_build_authorization_policy_returns_none_when_not_configured() -> None:
    command = AuthenticateCommandOptions(
        ksef_token=None,
        context_type="Nip",
        context_value="6771086988",
        poll_interval=1.0,
        wait_timeout=60.0,
        allowed_ipv4=(),
        allowed_ipv4_range=(),
        allowed_ipv4_mask=(),
    )

    assert build_authorization_policy(command) is None


def test_build_invoice_filters_uses_current_month_in_warsaw_timezone() -> None:
    command = build_invoices_command()

    filters = build_invoice_filters(command, now=datetime.fromisoformat("2026-04-06T10:15:00+02:00"))

    assert filters["subjectType"] == "Subject2"
    assert filters["dateRange"]["from"] == "2026-04-01T00:00:00+02:00"
    assert filters["dateRange"]["to"] == "2026-04-06T10:15:00+02:00"


def test_resolve_access_token_prefers_existing_access_token() -> None:
    auth_service = StubAuthService()
    command = build_invoices_command()

    token = resolve_access_token(
        command,
        {
            "KSEF_ACCESS_TOKEN": "existing-access",
        },
        auth_service,
    )

    assert token == "existing-access"
    assert auth_service.refresh_calls == []
    assert auth_service.auth_calls == []


def test_resolve_access_token_uses_refresh_token_when_access_token_is_missing() -> None:
    auth_service = StubAuthService()
    command = build_invoices_command()

    token = resolve_access_token(
        command,
        {
            "KSEF_REFRESH_TOKEN": "refresh-token",
        },
        auth_service,
    )

    assert token == "refreshed-access"
    assert auth_service.refresh_calls == ["refresh-token"]


def test_resolve_access_token_runs_full_authentication_flow_when_needed() -> None:
    auth_service = StubAuthService()
    command = build_invoices_command()

    token = resolve_access_token(
        command,
        {
            "KSEF_TOKEN": "ksef-token",
            "KSEF_CONTEXT_TYPE": "Nip",
            "KSEF_CONTEXT_VALUE": "6771086988",
        },
        auth_service,
    )

    assert token == "authenticated-access"
    assert auth_service.auth_calls == [("ksef-token", "Nip", "6771086988")]


def test_resolve_access_token_raises_when_no_authentication_input_is_available() -> None:
    auth_service = StubAuthService()
    command = build_invoices_command()

    with pytest.raises(ConfigurationError):
        resolve_access_token(command, {}, auth_service)
