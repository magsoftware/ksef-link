from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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
    content: bytes
    content_hash: str | None
