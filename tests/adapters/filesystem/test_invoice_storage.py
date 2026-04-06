from __future__ import annotations

import logging
from pathlib import Path

from ksef_link.adapters.filesystem.invoice_storage import FileInvoiceStorage
from ksef_link.domain.invoices import InvoiceDownload


def test_save_invoice_writes_xml_and_returns_metadata(tmp_path: Path) -> None:
    storage = FileInvoiceStorage(logging.getLogger("test"))
    result = storage.save_invoice(
        download=InvoiceDownload(ksef_number="1", content=b"<xml>1</xml>", content_hash="hash1"),
        output_dir=tmp_path,
    )

    assert result["contentHash"] == "hash1"
    assert (tmp_path / "1.xml").read_text(encoding="utf-8") == "<xml>1</xml>"
