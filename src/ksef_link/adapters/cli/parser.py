from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from ksef_link.application.commands import (
    AuthenticateCommandOptions,
    CliOptions,
    InvoicesCommandOptions,
    RefreshCommandOptions,
    RuntimeOptions,
)

DEFAULT_BASE_URL = "https://api.ksef.mf.gov.pl/v2"
DEFAULT_INVOICE_DATE_TYPE = "PermanentStorage"
DEFAULT_INVOICE_SUBJECT_TYPE = "Subject2"
DEFAULT_INVOICE_SORT_ORDER = "Asc"
DEFAULT_INVOICE_PAGE_SIZE = 250


def build_parser() -> argparse.ArgumentParser:
    """Build the application CLI parser."""
    parser = argparse.ArgumentParser(
        description="CLI for KSeF authentication and invoice operations.",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"Adres bazowy API KSeF. Domyślnie: {DEFAULT_BASE_URL}",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Timeout pojedynczego requestu HTTP w sekundach.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Włącza logowanie requestów i odpowiedzi HTTP z maskowaniem danych wrażliwych.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(".env"),
        help="Ścieżka do pliku .env. Domyślnie: ./.env",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    authenticate_parser = subparsers.add_parser(
        "authenticate",
        help="Pełny przepływ uwierzytelnienia tokenem KSeF.",
    )
    authenticate_parser.add_argument("--ksef-token", help="Token KSeF.")
    authenticate_parser.add_argument(
        "--context-type",
        required=True,
        choices=["Nip", "InternalId", "NipVatUe", "PeppolId"],
        help="Typ contextIdentifier.type.",
    )
    authenticate_parser.add_argument(
        "--context-value",
        required=True,
        help="Wartość contextIdentifier.value.",
    )
    authenticate_parser.add_argument(
        "--poll-interval",
        type=float,
        default=1.0,
        help="Co ile sekund odpytywać status uwierzytelnienia.",
    )
    authenticate_parser.add_argument(
        "--wait-timeout",
        type=float,
        default=60.0,
        help="Maksymalny czas oczekiwania na status 200.",
    )
    authenticate_parser.add_argument(
        "--allowed-ipv4",
        action="append",
        default=[],
        help="Dozwolony adres IPv4 dla authorizationPolicy.allowedIps.ip4Addresses.",
    )
    authenticate_parser.add_argument(
        "--allowed-ipv4-range",
        action="append",
        default=[],
        help="Dozwolony zakres IPv4 dla authorizationPolicy.allowedIps.ip4Ranges.",
    )
    authenticate_parser.add_argument(
        "--allowed-ipv4-mask",
        action="append",
        default=[],
        help="Dozwolona maska CIDR dla authorizationPolicy.allowedIps.ip4Masks.",
    )

    refresh_parser = subparsers.add_parser(
        "refresh",
        help="Odświeża access token na podstawie refresh tokena.",
    )
    refresh_parser.add_argument("--refresh-token", required=True, help="Refresh token.")

    invoices_parser = subparsers.add_parser(
        "invoices",
        help="Pobiera metadane faktur, domyślnie zakupowych od początku bieżącego miesiąca.",
    )
    invoices_parser.add_argument("--access-token", help="Access token JWT.")
    invoices_parser.add_argument("--refresh-token", help="Refresh token JWT.")
    invoices_parser.add_argument(
        "--ksef-token",
        help="Token KSeF używany jako fallback do uzyskania access tokena.",
    )
    invoices_parser.add_argument(
        "--context-type",
        choices=["Nip", "InternalId", "NipVatUe", "PeppolId"],
        help="Typ contextIdentifier.type przy fallbackowym uwierzytelnieniu tokenem KSeF.",
    )
    invoices_parser.add_argument(
        "--context-value",
        help="Wartość contextIdentifier.value przy fallbackowym uwierzytelnieniu tokenem KSeF.",
    )
    invoices_parser.add_argument(
        "--subject-type",
        default=DEFAULT_INVOICE_SUBJECT_TYPE,
        choices=["Subject1", "Subject2", "Subject3", "SubjectAuthorized"],
        help="Typ podmiotu do wyszukiwania faktur. Domyślnie Subject2.",
    )
    invoices_parser.add_argument(
        "--date-type",
        default=DEFAULT_INVOICE_DATE_TYPE,
        choices=["Issue", "Invoicing", "PermanentStorage"],
        help="Typ daty używany do filtrowania. Domyślnie PermanentStorage.",
    )
    invoices_parser.add_argument(
        "--date-from",
        help="Początek zakresu w ISO-8601. Domyślnie pierwszy dzień bieżącego miesiąca w strefie Europe/Warsaw.",
    )
    invoices_parser.add_argument(
        "--date-to",
        help="Koniec zakresu w ISO-8601. Domyślnie bieżąca data i czas w strefie Europe/Warsaw.",
    )
    invoices_parser.add_argument(
        "--sort-order",
        default=DEFAULT_INVOICE_SORT_ORDER,
        choices=["Asc", "Desc"],
        help="Kolejność sortowania wyników. Domyślnie Asc.",
    )
    invoices_parser.add_argument(
        "--page-size",
        type=int,
        default=DEFAULT_INVOICE_PAGE_SIZE,
        help="Rozmiar strony wyników dla zapytań do metadanych. Domyślnie 250.",
    )
    invoices_parser.add_argument(
        "--restrict-to-hwm",
        action="store_true",
        help="Dla dateType=PermanentStorage ogranicza zakres do permanentStorageHwmDate.",
    )
    invoices_parser.add_argument("--ksef-number", help="Filtr exact match po numerze KSeF.")
    invoices_parser.add_argument("--invoice-number", help="Filtr exact match po numerze faktury.")
    invoices_parser.add_argument("--seller-nip", help="Filtr exact match po NIP sprzedawcy.")
    invoices_parser.add_argument(
        "--download-dir",
        type=Path,
        help="Jeżeli podasz katalog, skrypt pobierze XML każdej znalezionej faktury do tego katalogu.",
    )
    invoices_parser.add_argument(
        "--poll-interval",
        type=float,
        default=1.0,
        help="Interwał używany, gdy trzeba uzyskać access token przez uwierzytelnienie tokenem KSeF.",
    )
    invoices_parser.add_argument(
        "--wait-timeout",
        type=float,
        default=60.0,
        help="Timeout używany, gdy trzeba uzyskać access token przez uwierzytelnienie tokenem KSeF.",
    )

    return parser


def parse_arguments(argv: Sequence[str] | None = None) -> CliOptions:
    """Parse CLI arguments into typed command options."""
    parser = build_parser()
    namespace = parser.parse_args(list(argv) if argv is not None else None)

    runtime = RuntimeOptions(
        base_url=namespace.base_url,
        timeout=namespace.timeout,
        debug=namespace.debug,
        env_file=namespace.env_file.expanduser(),
    )

    command: AuthenticateCommandOptions | RefreshCommandOptions | InvoicesCommandOptions
    if namespace.command == "authenticate":
        command = AuthenticateCommandOptions(
            ksef_token=namespace.ksef_token,
            context_type=namespace.context_type,
            context_value=namespace.context_value,
            poll_interval=namespace.poll_interval,
            wait_timeout=namespace.wait_timeout,
            allowed_ipv4=tuple(namespace.allowed_ipv4),
            allowed_ipv4_range=tuple(namespace.allowed_ipv4_range),
            allowed_ipv4_mask=tuple(namespace.allowed_ipv4_mask),
        )
    elif namespace.command == "refresh":
        command = RefreshCommandOptions(refresh_token=namespace.refresh_token)
    else:
        command = InvoicesCommandOptions(
            access_token=namespace.access_token,
            refresh_token=namespace.refresh_token,
            ksef_token=namespace.ksef_token,
            context_type=namespace.context_type,
            context_value=namespace.context_value,
            subject_type=namespace.subject_type,
            date_type=namespace.date_type,
            date_from=namespace.date_from,
            date_to=namespace.date_to,
            sort_order=namespace.sort_order,
            page_size=namespace.page_size,
            restrict_to_hwm=namespace.restrict_to_hwm,
            ksef_number=namespace.ksef_number,
            invoice_number=namespace.invoice_number,
            seller_nip=namespace.seller_nip,
            download_dir=namespace.download_dir.expanduser() if namespace.download_dir is not None else None,
            poll_interval=namespace.poll_interval,
            wait_timeout=namespace.wait_timeout,
        )

    return CliOptions(runtime=runtime, command=command)
