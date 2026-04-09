"""Low-level HTTP client with KSeF-specific logging and retry behavior."""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar

import httpx

from ksef_link.adapters.ksef_api.models import HttpResponse, StreamedHttpResponse
from ksef_link.shared.errors import KsefApiError

REDACTED = "***REDACTED***"
MAX_DEBUG_JSON_BYTES = 16_384
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_BASE_RETRY_DELAY = 0.5
DEFAULT_MAX_RETRY_DELAY = 8.0
RETRYABLE_STATUS_CODES = {429, 502, 503, 504}
RETRYABLE_POST_PATHS = {
    "/auth/challenge",
    "/auth/token/refresh",
    "/invoices/query/metadata",
}
SENSITIVE_KEYS = {
    "authorization",
    "token",
    "encryptedtoken",
    "accesstoken",
    "refreshtoken",
    "authenticationtoken",
    "kseftoken",
}
T = TypeVar("T")


@dataclass(frozen=True)
class _RetryDirective:
    """Internal signal indicating the request should be retried."""

    status_code: int
    retry_after: float | None = None


class KsefHttpClient:
    """Thin HTTP client with logging and KSeF-specific error mapping."""

    def __init__(
        self,
        base_url: str,
        timeout: float,
        logger: logging.Logger,
        client: httpx.Client | None = None,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        base_retry_delay: float = DEFAULT_BASE_RETRY_DELAY,
        max_retry_delay: float = DEFAULT_MAX_RETRY_DELAY,
        sleep_fn: Callable[[float], None] | None = None,
    ) -> None:
        """Initialize the HTTP client wrapper.

        Args:
            base_url: Base URL of the KSeF API.
            timeout: Default per-request timeout in seconds.
            logger: Logger used for debug and retry messages.
            client: Optional injected ``httpx.Client``.
            max_attempts: Maximum number of attempts for retryable requests.
            base_retry_delay: Base retry delay in seconds.
            max_retry_delay: Maximum retry delay in seconds.
            sleep_fn: Optional sleep implementation used mainly by tests.

        Raises:
            ValueError: If ``max_attempts`` is smaller than one.
        """
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        self._logger = logger
        self._owns_client = client is None
        self._client = client or httpx.Client(base_url=base_url, timeout=timeout)
        self._max_attempts = max_attempts
        self._base_retry_delay = base_retry_delay
        self._max_retry_delay = max_retry_delay
        self._sleep = sleep_fn or time.sleep

    def __enter__(self) -> KsefHttpClient:
        """Enter the context manager.

        Returns:
            The active HTTP client wrapper.
        """
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        """Exit the context manager and close owned resources."""
        self.close()

    def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._owns_client:
            self._client.close()

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: Mapping[str, Any] | None = None,
        bearer_token: str | None = None,
        content: bytes | None = None,
        accept: str = "application/json",
        timeout: float | None = None,
    ) -> HttpResponse:
        """Send an HTTP request and return the buffered response.

        Args:
            method: HTTP method.
            path: Relative API path.
            json_body: Optional JSON payload.
            bearer_token: Optional bearer token.
            content: Optional raw request body.
            accept: Requested ``Accept`` header value.
            timeout: Optional per-request timeout override.

        Returns:
            Buffered HTTP response.

        Raises:
            KsefApiError: If the request fails or the API returns an error.
        """
        headers: dict[str, str] = {
            "Accept": accept,
        }
        if bearer_token:
            headers["Authorization"] = f"Bearer {bearer_token}"

        body = content
        if json_body is not None:
            body = json.dumps(json_body).encode("utf-8")
            headers["Content-Type"] = "application/json"

        def execute(attempt: int) -> HttpResponse | _RetryDirective:
            self._log_request(method=method, path=path, headers=headers, body=body)
            response = self._client.request(method, path, headers=headers, content=body, timeout=timeout)

            self._log_response(response)

            if response.status_code in RETRYABLE_STATUS_CODES and self._should_retry_request(
                method=method, path=path, attempt=attempt
            ):
                return _RetryDirective(
                    status_code=response.status_code,
                    retry_after=_parse_retry_after_seconds(response.headers.get("Retry-After")),
                )

            if response.is_error:
                self._raise_api_error(response)

            return HttpResponse(
                status_code=response.status_code,
                body=response.content,
                headers=dict(response.headers.items()),
            )

        return self._execute_with_retry(method=method, path=path, operation=execute)

    def request_json(
        self,
        method: str,
        path: str,
        *,
        json_body: Mapping[str, Any] | None = None,
        bearer_token: str | None = None,
        content: bytes | None = None,
        timeout: float | None = None,
    ) -> Any:
        """Send an HTTP request and parse a JSON response body.

        Args:
            method: HTTP method.
            path: Relative API path.
            json_body: Optional JSON payload.
            bearer_token: Optional bearer token.
            content: Optional raw request body.
            timeout: Optional per-request timeout override.

        Returns:
            Parsed JSON payload, or ``None`` for an empty response body.
        """
        response = self.request(
            method,
            path,
            json_body=json_body,
            bearer_token=bearer_token,
            content=content,
            timeout=timeout,
        )
        if not response.body:
            return None

        return json.loads(response.body.decode("utf-8"))

    def request_stream_to_file(
        self,
        method: str,
        path: str,
        *,
        bearer_token: str | None = None,
        content: bytes | None = None,
        accept: str = "application/octet-stream",
        timeout: float | None = None,
    ) -> StreamedHttpResponse:
        """Send an HTTP request and stream the response body into a temporary file.

        Args:
            method: HTTP method.
            path: Relative API path.
            bearer_token: Optional bearer token.
            content: Optional raw request body.
            accept: Requested ``Accept`` header value.
            timeout: Optional per-request timeout override.

        Returns:
            Response metadata and the temporary file path with streamed content.

        Raises:
            KsefApiError: If the request fails or the API returns an error.
        """
        headers: dict[str, str] = {
            "Accept": accept,
        }
        if bearer_token:
            headers["Authorization"] = f"Bearer {bearer_token}"

        def execute(attempt: int) -> StreamedHttpResponse | _RetryDirective:
            self._log_request(method=method, path=path, headers=headers, body=content)

            with self._client.stream(method, path, headers=headers, content=content, timeout=timeout) as response:
                self._logger.debug("HTTP response status: %s", response.status_code)
                self._logger.debug(
                    "Response headers: %s",
                    json.dumps(_redact_headers(dict(response.headers.items())), ensure_ascii=False),
                )

                if response.status_code in RETRYABLE_STATUS_CODES and self._should_retry_request(
                    method=method, path=path, attempt=attempt
                ):
                    return _RetryDirective(
                        status_code=response.status_code,
                        retry_after=_parse_retry_after_seconds(response.headers.get("Retry-After")),
                    )

                if response.is_error:
                    response.read()
                    self._log_response(response)
                    self._raise_api_error(response)

                file_path, content_length = self._stream_response_to_temp_file(response)
                content_type = response.headers.get("Content-Type", "unknown")
                self._logger.debug(
                    "Response body: <streamed content-type=%s length=%s file=%s>",
                    content_type,
                    content_length,
                    file_path,
                )
                return StreamedHttpResponse(
                    status_code=response.status_code,
                    file_path=file_path,
                    headers=dict(response.headers.items()),
                )

        return self._execute_with_retry(method=method, path=path, operation=execute)

    def _execute_with_retry(
        self,
        *,
        method: str,
        path: str,
        operation: Callable[[int], T | _RetryDirective],
    ) -> T:
        """Run a request operation with shared transport and status retry handling."""
        attempt = 1
        while True:
            try:
                result = operation(attempt)
            except httpx.TransportError as error:
                self._logger.debug("HTTP transport error: %s", error)
                if self._should_retry_request(method=method, path=path, attempt=attempt):
                    delay = self._retry_delay_seconds(attempt=attempt)
                    self._logger.warning(
                        "Retrying %s %s after transport error on attempt %s/%s in %.2fs",
                        method,
                        path,
                        attempt,
                        self._max_attempts,
                        delay,
                    )
                    self._sleep(delay)
                    attempt += 1
                    continue
                raise KsefApiError(f"Błąd połączenia z API KSeF: {error}") from error

            if isinstance(result, _RetryDirective):
                delay = self._retry_delay_seconds(attempt=attempt, retry_after=result.retry_after)
                self._logger.warning(
                    "Retrying %s %s after HTTP %s on attempt %s/%s in %.2fs",
                    method,
                    path,
                    result.status_code,
                    attempt,
                    self._max_attempts,
                    delay,
                )
                self._sleep(delay)
                attempt += 1
                continue

            return result

    def _log_request(
        self,
        *,
        method: str,
        path: str,
        headers: dict[str, str],
        body: bytes | None,
    ) -> None:
        """Log an outgoing request with redacted headers and safe body preview.

        Args:
            method: HTTP method.
            path: Relative API path.
            headers: Request headers.
            body: Optional raw request body.
        """
        self._logger.debug("HTTP request: %s %s", method, f"{self._client.base_url}{path.lstrip('/')}")
        self._logger.debug("Request headers: %s", json.dumps(_redact_headers(headers), ensure_ascii=False))
        if body:
            self._logger.debug("Request body: %s", _format_debug_body(body))
            return
        self._logger.debug("Request body: <empty>")

    def _log_response(self, response: httpx.Response) -> None:
        """Log a received response using safe, redacted body formatting.

        Args:
            response: HTTP response object returned by ``httpx``.
        """
        self._logger.debug("HTTP response status: %s", response.status_code)
        self._logger.debug(
            "Response headers: %s",
            json.dumps(_redact_headers(dict(response.headers.items())), ensure_ascii=False),
        )
        if response.content:
            self._logger.debug(
                "Response body: %s",
                _format_response_debug_body(response.content, response.headers.get("Content-Type")),
            )
            return
        self._logger.debug("Response body: <empty>")

    def _raise_api_error(self, response: httpx.Response) -> None:
        """Raise a typed application error from an HTTP response.

        Args:
            response: Error response returned by ``httpx``.

        Raises:
            KsefApiError: Always raised with parsed diagnostic data when available.
        """
        body: Any
        try:
            body = response.json()
        except json.JSONDecodeError:
            body = response.text

        if isinstance(body, dict):
            error_code = body.get("exceptionCode") or body.get("code") or body.get("status")
            description = (
                body.get("exceptionDescription") or body.get("title") or body.get("message") or "Błąd API KSeF"
            )
            details = body.get("details") or body.get("detail") or body.get("errors")
            raise KsefApiError(
                f"HTTP {response.status_code}: {description}",
                status_code=response.status_code,
                error_code=error_code,
                details=details,
                body=body,
            )

        raise KsefApiError(
            f"HTTP {response.status_code}: {body}",
            status_code=response.status_code,
            body=body,
        )

    def _should_retry_request(self, *, method: str, path: str, attempt: int) -> bool:
        """Decide whether a request is retryable.

        Args:
            method: HTTP method.
            path: Relative API path.
            attempt: Current attempt number.

        Returns:
            ``True`` when the request should be retried.
        """
        if attempt >= self._max_attempts:
            return False

        normalized_method = method.upper()
        if normalized_method == "GET":
            return True
        if normalized_method != "POST":
            return False

        normalized_path = path.split("?", 1)[0]
        return normalized_path in RETRYABLE_POST_PATHS

    def _retry_delay_seconds(self, *, attempt: int, retry_after: float | None = None) -> float:
        """Compute the delay before the next retry attempt.

        Args:
            attempt: Current attempt number.
            retry_after: Optional server-provided retry hint.

        Returns:
            Delay in seconds capped by the configured maximum.
        """
        exponential_delay: float = self._base_retry_delay * (2 ** (attempt - 1))
        if exponential_delay > self._max_retry_delay:
            exponential_delay = self._max_retry_delay
        if retry_after is None:
            return exponential_delay
        delay = retry_after if retry_after > exponential_delay else exponential_delay
        if delay > self._max_retry_delay:
            return self._max_retry_delay
        return delay

    def _stream_response_to_temp_file(self, response: httpx.Response) -> tuple[Path, int]:
        """Write a streamed response body into a temporary file.

        Args:
            response: Streaming HTTP response object.

        Returns:
            Tuple of ``(file_path, bytes_written)``.
        """
        file_descriptor, file_name = tempfile.mkstemp(prefix="ksef-link-", suffix=".xml")
        os.close(file_descriptor)
        target_path = Path(file_name)
        bytes_written = 0
        try:
            with target_path.open("wb") as target_file:
                for chunk in response.iter_bytes():
                    target_file.write(chunk)
                    bytes_written += len(chunk)
        except Exception:
            target_path.unlink(missing_ok=True)
            raise
        return target_path, bytes_written


