"""Application handlers for invoice-related CLI commands."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from ksef_link.application.commands import InvoicesCommandOptions
from ksef_link.application.invoice_serializers import serialize_invoice_query_result
from ksef_link.domain.invoices import InvoiceDateRangeFilter, InvoiceQueryFilters
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
    """Run the ``invoices`` command use case.

    Args:
        command: Typed CLI command options.
        environment: Environment variables merged from the OS and dotenv file.
        auth_port: Authentication port used to resolve access tokens.
        invoice_port: Invoice port used to query and download invoices.
        invoice_storage: Storage port used to persist downloaded XML files.

    Returns:
        User-facing payload with invoice metadata and optional download details.
    """
    access_token = resolve_access_token(command, environment, auth_port)
    filters = build_invoice_filters(command)
    query_result = invoice_port.query_all_invoice_metadata(
        access_token=access_token,
        filters=filters,
        sort_order=command.sort_order,
        page_size=command.page_size,
    )

    if command.download_dir is not None:
        downloads = [
            invoice_storage.save_invoice(
                download=invoice_port.download_invoice(access_token=access_token, ksef_number=invoice["ksefNumber"]),
                output_dir=command.download_dir,
            )
            for invoice in query_result.invoices
        ]
        return serialize_invoice_query_result(filters=filters, query_result=query_result, downloads=downloads)

    return serialize_invoice_query_result(filters=filters, query_result=query_result)


def resolve_access_token(
    command: InvoicesCommandOptions,
    environment: Mapping[str, str],
    auth_port: AuthPort,
) -> str:
    """Resolve an access token for invoice operations.

    Args:
        command: Typed CLI command options.
        environment: Environment variables merged from the OS and dotenv file.
        auth_port: Authentication port used for refresh or full auth fallback.

    Returns:
        Access token used for invoice API calls.

    Raises:
        ConfigurationError: If no access path can be resolved.
    """
    access_token = command.access_token or environment.get("KSEF_ACCESS_TOKEN")
    if access_token:
        return access_token

    refresh_token = command.refresh_token or environment.get("KSEF_REFRESH_TOKEN")
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
    """Resolve KSeF context values from CLI args or environment.

    Args:
        command: Typed CLI command options.
        environment: Environment variables merged from the OS and dotenv file.

    Returns:
        Tuple of ``(context_type, context_value)``.

    Raises:
        ConfigurationError: If context values are missing.
    """
    context_type = command.context_type or environment.get("KSEF_CONTEXT_TYPE")
    context_value = command.context_value or environment.get("KSEF_CONTEXT_VALUE")
    if not context_type or not context_value:
        raise ConfigurationError(
            "Brakuje contextu KSeF. Podaj --context-type i --context-value albo ustaw "
            "KSEF_CONTEXT_TYPE i KSEF_CONTEXT_VALUE."
        )
    return context_type, context_value


def build_invoice_filters(command: InvoicesCommandOptions, now: datetime | None = None) -> InvoiceQueryFilters:
    """Build typed KSeF invoice query filters.

    Args:
        command: Typed CLI command options.
        now: Optional current time override used mainly by tests.

    Returns:
        Typed filter payload ready to be sent to the KSeF invoice API.
    """
    date_from, date_to = current_month_range_warsaw(now)
    date_range: InvoiceDateRangeFilter = {
        "dateType": command.date_type,
        "from": command.date_from or date_from,
        "to": command.date_to or date_to,
        "restrictToPermanentStorageHwmDate": (
            command.date_type == "PermanentStorage" and command.restrict_to_hwm
        ),
    }
    filters: InvoiceQueryFilters = {
        "subjectType": command.subject_type,
        "dateRange": date_range,
    }
    if command.ksef_number is not None:
        filters["ksefNumber"] = command.ksef_number
    if command.invoice_number is not None:
        filters["invoiceNumber"] = command.invoice_number
    if command.seller_nip is not None:
        filters["sellerNip"] = command.seller_nip
    return filters


def current_month_range_warsaw(now: datetime | None = None) -> tuple[str, str]:
    """Return the default invoice date range for the current Warsaw month.

    Args:
        now: Optional current time override used mainly by tests.

    Returns:
        Tuple of ISO-8601 timestamps from the first day of the month until now.
    """
    current_time = now.astimezone(WARSAW_TIMEZONE) if now is not None else datetime.now(WARSAW_TIMEZONE)
    month_start = current_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return month_start.isoformat(), current_time.isoformat()
