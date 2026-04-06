from __future__ import annotations

import logging
from pathlib import Path

from ksef_link.adapters.filesystem.invoice_storage import FileInvoiceStorage
from ksef_link.domain.invoices import InvoiceDownload


def test_save_invoice_writes_xml_and_returns_metadata(tmp_path: Path) -> None:
    storage = FileInvoiceStorage(logging.getLogger("test"))
    result = storage.save_invoice(
        download=InvoiceDownload(ksef_number="1", content_hash="hash1", content=b"<xml>1</xml>"),
        output_dir=tmp_path,
    )

    assert result["contentHash"] == "hash1"
    assert (tmp_path / "1.xml").read_text(encoding="utf-8") == "<xml>1</xml>"


def test_save_invoice_moves_streamed_file_into_output_directory(tmp_path: Path) -> None:
    storage = FileInvoiceStorage(logging.getLogger("test"))
    source_path = tmp_path / "source.xml"
    source_path.write_text("<xml>streamed</xml>", encoding="utf-8")

    result = storage.save_invoice(
        download=InvoiceDownload(ksef_number="2", content_hash="hash2", source_path=source_path),
        output_dir=tmp_path / "out",
    )

    assert result["contentHash"] == "hash2"
    assert not source_path.exists()
    assert (tmp_path / "out" / "2.xml").read_text(encoding="utf-8") == "<xml>streamed</xml>"
