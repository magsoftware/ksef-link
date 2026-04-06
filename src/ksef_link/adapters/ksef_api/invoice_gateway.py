from __future__ import annotations

from typing import Any
from urllib.parse import quote, urlencode

from ksef_link.adapters.ksef_api.http_client import KsefHttpClient
from ksef_link.adapters.ksef_api.models import InvoiceMetadataPage
from ksef_link.adapters.ksef_api.pagination import InvoiceMetadataPaginator
from ksef_link.domain.invoices import InvoiceDownload, InvoiceQueryResult


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
        filters: dict[str, Any],
        sort_order: str,
        page_size: int,
    ) -> InvoiceQueryResult:
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

    def query_invoice_metadata_page(
        self,
        *,
        access_token: str,
        filters: dict[str, Any],
        sort_order: str,
        page_offset: int,
        page_size: int,
    ) -> InvoiceMetadataPage:
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
