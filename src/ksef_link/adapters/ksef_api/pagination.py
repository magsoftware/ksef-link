from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any

from ksef_link.adapters.ksef_api.models import InvoiceMetadataPage
from ksef_link.domain.invoices import InvoiceQueryFilters, InvoiceQueryResult
from ksef_link.shared.errors import KsefApiError

INVOICE_DATE_FIELDS = {
    "Issue": "issueDate",
    "Invoicing": "invoicingDate",
    "PermanentStorage": "permanentStorageDate",
}


class InvoiceMetadataPaginator:
    """Collect paged KSeF invoice metadata responses into one result."""

    def __init__(
        self,
        *,
        fetch_page: Callable[[InvoiceQueryFilters, int], InvoiceMetadataPage],
        filters: InvoiceQueryFilters,
        sort_order: str,
    ) -> None:
        self._fetch_page = fetch_page
        self._filters = deepcopy(filters)
        self._sort_order = sort_order

    def collect_all(self) -> InvoiceQueryResult:
        page_offset = 0
        pages_fetched = 0
        has_any_truncation = False
        permanent_storage_hwm_date: str | None = None
        invoices: list[dict[str, Any]] = []
        seen_ksef_numbers: set[str] = set()

        while True:
            page = self._fetch_page(self._filters, page_offset)
            pages_fetched += 1
            if permanent_storage_hwm_date is None:
                permanent_storage_hwm_date = page.permanent_storage_hwm_date

            for invoice in page.invoices:
                ksef_number = invoice["ksefNumber"]
                if ksef_number in seen_ksef_numbers:
                    continue
                seen_ksef_numbers.add(ksef_number)
                invoices.append(invoice)

            if page.is_truncated and not page.has_more:
                raise KsefApiError(
                    "KSeF zwrócił niejednoznaczne flagi paginacji: hasMore=false oraz isTruncated=true."
                )

            if not page.has_more:
                return InvoiceQueryResult(
                    has_more=False,
                    is_truncated=has_any_truncation,
                    permanent_storage_hwm_date=permanent_storage_hwm_date,
                    pages_fetched=pages_fetched,
                    invoices=invoices,
                )

            if page.is_truncated:
                has_any_truncation = True
                self._advance_truncated_date_range(page.invoices)
                page_offset = 0
                continue

            page_offset += 1

    def _advance_truncated_date_range(self, response_invoices: list[dict[str, Any]]) -> None:
        date_type = self._filters["dateRange"]["dateType"]
        if self._sort_order != "Asc":
            raise KsefApiError("Automatyczna obsługa isTruncated działa tylko dla sortowania Asc.")
        if date_type != "PermanentStorage":
            raise KsefApiError(
                "KSeF zwrócił isTruncated=true. Zawęź zakres ręcznie lub użyj dateType=PermanentStorage."
            )
        if not response_invoices:
            raise KsefApiError("KSeF zwrócił isTruncated=true bez żadnych faktur na stronie wyników.")

        next_from = response_invoices[-1][_invoice_date_field_name(date_type)]
        if next_from == self._filters["dateRange"]["from"]:
            raise KsefApiError(
                "KSeF zwrócił isTruncated=true, ale nie pozwala zawęzić zakresu dateRange.from."
            )

        self._filters["dateRange"]["from"] = next_from


def _invoice_date_field_name(date_type: str) -> str:
    try:
        return INVOICE_DATE_FIELDS[date_type]
    except KeyError as error:
        raise ValueError(f"Nieobsługiwany dateType: {date_type}") from error
