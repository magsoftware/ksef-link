from __future__ import annotations

import pytest

from ksef_link.adapters.ksef_api.models import HttpResponse, InvoiceMetadataPage
from ksef_link.shared.errors import KsefApiError


def test_http_response_dataclass_stores_values() -> None:
    response = HttpResponse(status_code=200, body=b"{}", headers={"Content-Type": "application/json"})

    assert response.status_code == 200


def test_invoice_metadata_page_roundtrip() -> None:
    page = InvoiceMetadataPage.from_api(
        {
            "hasMore": True,
            "isTruncated": False,
            "permanentStorageHwmDate": "2026-04-06T12:00:00+02:00",
            "invoices": [{"ksefNumber": "1"}],
        }
    )

    assert page.to_payload() == {
        "hasMore": True,
        "isTruncated": False,
        "permanentStorageHwmDate": "2026-04-06T12:00:00+02:00",
        "invoices": [{"ksefNumber": "1"}],
    }


def test_invoice_metadata_page_rejects_invalid_payloads() -> None:
    with pytest.raises(KsefApiError):
        InvoiceMetadataPage.from_api(["not-a-dict"])

    with pytest.raises(KsefApiError):
        InvoiceMetadataPage.from_api({"hasMore": False, "isTruncated": False, "invoices": "bad"})
