from __future__ import annotations

from ksef_link.application.invoice_serializers import serialize_invoice_query_result
from ksef_link.domain.invoices import InvoiceQueryResult


def test_serialize_invoice_query_result_without_downloads() -> None:
    payload = serialize_invoice_query_result(
        filters={"subjectType": "Subject2"},
        query_result=InvoiceQueryResult(
            has_more=False,
            is_truncated=False,
            permanent_storage_hwm_date="hwm",
            pages_fetched=1,
            invoices=[{"ksefNumber": "1"}],
        ),
    )

    assert payload == {
        "filters": {"subjectType": "Subject2"},
        "summary": {
            "count": 1,
            "pagesFetched": 1,
            "hasMore": False,
            "isTruncated": False,
            "permanentStorageHwmDate": "hwm",
        },
        "invoices": [{"ksefNumber": "1"}],
    }


def test_serialize_invoice_query_result_includes_downloads_when_present() -> None:
    payload = serialize_invoice_query_result(
        filters={"subjectType": "Subject2"},
        query_result=InvoiceQueryResult(
            has_more=False,
            is_truncated=False,
            permanent_storage_hwm_date=None,
            pages_fetched=1,
            invoices=[],
        ),
        downloads=[{"ksefNumber": "1", "path": "1.xml", "contentHash": "hash"}],
    )

    assert payload["downloads"] == [{"ksefNumber": "1", "path": "1.xml", "contentHash": "hash"}]
