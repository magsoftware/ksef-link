"""Invoice query and download port exposed to the application layer."""

from __future__ import annotations

from typing import Protocol

from ksef_link.domain.invoices import InvoiceDownload, InvoiceQueryFilters, InvoiceQueryResult


class InvoicePort(Protocol):
    """Protocol implemented by invoice adapters."""

    def query_all_invoice_metadata(
        self,
        *,
        access_token: str,
        filters: InvoiceQueryFilters,
        sort_order: str,
        page_size: int,
    ) -> InvoiceQueryResult:
        """Query and aggregate invoice metadata."""
        ...

    def download_invoice(self, *, access_token: str, ksef_number: str) -> InvoiceDownload:
        """Download one invoice XML document."""
        ...
