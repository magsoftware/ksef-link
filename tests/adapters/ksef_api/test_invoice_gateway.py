from __future__ import annotations

from typing import Any

import pytest

from ksef_link.adapters.ksef_api.invoice_gateway import KsefInvoiceGateway
from ksef_link.adapters.ksef_api.models import HttpResponse
from ksef_link.shared.errors import KsefApiError


class StubHttpClient:
    def __init__(
        self,
        json_responses: list[Any] | None = None,
        raw_responses: list[HttpResponse] | None = None,
    ) -> None:
        self.json_responses = json_responses or []
        self.raw_responses = raw_responses or []
        self.json_calls: list[dict[str, Any]] = []
        self.raw_calls: list[dict[str, Any]] = []

    def request_json(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        bearer_token: str | None = None,
        content: bytes | None = None,
    ) -> Any:
        self.json_calls.append(
            {"method": method, "path": path, "json_body": json_body, "bearer_token": bearer_token, "content": content}
        )
        return self.json_responses.pop(0)

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        bearer_token: str | None = None,
        content: bytes | None = None,
        accept: str = "application/json",
    ) -> HttpResponse:
        self.raw_calls.append(
            {
                "method": method,
                "path": path,
                "json_body": json_body,
                "bearer_token": bearer_token,
                "content": content,
                "accept": accept,
            }
        )
        return self.raw_responses.pop(0)


def test_query_invoice_metadata_builds_request_and_returns_payload() -> None:
    http_client = StubHttpClient(json_responses=[{"hasMore": False, "isTruncated": False, "invoices": []}])
    service = KsefInvoiceGateway(http_client)  # type: ignore[arg-type]

    payload = service.query_invoice_metadata(
        access_token="access",
        filters={"subjectType": "Subject2"},
        sort_order="Asc",
        page_offset=0,
        page_size=250,
    )

    assert payload["hasMore"] is False
    assert "pageSize=250" in http_client.json_calls[0]["path"]


def test_query_invoice_metadata_raises_for_non_dict_payload() -> None:
    http_client = StubHttpClient(json_responses=[["not-a-dict"]])
    service = KsefInvoiceGateway(http_client)  # type: ignore[arg-type]

    with pytest.raises(KsefApiError):
        service.query_invoice_metadata(
            access_token="access",
            filters={"subjectType": "Subject2"},
            sort_order="Asc",
            page_offset=0,
            page_size=250,
        )


def test_query_all_invoice_metadata_handles_multiple_pages_and_deduplicates() -> None:
    http_client = StubHttpClient(
        json_responses=[
            {
                "hasMore": True,
                "isTruncated": False,
                "permanentStorageHwmDate": "hwm",
                "invoices": [{"ksefNumber": "1"}, {"ksefNumber": "2"}],
            },
            {
                "hasMore": False,
                "isTruncated": False,
                "permanentStorageHwmDate": "hwm",
                "invoices": [{"ksefNumber": "2"}, {"ksefNumber": "3"}],
            },
        ]
    )
    service = KsefInvoiceGateway(http_client)  # type: ignore[arg-type]

    result = service.query_all_invoice_metadata(
        access_token="access",
        filters={"dateRange": {"dateType": "PermanentStorage", "from": "a"}},
        sort_order="Asc",
        page_size=250,
    )

    assert result.pages_fetched == 2
    assert [invoice["ksefNumber"] for invoice in result.invoices] == ["1", "2", "3"]


def test_query_all_invoice_metadata_handles_truncated_result() -> None:
    http_client = StubHttpClient(
        json_responses=[
            {
                "hasMore": True,
                "isTruncated": True,
                "permanentStorageHwmDate": "hwm",
                "invoices": [{"ksefNumber": "1", "permanentStorageDate": "2026-04-02T00:00:00+02:00"}],
            },
            {
                "hasMore": False,
                "isTruncated": False,
                "permanentStorageHwmDate": "hwm",
                "invoices": [{"ksefNumber": "2"}],
            },
        ]
    )
    service = KsefInvoiceGateway(http_client)  # type: ignore[arg-type]

    result = service.query_all_invoice_metadata(
        access_token="access",
        filters={"dateRange": {"dateType": "PermanentStorage", "from": "2026-04-01T00:00:00+02:00"}},
        sort_order="Asc",
        page_size=250,
    )

    assert result.is_truncated is True
    assert result.pages_fetched == 2


def test_download_invoice_returns_xml_response() -> None:
    http_client = StubHttpClient(
        raw_responses=[HttpResponse(status_code=200, body=b"<xml>1</xml>", headers={"x-ms-meta-hash": "hash1"})]
    )
    service = KsefInvoiceGateway(http_client)  # type: ignore[arg-type]

    single = service.download_invoice(access_token="access", ksef_number="1/2")

    assert single.content_hash == "hash1"
    assert http_client.raw_calls[0]["accept"] == "application/xml"
    assert "%2F" in http_client.raw_calls[0]["path"]
