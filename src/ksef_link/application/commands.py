"""Typed command objects produced by the CLI parser."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RuntimeOptions:
    """Runtime configuration shared by every CLI command."""

    base_url: str
    timeout: float
    debug: bool
    env_file: Path


@dataclass(frozen=True)
class AuthenticateCommandOptions:
    """Arguments required by the ``authenticate`` command."""

    ksef_token: str | None
    context_type: str
    context_value: str
    poll_interval: float
    wait_timeout: float
    allowed_ipv4: tuple[str, ...]
    allowed_ipv4_range: tuple[str, ...]
    allowed_ipv4_mask: tuple[str, ...]


@dataclass(frozen=True)
class RefreshCommandOptions:
    """Arguments required by the ``refresh`` command."""

    refresh_token: str


@dataclass(frozen=True)
class InvoicesCommandOptions:
    """Arguments required by the ``invoices`` command."""

    access_token: str | None
    refresh_token: str | None
    ksef_token: str | None
    context_type: str | None
    context_value: str | None
    subject_type: str
    date_type: str
    date_from: str | None
    date_to: str | None
    sort_order: str
    page_size: int
    restrict_to_hwm: bool
    ksef_number: str | None
    invoice_number: str | None
    seller_nip: str | None
    download_dir: Path | None
    poll_interval: float
    wait_timeout: float


CommandOptions = AuthenticateCommandOptions | RefreshCommandOptions | InvoicesCommandOptions


@dataclass(frozen=True)
class CliOptions:
    """Root object containing runtime options and the selected command."""

    runtime: RuntimeOptions
    command: CommandOptions
