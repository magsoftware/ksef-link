from __future__ import annotations

from datetime import datetime
from pathlib import Path
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
    CliOptions,
    InvoiceQueryResult,
    InvoicesCommandOptions,
    PublicKeyCertificate,
    RefreshCommandOptions,
    RuntimeOptions,
    StatusInfo,
    TokenInfo,
)
from ksef_link.workflows import (
    build_authorization_policy,
    build_invoice_filters,
    current_month_range_warsaw,
    execute_command,
    resolve_access_token,
    resolve_auth_context,
    run_authenticate_command,
    run_invoices_command,
    run_refresh_command,
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


class StubInvoiceService:
    def __init__(self) -> None:
        self.download_calls: list[Path] = []

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

    def download_invoices_to_directory(
        self,
        *,
        access_token: str,
        invoices: list[dict[str, Any]],
        output_dir: Path,
    ) -> list[dict[str, str | None]]:
        self.download_calls.append(output_dir)
        return [{"ksefNumber": "1", "path": str(output_dir / "1.xml"), "contentHash": "hash"}]


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


def test_build_authorization_policy_includes_all_ip_collections() -> None:
    command = AuthenticateCommandOptions(
        ksef_token="token",
        context_type="Nip",
        context_value="6771086988",
        poll_interval=1.0,
        wait_timeout=60.0,
        allowed_ipv4=("127.0.0.1",),
        allowed_ipv4_range=("10.0.0.1-10.0.0.2",),
        allowed_ipv4_mask=("172.16.0.0/16",),
    )

    policy = build_authorization_policy(command)

    assert policy == {
        "allowedIps": {
            "ip4Addresses": ["127.0.0.1"],
            "ip4Ranges": ["10.0.0.1-10.0.0.2"],
            "ip4Masks": ["172.16.0.0/16"],
        }
    }


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
    auth_service = StubAuthService()
    command = build_invoices_command()

    with pytest.raises(ConfigurationError):
        resolve_access_token(command, {}, auth_service)


def test_run_authenticate_command_uses_environment_token() -> None:
    auth_service = StubAuthService()
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

    result = run_authenticate_command(command, {"KSEF_TOKEN": "env-token"}, auth_service)  # type: ignore[arg-type]

    assert result["tokens"]["accessToken"]["token"] == "authenticated-access"


def test_run_authenticate_command_raises_when_token_missing() -> None:
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

    with pytest.raises(ConfigurationError):
        run_authenticate_command(command, {}, StubAuthService())  # type: ignore[arg-type]


def test_run_refresh_command_returns_access_token_payload() -> None:
    result = run_refresh_command(RefreshCommandOptions(refresh_token="refresh"), StubAuthService())  # type: ignore[arg-type]

    assert result["accessToken"]["token"] == "refreshed-access"


def test_run_invoices_command_includes_downloads_when_directory_is_set() -> None:
    auth_service = StubAuthService()
    invoice_service = StubInvoiceService()
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
        download_dir=Path("downloads"),
        poll_interval=1.0,
        wait_timeout=60.0,
    )

    result = run_invoices_command(command, {}, auth_service, invoice_service)  # type: ignore[arg-type]

    assert result["summary"]["count"] == 1
    assert result["downloads"][0]["contentHash"] == "hash"
    assert invoice_service.download_calls == [Path("downloads")]


def test_execute_command_routes_to_each_command_type() -> None:
    auth_service = StubAuthService()
    invoice_service = StubInvoiceService()
    runtime = RuntimeOptions(base_url="https://api.ksef.mf.gov.pl/v2", timeout=30.0, debug=False, env_file=Path(".env"))

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
        {},
        auth_service,  # type: ignore[arg-type]
        invoice_service,  # type: ignore[arg-type]
    )
    refresh_result = execute_command(
        CliOptions(runtime=runtime, command=RefreshCommandOptions(refresh_token="refresh")),
        {},
        auth_service,  # type: ignore[arg-type]
        invoice_service,  # type: ignore[arg-type]
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
        {},
        auth_service,  # type: ignore[arg-type]
        invoice_service,  # type: ignore[arg-type]
    )

    assert auth_result["tokens"]["refreshToken"]["token"] == "refresh"
    assert refresh_result["accessToken"]["token"] == "refreshed-access"
    assert invoices_result["summary"]["count"] == 1


def test_execute_command_raises_for_unsupported_command_type() -> None:
    runtime = RuntimeOptions(base_url="https://api.ksef.mf.gov.pl/v2", timeout=30.0, debug=False, env_file=Path(".env"))

    with pytest.raises(ConfigurationError):
        execute_command(
            CliOptions(runtime=runtime, command=object()),  # type: ignore[arg-type]
            {},
            StubAuthService(),  # type: ignore[arg-type]
            StubInvoiceService(),  # type: ignore[arg-type]
        )


def test_current_month_range_warsaw_uses_current_time_when_not_provided() -> None:
    start, end = current_month_range_warsaw()

    assert start.endswith("+02:00") or start.endswith("+01:00")
    assert end.endswith("+02:00") or end.endswith("+01:00")
