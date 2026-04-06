from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

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

type CommandHandler = Callable[[object, ApplicationContext], dict[str, Any]]


def _dispatch_authenticate_command(command: object, context: ApplicationContext) -> dict[str, Any]:
    return handle_authenticate_command(
        cast(AuthenticateCommandOptions, command),
        context.environment,
        context.auth_port,
    )


def _dispatch_refresh_command(command: object, context: ApplicationContext) -> dict[str, Any]:
    return handle_refresh_command(cast(RefreshCommandOptions, command), context.auth_port)


def _dispatch_invoices_command(command: object, context: ApplicationContext) -> dict[str, Any]:
    return handle_invoices_command(
        cast(InvoicesCommandOptions, command),
        context.environment,
        context.auth_port,
        context.invoice_port,
        context.invoice_storage,
    )


COMMAND_HANDLERS: dict[type[object], CommandHandler] = {
    AuthenticateCommandOptions: _dispatch_authenticate_command,
    RefreshCommandOptions: _dispatch_refresh_command,
    InvoicesCommandOptions: _dispatch_invoices_command,
}


def execute_command(options: CliOptions, context: ApplicationContext) -> dict[str, Any]:
    """Execute the selected CLI command."""
    handler = COMMAND_HANDLERS.get(type(options.command))
    if handler is not None:
        return handler(options.command, context)
    raise ConfigurationError("Nieobsługiwany typ komendy.")
