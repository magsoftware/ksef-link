from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import asdict
from datetime import datetime
from typing import Any, Protocol, cast
from zoneinfo import ZoneInfo

from ksef_link.auth import KsefAuthService
from ksef_link.errors import ConfigurationError
from ksef_link.invoices import KsefInvoiceService
from ksef_link.models import (
    AuthenticateCommandOptions,
    AuthenticatedSession,
    CliOptions,
    InvoicesCommandOptions,
    RefreshCommandOptions,
    TokenInfo,
)

WARSAW_TIMEZONE = ZoneInfo("Europe/Warsaw")


type CommandHandler = (
    Callable[
        [object, Mapping[str, str], KsefAuthService, KsefInvoiceService],
        dict[str, Any],
    ]
)


class AuthTokenResolver(Protocol):
    """Subset of authentication operations needed by workflows."""

    def refresh_access_token(self, *, refresh_token: str) -> TokenInfo:
        ...

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
        ...


def _dispatch_authenticate_command(
    command: object,
    environment: Mapping[str, str],
    auth_service: KsefAuthService,
    invoice_service: KsefInvoiceService,
) -> dict[str, Any]:
    del invoice_service
    return run_authenticate_command(cast(AuthenticateCommandOptions, command), environment, auth_service)


def _dispatch_refresh_command(
    command: object,
    environment: Mapping[str, str],
    auth_service: KsefAuthService,
    invoice_service: KsefInvoiceService,
) -> dict[str, Any]:
    del environment, invoice_service
    return run_refresh_command(cast(RefreshCommandOptions, command), auth_service)


def _dispatch_invoices_command(
    command: object,
    environment: Mapping[str, str],
    auth_service: KsefAuthService,
    invoice_service: KsefInvoiceService,
) -> dict[str, Any]:
    return run_invoices_command(cast(InvoicesCommandOptions, command), environment, auth_service, invoice_service)


COMMAND_HANDLERS: dict[type[object], CommandHandler] = {
    AuthenticateCommandOptions: _dispatch_authenticate_command,
    RefreshCommandOptions: _dispatch_refresh_command,
    InvoicesCommandOptions: _dispatch_invoices_command,
}


def execute_command(
    options: CliOptions,
    environment: Mapping[str, str],
    auth_service: KsefAuthService,
    invoice_service: KsefInvoiceService,
) -> dict[str, Any]:
    """Execute the selected CLI command."""
    command = options.command
    handler = COMMAND_HANDLERS.get(type(command))
    if handler is not None:
        return handler(command, environment, auth_service, invoice_service)

    raise ConfigurationError("Nieobsługiwany typ komendy.")


def run_authenticate_command(
    command: AuthenticateCommandOptions,
    environment: Mapping[str, str],
    auth_service: KsefAuthService,
) -> dict[str, Any]:
    """Run the authenticate CLI command."""
    ksef_token = command.ksef_token or environment.get("KSEF_TOKEN")
    if not ksef_token:
        raise ConfigurationError("Brakuje tokena KSeF. Podaj --ksef-token albo ustaw KSEF_TOKEN.")

    session = auth_service.authenticate_with_ksef_token(
        ksef_token=ksef_token,
        context_type=command.context_type,
        context_value=command.context_value,
        authorization_policy=build_authorization_policy(command),
        timeout_seconds=command.wait_timeout,
        poll_interval=command.poll_interval,
    )

    return {
        "challenge": {
            "challenge": session.challenge.challenge,
            "timestamp": session.challenge.timestamp,
            "timestampMs": session.challenge.timestamp_ms,
            "clientIp": session.challenge.client_ip,
        },
        "publicKeyCertificate": {
            "validFrom": session.certificate.valid_from,
            "validTo": session.certificate.valid_to,
            "usage": session.certificate.usage,
        },
        "authentication": {
            "referenceNumber": session.init_result.reference_number,
            "authenticationToken": asdict(session.init_result.authentication_token),
            "status": asdict(session.status.status),
        },
        "tokens": {
            "accessToken": asdict(session.tokens.access_token),
            "refreshToken": asdict(session.tokens.refresh_token),
        },
    }


def run_refresh_command(
    command: RefreshCommandOptions,
    auth_service: KsefAuthService,
) -> dict[str, Any]:
    """Run the refresh CLI command."""
    access_token = auth_service.refresh_access_token(refresh_token=command.refresh_token)
    return {
        "accessToken": asdict(access_token),
    }


