"""Filesystem adapter for persisting downloaded invoice XML files."""

from __future__ import annotations

import shutil
from logging import Logger
from pathlib import Path

from ksef_link.domain.invoices import InvoiceDownload
from ksef_link.ports.storage import InvoiceStoragePort


class FileInvoiceStorage(InvoiceStoragePort):
    """Filesystem adapter for storing downloaded invoice XML files."""

    def __init__(self, logger: Logger) -> None:
        """Initialize the filesystem storage adapter.

        Args:
            logger: Application logger used for debug output.
        """
        self._logger = logger

    def save_invoice(self, *, download: InvoiceDownload, output_dir: Path) -> dict[str, str | None]:
        """Persist a downloaded invoice into the target directory.

        Args:
            download: Download descriptor containing XML data or staged file path.
            output_dir: Target directory for the final XML file.

        Returns:
            Saved file metadata exposed in the CLI response.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        target_path = output_dir / f"{download.ksef_number}.xml"
        if download.source_path is not None:
            shutil.move(str(download.source_path), target_path)
        else:
            assert download.content is not None
            target_path.write_bytes(download.content)
        self._logger.debug("Saved invoice XML to %s for ksefNumber=%s", target_path, download.ksef_number)
        return {
            "ksefNumber": download.ksef_number,
            "path": str(target_path),
            "contentHash": download.content_hash,
        }
