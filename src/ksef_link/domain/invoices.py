"""Domain models describing invoice queries and downloads."""

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
    """Typed invoice query payload accepted by the KSeF metadata endpoint."""

    subjectType: str
    dateRange: InvoiceDateRangeFilter
    ksefNumber: str
    invoiceNumber: str
    sellerNip: str


@dataclass(frozen=True)
class InvoiceQueryResult:
    """Aggregated result of traversing invoice metadata pages."""

    has_more: bool
    is_truncated: bool
    permanent_storage_hwm_date: str | None
    pages_fetched: int
    invoices: list[dict[str, Any]]


@dataclass(frozen=True)
class InvoiceDownload:
    """Represents one downloaded invoice XML payload or staged file."""

    ksef_number: str
    content_hash: str | None
    content: bytes | None = None
    source_path: Path | None = None

    def __post_init__(self) -> None:
        """Validate that the download uses exactly one content source.

        Raises:
            ValueError: If both or neither of ``content`` and ``source_path`` are set.
        """
        if (self.content is None) == (self.source_path is None):
            raise ValueError("InvoiceDownload requires exactly one of content or source_path.")
