from __future__ import annotations

import logging

import httpx
import pytest

from ksef_link.errors import KsefApiError
from ksef_link.http import KsefHttpClient, _format_debug_body, _redact_headers, _redact_json_value


def build_http_client(handler: httpx.MockTransport) -> KsefHttpClient:
    client = httpx.Client(base_url="https://api.ksef.mf.gov.pl/v2", timeout=30.0, transport=handler)
    return KsefHttpClient(
        base_url="https://api.ksef.mf.gov.pl/v2",
        timeout=30.0,
        logger=logging.getLogger("test-http"),
        client=client,
    )


def test_request_json_success_and_logging(caplog: pytest.LogCaptureFixture) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={"token": "secret", "value": 1},
            headers={"x-ms-meta-hash": "hash"},
        )
    )
    http_client = build_http_client(transport)

    with caplog.at_level(logging.DEBUG):
        payload = http_client.request_json("POST", "/auth/challenge", json_body={"encryptedToken": "secret"})

    assert payload == {"token": "secret", "value": 1}
    assert "***REDACTED***" in caplog.text


def test_request_returns_raw_http_response() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            content=b"<xml/>",
            headers={"x-ms-meta-hash": "x"},
        )
    )
    http_client = build_http_client(transport)

    response = http_client.request("GET", "/invoices/ksef/1", accept="application/xml")

    assert response.status_code == 200
    assert response.body == b"<xml/>"
    assert response.headers["x-ms-meta-hash"] == "x"


def test_request_json_returns_none_for_empty_body() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=b""))
    http_client = build_http_client(transport)

    payload = http_client.request_json("POST", "/auth/challenge", content=b"")

    assert payload is None


def test_request_raises_api_error_for_json_error_response() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            403,
            json={"title": "Forbidden", "detail": "missing", "status": 403},
        )
    )
    http_client = build_http_client(transport)

    with pytest.raises(KsefApiError) as error:
        http_client.request("GET", "/invoices/query/metadata")

    assert error.value.status_code == 403
    assert error.value.details == "missing"


def test_request_raises_api_error_for_text_error_response() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(500, text="boom"))
    http_client = build_http_client(transport)

    with pytest.raises(KsefApiError) as error:
        http_client.request("GET", "/broken")

    assert error.value.status_code == 500
    assert "boom" in str(error.value)


def test_request_raises_api_error_for_transport_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connect failed", request=request)

    http_client = build_http_client(httpx.MockTransport(handler))

    with pytest.raises(KsefApiError) as error:
        http_client.request("GET", "/auth/challenge")

    assert "Błąd połączenia" in str(error.value)


def test_context_manager_closes_owned_client() -> None:
    http_client = KsefHttpClient(
        base_url="https://api.ksef.mf.gov.pl/v2",
        timeout=30.0,
        logger=logging.getLogger("test-http"),
    )

    with http_client as active_client:
        assert active_client is http_client

    with pytest.raises(RuntimeError):
        http_client.request("GET", "/auth/challenge")


def test_close_does_not_close_injected_client_and_request_adds_authorization_header() -> None:
    captured_headers: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_headers
        captured_headers = dict(request.headers.items())
        return httpx.Response(200, json={"ok": True})

    injected_client = httpx.Client(
        base_url="https://api.ksef.mf.gov.pl/v2",
        timeout=30.0,
        transport=httpx.MockTransport(handler),
    )
    http_client = KsefHttpClient(
        base_url="https://api.ksef.mf.gov.pl/v2",
        timeout=30.0,
        logger=logging.getLogger("test-http"),
        client=injected_client,
    )

    http_client.close()
    payload = http_client.request_json("GET", "/auth/challenge", bearer_token="secret-token")

    assert payload == {"ok": True}
    assert captured_headers["authorization"] == "Bearer secret-token"
    injected_client.close()


def test_redaction_helpers_mask_sensitive_values() -> None:
    assert _redact_headers({"Authorization": "Bearer secret"}) == {"Authorization": "***REDACTED***"}
    assert _redact_json_value({"token": "secret", "items": [{"refreshToken": "x"}]}) == {
        "token": "***REDACTED***",
        "items": [{"refreshToken": "***REDACTED***"}],
    }
    assert _format_debug_body(b'{"token":"secret","value":1}').count("***REDACTED***") == 1
    assert _format_debug_body(b"plain-text") == "plain-text"
    assert "... <truncated>" in _format_debug_body(b"a" * 21000)
