from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ksef_link.domain.invoices import InvoiceDownload


class InvoiceStoragePort(Protocol):
    def save_invoice(self, *, download: InvoiceDownload, output_dir: Path) -> dict[str, str | None]:
        ...
