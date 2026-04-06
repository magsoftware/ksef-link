from __future__ import annotations

from logging import Logger
from pathlib import Path

from ksef_link.domain.invoices import InvoiceDownload
from ksef_link.ports.storage import InvoiceStoragePort


class FileInvoiceStorage(InvoiceStoragePort):
    """Filesystem adapter for storing downloaded invoice XML files."""

    def __init__(self, logger: Logger) -> None:
        self._logger = logger

    def save_invoice(self, *, download: InvoiceDownload, output_dir: Path) -> dict[str, str | None]:
        output_dir.mkdir(parents=True, exist_ok=True)
        target_path = output_dir / f"{download.ksef_number}.xml"
        target_path.write_bytes(download.content)
        self._logger.debug("Saved invoice XML to %s for ksefNumber=%s", target_path, download.ksef_number)
        return {
            "ksefNumber": download.ksef_number,
            "path": str(target_path),
            "contentHash": download.content_hash,
        }
