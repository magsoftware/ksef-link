from __future__ import annotations

from ksef_link.domain.invoices import InvoiceDownload, InvoiceQueryResult


def test_invoice_query_result_and_download_store_values() -> None:
    query_result = InvoiceQueryResult(
        has_more=False,
        is_truncated=False,
        permanent_storage_hwm_date=None,
        pages_fetched=1,
        invoices=[],
    )
    invoice_download = InvoiceDownload(ksef_number="ksef", content=b"<xml/>", content_hash="hash")

    assert query_result.pages_fetched == 1
    assert invoice_download.content == b"<xml/>"
