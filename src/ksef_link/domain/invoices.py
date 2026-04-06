from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypedDict

InvoiceDateRangeFilter = TypedDict(
    "InvoiceDateRangeFilter",
    {
        "dateType": str,
        "from": str,
        "to": str,
        "restrictToPermanentStorageHwmDate": bool,
    },
)


class InvoiceQueryFilters(TypedDict, total=False):
    subjectType: str
    dateRange: InvoiceDateRangeFilter
    ksefNumber: str
    invoiceNumber: str
    sellerNip: str


@dataclass(frozen=True)
class InvoiceQueryResult:
    has_more: bool
    is_truncated: bool
    permanent_storage_hwm_date: str | None
    pages_fetched: int
    invoices: list[dict[str, Any]]


@dataclass(frozen=True)
class InvoiceDownload:
    ksef_number: str
    content_hash: str | None
    content: bytes | None = None
    source_path: Path | None = None

    def __post_init__(self) -> None:
        if (self.content is None) == (self.source_path is None):
            raise ValueError("InvoiceDownload requires exactly one of content or source_path.")
