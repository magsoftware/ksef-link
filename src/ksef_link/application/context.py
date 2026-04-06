"""Dependency container passed to application command handlers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from ksef_link.ports.auth import AuthPort
from ksef_link.ports.invoices import InvoicePort
from ksef_link.ports.storage import InvoiceStoragePort


@dataclass(frozen=True)
class ApplicationContext:
    """Holds runtime services needed to execute a CLI command."""

    environment: Mapping[str, str]
    auth_port: AuthPort
    invoice_port: InvoicePort
    invoice_storage: InvoiceStoragePort
