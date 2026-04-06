from __future__ import annotations

from typing import Any

import pytest

from ksef_link.adapters.ksef_api.models import InvoiceMetadataPage
from ksef_link.adapters.ksef_api.pagination import InvoiceMetadataPaginator, _invoice_date_field_name
from ksef_link.domain.invoices import InvoiceQueryFilters
from ksef_link.shared.errors import KsefApiError


def _build_filters(date_type: str, date_from: str) -> InvoiceQueryFilters:
    return {
        "subjectType": "Subject2",
        "dateRange": {
            "dateType": date_type,
            "from": date_from,
            "to": "2026-04-30T23:59:59+02:00",
            "restrictToPermanentStorageHwmDate": False,
        },
    }


def test_collect_all_deduplicates_invoices_across_pages() -> None:
    pages = [
        InvoiceMetadataPage(
            has_more=True,
            is_truncated=False,
            permanent_storage_hwm_date="hwm",
            invoices=[{"ksefNumber": "1"}, {"ksefNumber": "2"}],
        ),
        InvoiceMetadataPage(
            has_more=False,
            is_truncated=False,
            permanent_storage_hwm_date="hwm",
            invoices=[{"ksefNumber": "2"}, {"ksefNumber": "3"}],
        ),
    ]
    paginator = InvoiceMetadataPaginator(
        fetch_page=lambda filters, page_offset: pages.pop(0),
        filters=_build_filters("PermanentStorage", "a"),
        sort_order="Asc",
    )

    result = paginator.collect_all()

    assert result.pages_fetched == 2
    assert result.permanent_storage_hwm_date == "hwm"
    assert [invoice["ksefNumber"] for invoice in result.invoices] == ["1", "2", "3"]


def test_collect_all_handles_truncated_result_by_advancing_date_range() -> None:
    pages = [
        InvoiceMetadataPage(
            has_more=True,
            is_truncated=True,
            permanent_storage_hwm_date="hwm",
            invoices=[{"ksefNumber": "1", "permanentStorageDate": "2026-04-02T00:00:00+02:00"}],
        ),
        InvoiceMetadataPage(
            has_more=False,
            is_truncated=False,
            permanent_storage_hwm_date="hwm",
            invoices=[{"ksefNumber": "2"}],
        ),
    ]
    seen_filters: list[dict[str, Any]] = []

    def fetch_page(filters: InvoiceQueryFilters, page_offset: int) -> InvoiceMetadataPage:
        seen_filters.append({"from": filters["dateRange"]["from"], "pageOffset": page_offset})
        return pages.pop(0)

    paginator = InvoiceMetadataPaginator(
        fetch_page=fetch_page,
        filters=_build_filters("PermanentStorage", "2026-04-01T00:00:00+02:00"),
        sort_order="Asc",
    )

    result = paginator.collect_all()

    assert result.is_truncated is True
    assert seen_filters == [
        {"from": "2026-04-01T00:00:00+02:00", "pageOffset": 0},
        {"from": "2026-04-02T00:00:00+02:00", "pageOffset": 0},
    ]


def test_collect_all_raises_for_ambiguous_truncated_last_page() -> None:
    paginator = InvoiceMetadataPaginator(
        fetch_page=lambda filters, page_offset: InvoiceMetadataPage(
            has_more=False,
            is_truncated=True,
            permanent_storage_hwm_date="hwm",
            invoices=[{"ksefNumber": "1"}],
        ),
        filters=_build_filters("PermanentStorage", "a"),
        sort_order="Asc",
    )

    with pytest.raises(KsefApiError):
        paginator.collect_all()


def test_advance_truncated_date_range_validation_errors() -> None:
    paginator = InvoiceMetadataPaginator(
        fetch_page=lambda filters, page_offset: InvoiceMetadataPage(
            has_more=False,
            is_truncated=False,
            permanent_storage_hwm_date=None,
            invoices=[],
        ),
        filters=_build_filters("PermanentStorage", "a"),
        sort_order="Asc",
    )

    with pytest.raises(KsefApiError):
        InvoiceMetadataPaginator(
            fetch_page=lambda filters, page_offset: InvoiceMetadataPage(
                has_more=False,
                is_truncated=False,
                permanent_storage_hwm_date=None,
                invoices=[],
            ),
            filters=_build_filters("PermanentStorage", "a"),
            sort_order="Desc",
        )._advance_truncated_date_range(response_invoices=[{"permanentStorageDate": "b"}])

    with pytest.raises(KsefApiError):
        InvoiceMetadataPaginator(
            fetch_page=lambda filters, page_offset: InvoiceMetadataPage(
                has_more=False,
                is_truncated=False,
                permanent_storage_hwm_date=None,
                invoices=[],
            ),
            filters=_build_filters("Issue", "a"),
            sort_order="Asc",
        )._advance_truncated_date_range(response_invoices=[{"issueDate": "b"}])

    with pytest.raises(KsefApiError):
        paginator._advance_truncated_date_range(response_invoices=[])

    with pytest.raises(KsefApiError):
        InvoiceMetadataPaginator(
            fetch_page=lambda filters, page_offset: InvoiceMetadataPage(
                has_more=False,
                is_truncated=False,
                permanent_storage_hwm_date=None,
                invoices=[],
            ),
            filters=_build_filters("PermanentStorage", "same"),
            sort_order="Asc",
        )._advance_truncated_date_range(response_invoices=[{"permanentStorageDate": "same"}])


def test_invoice_date_field_name_supports_all_variants() -> None:
    assert _invoice_date_field_name("Issue") == "issueDate"
    assert _invoice_date_field_name("Invoicing") == "invoicingDate"
    assert _invoice_date_field_name("PermanentStorage") == "permanentStorageDate"

    with pytest.raises(ValueError):
        _invoice_date_field_name("Other")
