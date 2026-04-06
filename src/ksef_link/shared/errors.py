from __future__ import annotations

from typing import Any


class KsefLinkError(Exception):
    """Base exception for application-level failures."""


class ConfigurationError(KsefLinkError):
    """Raised when configuration required to execute a command is missing."""


class KsefApiError(KsefLinkError):
    """Raised when KSeF API returns an error or cannot be reached."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        error_code: str | int | None = None,
        details: Any | None = None,
        body: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.details = details
        self.body = body

    def to_payload(self) -> dict[str, Any]:
        """Convert the error into a user-facing JSON payload."""
        return {
            "error": str(self),
            "statusCode": self.status_code,
            "errorCode": self.error_code,
            "details": self.details,
        }

    def to_log_payload(self) -> dict[str, Any]:
        """Convert the error into a diagnostic payload for logs."""
        return {
            "error": str(self),
            "statusCode": self.status_code,
            "errorCode": self.error_code,
            "details": self.details,
            "body": self.body,
        }
