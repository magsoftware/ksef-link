from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ksef_link.shared.errors import KsefApiError


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    body: bytes
    headers: dict[str, str]


@dataclass(frozen=True)
class InvoiceMetadataPage:
    has_more: bool
    is_truncated: bool
    permanent_storage_hwm_date: str | None
    invoices: list[dict[str, Any]]

    @classmethod
    def from_api(cls, payload: Any) -> InvoiceMetadataPage:
        if not isinstance(payload, dict):
            raise KsefApiError("KSeF zwrócił nieprawidłowy format odpowiedzi dla listy metadanych faktur.")

        raw_invoices = payload.get("invoices")
        if not isinstance(raw_invoices, list):
            raise KsefApiError("KSeF zwrócił nieprawidłową listę faktur w odpowiedzi metadanych.")

        return cls(
            has_more=bool(payload["hasMore"]),
            is_truncated=bool(payload["isTruncated"]),
            permanent_storage_hwm_date=payload.get("permanentStorageHwmDate"),
            invoices=list(raw_invoices),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "hasMore": self.has_more,
            "isTruncated": self.is_truncated,
            "permanentStorageHwmDate": self.permanent_storage_hwm_date,
            "invoices": self.invoices,
        }
