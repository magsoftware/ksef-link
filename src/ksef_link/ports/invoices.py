from __future__ import annotations

from typing import Protocol

from ksef_link.domain.invoices import InvoiceDownload, InvoiceQueryFilters, InvoiceQueryResult


class InvoicePort(Protocol):
    def query_all_invoice_metadata(
        self,
        *,
        access_token: str,
        filters: InvoiceQueryFilters,
        sort_order: str,
        page_size: int,
    ) -> InvoiceQueryResult:
        ...

    def download_invoice(self, *, access_token: str, ksef_number: str) -> InvoiceDownload:
        ...
