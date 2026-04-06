from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from ksef_link.adapters.ksef_api.models import HttpResponse
from ksef_link.shared.errors import KsefApiError

REDACTED = "***REDACTED***"
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
    ) -> None:
        self._logger = logger
        self._owns_client = client is None
        self._client = client or httpx.Client(base_url=base_url, timeout=timeout)

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

        self._log_request(method=method, path=path, headers=headers, body=body)

        try:
            response = self._client.request(method, path, headers=headers, content=body)
        except httpx.HTTPError as error:
            self._logger.debug("HTTP transport error: %s", error)
            raise KsefApiError(f"Błąd połączenia z API KSeF: {error}") from error

        self._log_response(response)

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
            self._logger.debug("Response body: %s", _format_debug_body(response.content))
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
    text = body.decode("utf-8", errors="replace")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        formatted = text
    else:
        formatted = json.dumps(_redact_json_value(payload), ensure_ascii=False, indent=2)

    if len(formatted) <= max_length:
        return formatted

    return f"{formatted[:max_length]}\n... <truncated>"