def _redact_headers(headers: dict[str, str]) -> dict[str, str]:
    """Redact sensitive values in HTTP headers.

    Args:
        headers: Raw header mapping.

    Returns:
        Header mapping with sensitive values redacted.
    """
    redacted_headers: dict[str, str] = {}
    for key, value in headers.items():
        if key.lower() == "authorization":
            redacted_headers[key] = REDACTED
        else:
            redacted_headers[key] = value
    return redacted_headers


def _redact_json_value(value: Any, key: str | None = None) -> Any:
    """Recursively redact sensitive keys in a JSON-like structure.

    Args:
        value: JSON-like value to inspect.
        key: Optional key associated with ``value``.

    Returns:
        Redacted value.
    """
    if key is not None and key.lower() in SENSITIVE_KEYS:
        return REDACTED
    if isinstance(value, dict):
        return {nested_key: _redact_json_value(nested_value, nested_key) for nested_key, nested_value in value.items()}
    if isinstance(value, list):
        return [_redact_json_value(item) for item in value]
    return value


def _format_debug_body(body: bytes, max_length: int = 20_000) -> str:
    """Format a request body for safe debug logging.

    Args:
        body: Raw request body.
        max_length: Maximum length of the formatted preview.

    Returns:
        Safe string representation for debug logs.
    """
    if _looks_like_json(body):
        if len(body) > MAX_DEBUG_JSON_BYTES:
            return f"<json body suppressed length={len(body)}>"
        try:
            payload = json.loads(body.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            return f"<json body suppressed length={len(body)}>"
        formatted = json.dumps(_redact_json_value(payload), ensure_ascii=False, indent=2)
    else:
        return f"<body suppressed length={len(body)}>"

    if len(formatted) <= max_length:
        return formatted

    return f"{formatted[:max_length]}\n... <truncated>"


def _format_response_debug_body(
    body: bytes,
    content_type: str | None,
    max_length: int = 20_000,
) -> str:
    """Format a response body for safe debug logging.

    Args:
        body: Raw response body.
        content_type: Optional ``Content-Type`` header value.
        max_length: Maximum length of the formatted preview.

    Returns:
        Safe string representation for debug logs.
    """
    normalized_content_type = (content_type or "").split(";", 1)[0].strip().lower()
    if _should_suppress_response_body(normalized_content_type, body):
        descriptor = normalized_content_type or "unknown"
        return f"<suppressed content-type={descriptor} length={len(body)}>"

    return _format_debug_body(body, max_length=max_length)


def _should_suppress_response_body(content_type: str, body: bytes) -> bool:
    """Decide whether a response body should be suppressed in logs.

    Args:
        content_type: Normalized response content type.
        body: Raw response body preview.

    Returns:
        ``True`` when the body should not be logged verbatim.
    """
    if content_type in {"application/xml", "text/xml", "application/octet-stream"}:
        return True
    if content_type.endswith("+xml"):
        return True

    preview = body.lstrip()[:32]
    if preview.startswith(b"<?xml") or preview.startswith(b"<"):
        return True

    return False


def _looks_like_json(body: bytes) -> bool:
    """Check whether the payload looks like JSON.

    Args:
        body: Raw payload bytes.

    Returns:
        ``True`` when the payload starts like a JSON object or array.
    """
    preview = body.lstrip()[:1]
    return preview in {b"{", b"["}


def _parse_retry_after_seconds(value: str | None) -> float | None:
    """Parse a ``Retry-After`` value expressed in seconds.

    Args:
        value: Raw header value.

    Returns:
        Parsed non-negative delay in seconds, or ``None`` if parsing fails.
    """
    if value is None:
        return None
    try:
        parsed = float(value.strip())
    except ValueError:
        return None
    return max(parsed, 0.0)
