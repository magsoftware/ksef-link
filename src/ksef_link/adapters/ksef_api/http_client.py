from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from typing import Any

import httpx

from ksef_link.adapters.ksef_api.models import HttpResponse
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
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
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
        json_body: dict[str, Any] | None = None,
        bearer_token: str | None = None,
        content: bytes | None = None,
        accept: str = "application/json",
    ) -> HttpResponse:
        """Send an HTTP request and return the raw response."""
        headers: dict[str, str] = {
            "Accept": accept,
        }
        if bearer_token:
            headers["Authorization"] = f"Bearer {bearer_token}"

        body = content
        if json_body is not None:
            body = json.dumps(json_body).encode("utf-8")
            headers["Content-Type"] = "application/json"

        attempt = 1
        while True:
            self._log_request(method=method, path=path, headers=headers, body=body)

            try:
                response = self._client.request(method, path, headers=headers, content=body)
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

            self._log_response(response)

            if (
                response.status_code in RETRYABLE_STATUS_CODES
                and self._should_retry_request(method=method, path=path, attempt=attempt)
            ):
                delay = self._retry_delay_seconds(
                    attempt=attempt,
                    retry_after=_parse_retry_after_seconds(response.headers.get("Retry-After")),
                )
                self._logger.warning(
                    "Retrying %s %s after HTTP %s on attempt %s/%s in %.2fs",
                    method,
                    path,
                    response.status_code,
                    attempt,
                    self._max_attempts,
                    delay,
                )
                self._sleep(delay)
                attempt += 1
                continue

            if response.is_error:
                self._raise_api_error(response)

            return HttpResponse(
                status_code=response.status_code,
                body=response.content,
                headers=dict(response.headers.items()),
            )

    def request_json(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        bearer_token: str | None = None,
        content: bytes | None = None,
    ) -> Any:
        """Send an HTTP request and parse a JSON response body."""
        response = self.request(
            method,
            path,
            json_body=json_body,
            bearer_token=bearer_token,
            content=content,
        )
        if not response.body:
            return None

        return json.loads(response.body.decode("utf-8"))

    def _log_request(
        self,
        *,
        method: str,
        path: str,
        headers: dict[str, str],
        body: bytes | None,
    ) -> None:
        self._logger.debug("HTTP request: %s %s", method, f"{self._client.base_url}{path.lstrip('/')}")
        self._logger.debug("Request headers: %s", json.dumps(_redact_headers(headers), ensure_ascii=False))
        if body:
            self._logger.debug("Request body: %s", _format_debug_body(body))
            return
        self._logger.debug("Request body: <empty>")

    def _log_response(self, response: httpx.Response) -> None:
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
        body: Any
        try:
            body = response.json()
        except json.JSONDecodeError:
            body = response.text

        if isinstance(body, dict):
            error_code = body.get("exceptionCode") or body.get("code") or body.get("status")
            description = (
                body.get("exceptionDescription")
                or body.get("title")
                or body.get("message")
                or "Błąd API KSeF"
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
        exponential_delay: float = self._base_retry_delay * (2 ** (attempt - 1))
        if exponential_delay > self._max_retry_delay:
            exponential_delay = self._max_retry_delay
        if retry_after is None:
            return exponential_delay
        delay = retry_after if retry_after > exponential_delay else exponential_delay
        if delay > self._max_retry_delay:
            return self._max_retry_delay
        return delay


def _redact_headers(headers: dict[str, str]) -> dict[str, str]:
    redacted_headers: dict[str, str] = {}
    for key, value in headers.items():
        if key.lower() == "authorization":
            redacted_headers[key] = REDACTED
        else:
            redacted_headers[key] = value
    return redacted_headers


def _redact_json_value(value: Any, key: str | None = None) -> Any:
    if key is not None and key.lower() in SENSITIVE_KEYS:
        return REDACTED
    if isinstance(value, dict):
        return {
            nested_key: _redact_json_value(nested_value, nested_key)
            for nested_key, nested_value in value.items()
        }
    if isinstance(value, list):
        return [_redact_json_value(item) for item in value]
    return value


def _format_debug_body(body: bytes, max_length: int = 20_000) -> str:
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
    normalized_content_type = (content_type or "").split(";", 1)[0].strip().lower()
    if _should_suppress_response_body(normalized_content_type, body):
        descriptor = normalized_content_type or "unknown"
        return f"<suppressed content-type={descriptor} length={len(body)}>"

    return _format_debug_body(body, max_length=max_length)


def _should_suppress_response_body(content_type: str, body: bytes) -> bool:
    if content_type in {"application/xml", "text/xml", "application/octet-stream"}:
        return True
    if content_type.endswith("+xml"):
        return True

    preview = body.lstrip()[:32]
    if preview.startswith(b"<?xml") or preview.startswith(b"<"):
        return True

    return False


def _looks_like_json(body: bytes) -> bool:
    preview = body.lstrip()[:1]
    return preview in {b"{", b"["}


def _parse_retry_after_seconds(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value.strip())
    except ValueError:
        return None
    return max(parsed, 0.0)
