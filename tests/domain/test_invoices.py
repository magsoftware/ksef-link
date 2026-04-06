from __future__ import annotations

from pathlib import Path

import pytest

from ksef_link.domain.invoices import InvoiceDownload, InvoiceQueryFilters, InvoiceQueryResult


def test_invoice_query_result_and_download_store_values() -> None:
    query_result = InvoiceQueryResult(
        has_more=False,
        is_truncated=False,
        permanent_storage_hwm_date=None,
        pages_fetched=1,
        invoices=[],
    )
    invoice_download = InvoiceDownload(ksef_number="ksef", content_hash="hash", content=b"<xml/>")
    filters: InvoiceQueryFilters = {
        "subjectType": "Subject2",
        "dateRange": {
            "dateType": "PermanentStorage",
            "from": "2026-04-01T00:00:00+02:00",
            "to": "2026-04-02T00:00:00+02:00",
            "restrictToPermanentStorageHwmDate": False,
        },
    }

    assert query_result.pages_fetched == 1
    assert invoice_download.content == b"<xml/>"
    assert filters["subjectType"] == "Subject2"


def test_invoice_download_requires_exactly_one_payload_source(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        InvoiceDownload(ksef_number="ksef", content_hash="hash", content=b"x", source_path=tmp_path / "a.xml")

    with pytest.raises(ValueError):
        InvoiceDownload(ksef_number="ksef", content_hash="hash")
