"""Application bootstrap helpers for assembling runtime dependencies."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from logging import Logger

from ksef_link.adapters.filesystem.invoice_storage import FileInvoiceStorage
from ksef_link.adapters.ksef_api.auth_gateway import KsefAuthService
from ksef_link.adapters.ksef_api.http_client import KsefHttpClient
from ksef_link.adapters.ksef_api.invoice_gateway import KsefInvoiceGateway
from ksef_link.application.commands import CliOptions
from ksef_link.application.context import ApplicationContext


@contextmanager
def build_application_context(
    options: CliOptions,
    environment: Mapping[str, str],
    logger: Logger,
) -> Iterator[ApplicationContext]:
    """Build and manage the application context with all runtime adapters.

    Args:
        options: Parsed CLI options with runtime settings.
        environment: Environment values visible to the application.
        logger: Shared application logger.

    Yields:
        Fully wired application context for the current command execution.
    """
    with KsefHttpClient(
        base_url=options.runtime.base_url,
        timeout=options.runtime.timeout,
        logger=logger,
    ) as http_client:
        yield ApplicationContext(
            environment=environment,
            auth_port=KsefAuthService(http_client),
            invoice_port=KsefInvoiceGateway(http_client),
            invoice_storage=FileInvoiceStorage(logger),
        )
