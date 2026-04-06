"""Invoice-specific KSeF API adapter."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote, urlencode

from ksef_link.adapters.ksef_api.http_client import KsefHttpClient
from ksef_link.adapters.ksef_api.models import InvoiceMetadataPage
from ksef_link.adapters.ksef_api.pagination import InvoiceMetadataPaginator
from ksef_link.domain.invoices import InvoiceDownload, InvoiceQueryFilters, InvoiceQueryResult


class KsefInvoiceGateway:
    """KSeF invoice gateway adapter."""

    def __init__(self, http_client: KsefHttpClient) -> None:
        """Initialize the invoice gateway.

        Args:
            http_client: Shared HTTP client used to talk to KSeF.
        """
        self._http_client = http_client

    def query_invoice_metadata(
        self,
        *,
        access_token: str,
        filters: InvoiceQueryFilters,
        sort_order: str,
        page_offset: int,
        page_size: int,
    ) -> dict[str, Any]:
        """Query one raw page of invoice metadata and return public payload shape.

        Args:
            access_token: Access token used for authorization.
            filters: Typed invoice query filters.
            sort_order: Requested API sort order.
            page_offset: Zero-based page offset.
            page_size: Maximum number of items per page.

        Returns:
            JSON-serializable payload representing one metadata page.
        """
        page = self.query_invoice_metadata_page(
            access_token=access_token,
            filters=filters,
            sort_order=sort_order,
            page_offset=page_offset,
            page_size=page_size,
        )
        return page.to_payload()

    def query_all_invoice_metadata(
        self,
        *,
        access_token: str,
        filters: InvoiceQueryFilters,
        sort_order: str,
        page_size: int,
    ) -> InvoiceQueryResult:
        """Query all invoice metadata pages and aggregate the result.

        Args:
            access_token: Access token used for authorization.
            filters: Typed invoice query filters.
            sort_order: Requested API sort order.
            page_size: Maximum number of items per page.

        Returns:
            Aggregated invoice query result.
        """
        paginator = InvoiceMetadataPaginator(
            fetch_page=lambda current_filters, page_offset: self.query_invoice_metadata_page(
                access_token=access_token,
                filters=current_filters,
                sort_order=sort_order,
                page_offset=page_offset,
                page_size=page_size,
            ),
            filters=filters,
            sort_order=sort_order,
        )
        return paginator.collect_all()

    def download_invoice(self, *, access_token: str, ksef_number: str) -> InvoiceDownload:
        """Download an invoice XML document into a temporary file.

        Args:
            access_token: Access token used for authorization.
            ksef_number: Invoice identifier in KSeF.

        Returns:
            Download descriptor pointing to the staged XML file.
        """
        response = self._http_client.request_stream_to_file(
            "GET",
            f"/invoices/ksef/{quote(ksef_number, safe='')}",
            bearer_token=access_token,
            accept="application/xml",
        )
        return InvoiceDownload(
            ksef_number=ksef_number,
            content_hash=response.headers.get("x-ms-meta-hash"),
            source_path=response.file_path,
        )

    def query_invoice_metadata_page(
        self,
        *,
        access_token: str,
        filters: InvoiceQueryFilters,
        sort_order: str,
        page_offset: int,
        page_size: int,
    ) -> InvoiceMetadataPage:
        """Query one invoice metadata page and convert it to a typed model.

        Args:
            access_token: Access token used for authorization.
            filters: Typed invoice query filters.
            sort_order: Requested API sort order.
            page_offset: Zero-based page offset.
            page_size: Maximum number of items per page.

        Returns:
            Typed invoice metadata page.
        """
        query = urlencode(
            {
                "sortOrder": sort_order,
                "pageOffset": page_offset,
                "pageSize": page_size,
            }
        )
        return InvoiceMetadataPage.from_api(
            self._http_client.request_json(
                "POST",
                f"/invoices/query/metadata?{query}",
                bearer_token=access_token,
                json_body=filters,
            )
        )
