"""Transport-oriented models used by the KSeF API adapters."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ksef_link.shared.errors import KsefApiError


@dataclass(frozen=True)
class HttpResponse:
    """Represents a fully buffered HTTP response."""

    status_code: int
    body: bytes
    headers: dict[str, str]


@dataclass(frozen=True)
class StreamedHttpResponse:
    """Represents an HTTP response streamed into a temporary file."""

    status_code: int
    file_path: Path
    headers: dict[str, str]


@dataclass(frozen=True)
class InvoiceMetadataPage:
    """Represents one page returned by the invoice metadata endpoint."""

    has_more: bool
    is_truncated: bool
    permanent_storage_hwm_date: str | None
    invoices: list[dict[str, Any]]

    @classmethod
    def from_api(cls, payload: Any) -> InvoiceMetadataPage:
        """Build a metadata page model from a KSeF API payload.

        Args:
            payload: Raw payload returned by the metadata endpoint.

        Returns:
            Parsed invoice metadata page.

        Raises:
            KsefApiError: If the payload shape is invalid.
        """
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
        """Convert the page back into the public JSON shape.

        Returns:
            JSON-serializable payload mirroring the KSeF response.
        """
        return {
            "hasMore": self.has_more,
            "isTruncated": self.is_truncated,
            "permanentStorageHwmDate": self.permanent_storage_hwm_date,
            "invoices": self.invoices,
        }
