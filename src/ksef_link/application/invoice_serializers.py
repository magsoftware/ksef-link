from __future__ import annotations

from typing import Any

from ksef_link.domain.invoices import InvoiceQueryFilters, InvoiceQueryResult


def serialize_invoice_query_result(
    *,
    filters: InvoiceQueryFilters,
    query_result: InvoiceQueryResult,
    downloads: list[dict[str, str | None]] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
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
    if downloads is not None:
        payload["downloads"] = downloads
    return payload
