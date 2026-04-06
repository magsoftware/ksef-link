"""Serialization helpers for invoice command responses."""

from __future__ import annotations

from typing import Any

from ksef_link.domain.invoices import InvoiceQueryFilters, InvoiceQueryResult


def serialize_invoice_query_result(
    *,
    filters: InvoiceQueryFilters,
    query_result: InvoiceQueryResult,
    downloads: list[dict[str, str | None]] | None = None,
) -> dict[str, Any]:
    """Convert invoice query results into the CLI response payload.

    Args:
        filters: Typed filter payload sent to the invoice API.
        query_result: Aggregated invoice query result.
        downloads: Optional list of saved file metadata.

    Returns:
        JSON-serializable payload for stdout.
    """
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
