"""Command dispatching for the application layer."""

from __future__ import annotations

from typing import Any

from ksef_link.application.auth_handlers import handle_authenticate_command, handle_refresh_command
from ksef_link.application.commands import (
    AuthenticateCommandOptions,
    CliOptions,
    InvoicesCommandOptions,
    RefreshCommandOptions,
)
from ksef_link.application.context import ApplicationContext
from ksef_link.application.invoice_handlers import handle_invoices_command
from ksef_link.shared.errors import ConfigurationError


def execute_command(options: CliOptions, context: ApplicationContext) -> dict[str, Any]:
    """Execute the selected CLI command.

    Args:
        options: Parsed CLI options with the selected command.
        context: Runtime dependencies available to command handlers.

    Returns:
        JSON-serializable payload ready to be printed to stdout.

    Raises:
        ConfigurationError: If the command type is not supported by the dispatcher.
    """
    command = options.command
    if isinstance(command, AuthenticateCommandOptions):
        return handle_authenticate_command(
            command,
            context.environment,
            context.auth_port,
        )
    if isinstance(command, RefreshCommandOptions):
        return handle_refresh_command(command, context.auth_port)
    if isinstance(command, InvoicesCommandOptions):
        return handle_invoices_command(
            command,
            context.environment,
            context.auth_port,
            context.invoice_port,
            context.invoice_storage,
        )
    raise ConfigurationError("Nieobsługiwany typ komendy.")