def run_invoices_command(
    command: InvoicesCommandOptions,
    environment: Mapping[str, str],
    auth_service: KsefAuthService,
    invoice_service: KsefInvoiceService,
) -> dict[str, Any]:
    """Run the invoices CLI command."""
    access_token = resolve_access_token(command, environment, auth_service)
    filters = build_invoice_filters(command)
    query_result = invoice_service.query_all_invoice_metadata(
        access_token=access_token,
        filters=filters,
        sort_order=command.sort_order,
        page_size=command.page_size,
    )

    result: dict[str, Any] = {
        "filters": filters,
        "summary": {
            "count": len(query_result.invoices),
            "pagesFetched": query_result.pages_fetched,
            "hasMore": query_result.has_more,
            "isTruncated": query_result.is_truncated,
            "permanentStorageHwmDate": query_result.permanent_storage_hwm_date,
        },
        "invoices": query_result.invoices,
    }

    if command.download_dir is not None:
        result["downloads"] = invoice_service.download_invoices_to_directory(
            access_token=access_token,
            invoices=query_result.invoices,
            output_dir=command.download_dir,
        )

    return result


def build_authorization_policy(command: AuthenticateCommandOptions) -> dict[str, Any] | None:
    """Build KSeF authorization policy payload from CLI values."""
    allowed_ips: dict[str, list[str]] = {}
    if command.allowed_ipv4:
        allowed_ips["ip4Addresses"] = list(command.allowed_ipv4)
    if command.allowed_ipv4_range:
        allowed_ips["ip4Ranges"] = list(command.allowed_ipv4_range)
    if command.allowed_ipv4_mask:
        allowed_ips["ip4Masks"] = list(command.allowed_ipv4_mask)

    if not allowed_ips:
        return None

    return {
        "allowedIps": allowed_ips,
    }


def resolve_access_token(
    command: InvoicesCommandOptions,
    environment: Mapping[str, str],
    auth_service: AuthTokenResolver,
) -> str:
    """Resolve access token from CLI args, refresh token or full authentication flow."""
    access_token = command.access_token or environment.get("KSEF_ACCESS_TOKEN") or environment.get("ACCESS_TOKEN")
    if access_token:
        return access_token

    refresh_token = command.refresh_token or environment.get("KSEF_REFRESH_TOKEN") or environment.get("REFRESH_TOKEN")
    if refresh_token:
        return auth_service.refresh_access_token(refresh_token=refresh_token).token

    ksef_token = command.ksef_token or environment.get("KSEF_TOKEN")
    if ksef_token:
        context_type, context_value = resolve_auth_context(command, environment)
        session = auth_service.authenticate_with_ksef_token(
            ksef_token=ksef_token,
            context_type=context_type,
            context_value=context_value,
            timeout_seconds=command.wait_timeout,
            poll_interval=command.poll_interval,
        )
        return session.tokens.access_token.token

    raise ConfigurationError(
        "Brakuje danych do uwierzytelnienia. Podaj access token, refresh token albo token KSeF z contextem."
    )


def resolve_auth_context(
    command: InvoicesCommandOptions,
    environment: Mapping[str, str],
) -> tuple[str, str]:
    """Resolve KSeF context values from CLI args or environment."""
    context_type = command.context_type or environment.get("KSEF_CONTEXT_TYPE")
    context_value = command.context_value or environment.get("KSEF_CONTEXT_VALUE")
    if not context_type or not context_value:
        raise ConfigurationError(
            "Brakuje contextu KSeF. Podaj --context-type i --context-value albo ustaw "
            "KSEF_CONTEXT_TYPE i KSEF_CONTEXT_VALUE."
        )
    return context_type, context_value


def build_invoice_filters(command: InvoicesCommandOptions, now: datetime | None = None) -> dict[str, Any]:
    """Build KSeF invoice query filters."""
    date_from, date_to = current_month_range_warsaw(now)
    filters: dict[str, Any] = {
        "subjectType": command.subject_type,
        "dateRange": {
            "dateType": command.date_type,
            "from": command.date_from or date_from,
            "to": command.date_to or date_to,
        },
    }
    if command.date_type == "PermanentStorage" and command.restrict_to_hwm:
        filters["dateRange"]["restrictToPermanentStorageHwmDate"] = True
    if command.ksef_number:
        filters["ksefNumber"] = command.ksef_number
    if command.invoice_number:
        filters["invoiceNumber"] = command.invoice_number
    if command.seller_nip:
        filters["sellerNip"] = command.seller_nip
    return filters


def current_month_range_warsaw(now: datetime | None = None) -> tuple[str, str]:
    """Return first day of current month and current moment in Europe/Warsaw."""
    current_time = now.astimezone(WARSAW_TIMEZONE) if now is not None else datetime.now(WARSAW_TIMEZONE)
    start = current_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return start.isoformat(), current_time.isoformat()
