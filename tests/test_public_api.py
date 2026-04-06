from __future__ import annotations

from ksef_link.adapters.cli import parse_arguments
from ksef_link.adapters.filesystem import FileInvoiceStorage
from ksef_link.adapters.ksef_api import (
    HttpResponse,
    InvoiceMetadataPage,
    KsefAuthService,
    KsefHttpClient,
    KsefInvoiceGateway,
)
from ksef_link.application import (
    ApplicationContext,
    AuthenticateCommandOptions,
    CliOptions,
    CommandOptions,
    InvoicesCommandOptions,
    RefreshCommandOptions,
    RuntimeOptions,
    execute_command,
)
from ksef_link.domain import (
    AuthChallenge,
    AuthenticatedSession,
    AuthenticationMethodInfo,
    AuthInitResult,
    AuthStatus,
    AuthTokens,
    InvoiceDownload,
    InvoiceQueryResult,
    PublicKeyCertificate,
    StatusInfo,
    TokenInfo,
)
from ksef_link.ports import AuthPort, InvoicePort, InvoiceStoragePort
from ksef_link.shared import (
    LOGGER_NAME,
    ConfigurationError,
    KsefApiError,
    KsefLinkError,
    configure_logging,
    env_flag,
    get_logger,
    load_environment,
)


def test_package_public_api_exports_expected_symbols() -> None:
    assert parse_arguments is not None
    assert FileInvoiceStorage is not None
    assert KsefHttpClient is not None
    assert KsefAuthService is not None
    assert KsefInvoiceGateway is not None
    assert HttpResponse is not None
    assert InvoiceMetadataPage is not None
    assert RuntimeOptions is not None
    assert AuthenticateCommandOptions is not None
    assert RefreshCommandOptions is not None
    assert InvoicesCommandOptions is not None
    assert CommandOptions is not None
    assert CliOptions is not None
    assert ApplicationContext is not None
    assert execute_command is not None
    assert AuthPort is not None
    assert InvoicePort is not None
    assert InvoiceStoragePort is not None
    assert TokenInfo is not None
    assert StatusInfo is not None
    assert AuthenticationMethodInfo is not None
    assert AuthChallenge is not None
    assert PublicKeyCertificate is not None
    assert AuthInitResult is not None
    assert AuthStatus is not None
    assert AuthTokens is not None
    assert AuthenticatedSession is not None
    assert InvoiceQueryResult is not None
    assert InvoiceDownload is not None
    assert KsefLinkError is not None
    assert ConfigurationError is not None
    assert KsefApiError is not None
    assert LOGGER_NAME == "ksef_link"
    assert get_logger is not None
    assert configure_logging is not None
    assert load_environment is not None
    assert env_flag is not None
