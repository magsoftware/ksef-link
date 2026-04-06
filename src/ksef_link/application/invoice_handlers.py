from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from ksef_link.application.commands import InvoicesCommandOptions
from ksef_link.ports.auth import AuthPort
from ksef_link.ports.invoices import InvoicePort
from ksef_link.ports.storage import InvoiceStoragePort
from ksef_link.shared.errors import ConfigurationError

WARSAW_TIMEZONE = ZoneInfo("Europe/Warsaw")


def handle_invoices_command(
    command: InvoicesCommandOptions,
    environment: Mapping[str, str],
    auth_port: AuthPort,
    invoice_port: InvoicePort,
    invoice_storage: InvoiceStoragePort,
) -> dict[str, Any]:
    """Run the invoices command use case."""
    access_token = resolve_access_token(command, environment, auth_port)
    filters = build_invoice_filters(command)
    query_result = invoice_port.query_all_invoice_metadata(
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
        result["downloads"] = [
            invoice_storage.save_invoice(
                download=invoice_port.download_invoice(access_token=access_token, ksef_number=invoice["ksefNumber"]),
                output_dir=command.download_dir,
            )
            for invoice in query_result.invoices
        ]

    return result


def resolve_access_token(
    command: InvoicesCommandOptions,
    environment: Mapping[str, str],
    auth_port: AuthPort,
) -> str:
    """Resolve access token from CLI args, refresh token or full authentication flow."""
    access_token = command.access_token or environment.get("KSEF_ACCESS_TOKEN") or environment.get("ACCESS_TOKEN")
    if access_token:
        return access_token

    refresh_token = command.refresh_token or environment.get("KSEF_REFRESH_TOKEN") or environment.get("REFRESH_TOKEN")
    if refresh_token:
        return auth_port.refresh_access_token(refresh_token=refresh_token).token

    ksef_token = command.ksef_token or environment.get("KSEF_TOKEN")
    if ksef_token:
        context_type, context_value = resolve_auth_context(command, environment)
        session = auth_port.authenticate_with_ksef_token(
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
    """Return ISO-8601 range from the start of the current Warsaw month until now."""
    current_time = now.astimezone(WARSAW_TIMEZONE) if now is not None else datetime.now(WARSAW_TIMEZONE)
    month_start = current_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return month_start.isoformat(), current_time.isoformat()
