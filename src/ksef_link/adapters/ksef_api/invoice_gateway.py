from __future__ import annotations

from copy import deepcopy
from typing import Any
from urllib.parse import quote, urlencode

from ksef_link.adapters.ksef_api.http_client import KsefHttpClient
from ksef_link.domain.invoices import InvoiceDownload, InvoiceQueryResult
from ksef_link.shared.errors import KsefApiError

INVOICE_DATE_FIELDS = {
    "Issue": "issueDate",
    "Invoicing": "invoicingDate",
    "PermanentStorage": "permanentStorageDate",
}


class KsefInvoiceGateway:
    """KSeF invoice gateway adapter."""

    def __init__(self, http_client: KsefHttpClient) -> None:
        self._http_client = http_client

    def query_invoice_metadata(
        self,
        *,
        access_token: str,
        filters: dict[str, Any],
        sort_order: str,
        page_offset: int,
        page_size: int,
    ) -> dict[str, Any]:
        query = urlencode(
            {
                "sortOrder": sort_order,
                "pageOffset": page_offset,
                "pageSize": page_size,
            }
        )
        payload = self._http_client.request_json(
            "POST",
            f"/invoices/query/metadata?{query}",
            bearer_token=access_token,
            json_body=filters,
        )
        if not isinstance(payload, dict):
            raise KsefApiError("KSeF zwrócił nieprawidłowy format odpowiedzi dla listy metadanych faktur.")
        return payload

    def query_all_invoice_metadata(
        self,
        *,
        access_token: str,
        filters: dict[str, Any],
        sort_order: str,
        page_size: int,
    ) -> InvoiceQueryResult:
        effective_filters = deepcopy(filters)
        page_offset = 0
        pages_fetched = 0
        has_any_truncation = False
        permanent_storage_hwm_date: str | None = None
        invoices: list[dict[str, Any]] = []
        seen_ksef_numbers: set[str] = set()

        while True:
            response = self.query_invoice_metadata(
                access_token=access_token,
                filters=effective_filters,
                sort_order=sort_order,
                page_offset=page_offset,
                page_size=page_size,
            )
            pages_fetched += 1
            if permanent_storage_hwm_date is None:
                permanent_storage_hwm_date = response.get("permanentStorageHwmDate")

            response_invoices = response["invoices"]
            for invoice in response_invoices:
                ksef_number = invoice["ksefNumber"]
                if ksef_number in seen_ksef_numbers:
                    continue
                seen_ksef_numbers.add(ksef_number)
                invoices.append(invoice)

            if not response["hasMore"]:
                return InvoiceQueryResult(
                    has_more=False,
                    is_truncated=has_any_truncation,
                    permanent_storage_hwm_date=permanent_storage_hwm_date,
                    pages_fetched=pages_fetched,
                    invoices=invoices,
                )

            if response["isTruncated"]:
                has_any_truncation = True
                self._advance_truncated_date_range(
                    filters=effective_filters,
                    sort_order=sort_order,
                    response_invoices=response_invoices,
                )
                page_offset = 0
                continue

            page_offset += 1

    def download_invoice(self, *, access_token: str, ksef_number: str) -> InvoiceDownload:
        response = self._http_client.request(
            "GET",
            f"/invoices/ksef/{quote(ksef_number, safe='')}",
            bearer_token=access_token,
            accept="application/xml",
        )
        return InvoiceDownload(
            ksef_number=ksef_number,
            content=response.body,
            content_hash=response.headers.get("x-ms-meta-hash"),
        )

    def _advance_truncated_date_range(
        self,
        *,
        filters: dict[str, Any],
        sort_order: str,
        response_invoices: list[dict[str, Any]],
    ) -> None:
        date_type = filters["dateRange"]["dateType"]
        if sort_order != "Asc":
            raise KsefApiError("Automatyczna obsługa isTruncated działa tylko dla sortowania Asc.")
        if date_type != "PermanentStorage":
            raise KsefApiError(
                "KSeF zwrócił isTruncated=true. Zawęź zakres ręcznie lub użyj dateType=PermanentStorage."
            )
        if not response_invoices:
            raise KsefApiError("KSeF zwrócił isTruncated=true bez żadnych faktur na stronie wyników.")

        next_from = response_invoices[-1][_invoice_date_field_name(date_type)]
        if next_from == filters["dateRange"]["from"]:
            raise KsefApiError(
                "KSeF zwrócił isTruncated=true, ale nie pozwala zawęzić zakresu dateRange.from."
            )

        filters["dateRange"]["from"] = next_from


def _invoice_date_field_name(date_type: str) -> str:
    try:
        return INVOICE_DATE_FIELDS[date_type]
    except KeyError as error:
        raise ValueError(f"Nieobsługiwany dateType: {date_type}") from error
