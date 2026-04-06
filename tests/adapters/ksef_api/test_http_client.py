from __future__ import annotations

import logging
import os
import tempfile
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from ksef_link.adapters.ksef_api.http_client import (
    KsefHttpClient,
    _format_debug_body,
    _format_response_debug_body,
    _parse_retry_after_seconds,
    _redact_headers,
    _redact_json_value,
)
from ksef_link.shared.errors import KsefApiError


def build_http_client(
    handler: httpx.MockTransport,
    *,
    sleep_fn: Callable[[float], None] | None = None,
    max_attempts: int = 3,
) -> KsefHttpClient:
    client = httpx.Client(base_url="https://api.ksef.mf.gov.pl/v2", timeout=30.0, transport=handler)
    return KsefHttpClient(
        base_url="https://api.ksef.mf.gov.pl/v2",
        timeout=30.0,
        logger=logging.getLogger("test-http"),
        client=client,
        sleep_fn=sleep_fn,
        max_attempts=max_attempts,
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


def test_request_stream_to_file_writes_response_body_to_temp_file() -> None:
    captured_headers: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_headers
        captured_headers = dict(request.headers.items())
        return httpx.Response(
            200,
            content=b"<xml/>",
            headers={"Content-Type": "application/xml", "x-ms-meta-hash": "hash1"},
        )

    transport = httpx.MockTransport(
        handler
    )
    http_client = build_http_client(transport)

    response = http_client.request_stream_to_file(
        "GET",
        "/invoices/ksef/1",
        bearer_token="secret-token",
        accept="application/xml",
    )

    try:
        assert response.status_code == 200
        assert response.headers["x-ms-meta-hash"] == "hash1"
        assert captured_headers["authorization"] == "Bearer secret-token"
        assert response.file_path.exists()
        assert response.file_path.read_bytes() == b"<xml/>"
    finally:
        response.file_path.unlink(missing_ok=True)


def test_request_stream_to_file_retries_transport_error_for_get_and_then_succeeds() -> None:
    calls = 0
    sleep_calls: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ReadTimeout("timed out", request=request)
        return httpx.Response(200, content=b"<xml/>", headers={"Content-Type": "application/xml"})

    http_client = build_http_client(httpx.MockTransport(handler), sleep_fn=sleep_calls.append)

    response = http_client.request_stream_to_file("GET", "/invoices/ksef/1", accept="application/xml")

    try:
        assert calls == 2
        assert sleep_calls == [0.5]
        assert response.file_path.read_bytes() == b"<xml/>"
    finally:
        response.file_path.unlink(missing_ok=True)


def test_request_stream_to_file_retries_retryable_status_and_honors_retry_after() -> None:
    calls = 0
    sleep_calls: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503, content=b"busy", headers={"Retry-After": "1.5"})
        return httpx.Response(200, content=b"<xml/>", headers={"Content-Type": "application/xml"})

    http_client = build_http_client(httpx.MockTransport(handler), sleep_fn=sleep_calls.append)

    response = http_client.request_stream_to_file("GET", "/invoices/ksef/1", accept="application/xml")

    try:
        assert calls == 2
        assert sleep_calls == [1.5]
        assert response.file_path.read_bytes() == b"<xml/>"
    finally:
        response.file_path.unlink(missing_ok=True)


def test_request_stream_to_file_raises_api_error_for_error_response() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            500,
            json={"title": "Broken", "detail": "stream failed", "status": 500},
        )
    )
    http_client = build_http_client(transport)

    with pytest.raises(KsefApiError) as error:
        http_client.request_stream_to_file("GET", "/invoices/ksef/1", accept="application/xml")

    assert error.value.status_code == 500
    assert error.value.details == "stream failed"


def test_request_stream_to_file_raises_api_error_for_non_retryable_transport_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connect failed", request=request)

    http_client = build_http_client(httpx.MockTransport(handler))

    with pytest.raises(KsefApiError) as error:
        http_client.request_stream_to_file("POST", "/auth/token/redeem", content=b"payload")

    assert "Błąd połączenia" in str(error.value)


def test_stream_response_to_temp_file_cleans_up_partial_file_on_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    target_path = tmp_path / "partial.xml"

    def fake_mkstemp(*, prefix: str, suffix: str) -> tuple[int, str]:
        file_descriptor = os.open(
            str(target_path),
            os.O_CREAT | os.O_RDWR,
            0o600,
        )
        return file_descriptor, str(target_path)

    class FailingResponse:
        def iter_bytes(self) -> object:
            raise RuntimeError("stream failed")

    monkeypatch.setattr(tempfile, "mkstemp", fake_mkstemp)

    http_client = build_http_client(httpx.MockTransport(lambda request: httpx.Response(200)))

    with pytest.raises(RuntimeError, match="stream failed"):
        http_client._stream_response_to_temp_file(FailingResponse())  # type: ignore[arg-type]

    assert not target_path.exists()


def test_response_logging_suppresses_xml_body_in_debug_mode(caplog: pytest.LogCaptureFixture) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            content=b"<Invoice><Seller>Name</Seller></Invoice>",
            headers={"Content-Type": "application/xml", "x-ms-meta-hash": "x"},
        )
    )
    http_client = build_http_client(transport)

    with caplog.at_level(logging.DEBUG):
        http_client.request("GET", "/invoices/ksef/1", accept="application/xml")

    assert "<Invoice>" not in caplog.text
    assert "<suppressed content-type=application/xml length=" in caplog.text


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


def test_request_retries_transport_error_for_get_and_then_succeeds() -> None:
    calls = 0
    sleep_calls: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ConnectError("connect failed", request=request)
        return httpx.Response(200, json={"ok": True})

    http_client = build_http_client(httpx.MockTransport(handler), sleep_fn=sleep_calls.append)

    payload = http_client.request_json("GET", "/auth/challenge")

    assert payload == {"ok": True}
    assert calls == 2
    assert sleep_calls == [0.5]


def test_request_retries_retryable_post_for_503_and_honors_retry_after() -> None:
    calls = 0
    sleep_calls: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503, json={"title": "Busy"}, headers={"Retry-After": "1.5"})
        return httpx.Response(200, json={"challenge": "ok"})

    http_client = build_http_client(httpx.MockTransport(handler), sleep_fn=sleep_calls.append)

    payload = http_client.request_json("POST", "/auth/challenge", content=b"")

    assert payload == {"challenge": "ok"}
    assert calls == 2
    assert sleep_calls == [1.5]


def test_request_does_not_retry_non_retryable_post() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503, json={"title": "Busy"})

    http_client = build_http_client(httpx.MockTransport(handler))

    with pytest.raises(KsefApiError) as error:
        http_client.request("POST", "/auth/token/redeem", content=b"")

    assert error.value.status_code == 503
    assert calls == 1


def test_request_does_not_retry_non_retryable_method() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503, json={"title": "Busy"})

    http_client = build_http_client(httpx.MockTransport(handler))

    with pytest.raises(KsefApiError) as error:
        http_client.request("PUT", "/auth/challenge", content=b"")

    assert error.value.status_code == 503
    assert calls == 1


def test_http_client_rejects_invalid_max_attempts() -> None:
    with pytest.raises(ValueError):
        KsefHttpClient(
            base_url="https://api.ksef.mf.gov.pl/v2",
            timeout=30.0,
            logger=logging.getLogger("test-http"),
            max_attempts=0,
        )


def test_retry_delay_seconds_caps_exponential_and_retry_after_values() -> None:
    http_client = KsefHttpClient(
        base_url="https://api.ksef.mf.gov.pl/v2",
        timeout=30.0,
        logger=logging.getLogger("test-http"),
        max_attempts=3,
        base_retry_delay=5.0,
        max_retry_delay=2.0,
    )

    assert http_client._retry_delay_seconds(attempt=2) == 2.0
    assert http_client._retry_delay_seconds(attempt=1, retry_after=10.0) == 2.0


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
    assert "... <truncated>" in _format_debug_body(b'{"value":"' + (b"a" * 1000) + b'"}', max_length=50)
    assert _format_debug_body(b"plain-text") == "<body suppressed length=10>"
    assert _format_debug_body(b'{"token":') == "<json body suppressed length=9>"
    assert _format_debug_body(b'{"data":"' + (b"a" * 17000) + b'"}').startswith("<json body suppressed length=")
    assert _format_response_debug_body(b"<xml/>", "application/xml").startswith(
        "<suppressed content-type=application/xml"
    )
    assert _format_response_debug_body(b"<xml/>", "application/problem+xml").startswith(
        "<suppressed content-type=application/problem+xml"
    )
    assert _format_response_debug_body(b'{"token":"secret"}', "application/json").count("***REDACTED***") == 1
    assert _format_response_debug_body(b"<xml/>", None).startswith("<suppressed content-type=unknown")
    assert _parse_retry_after_seconds("2.5") == 2.5
    assert _parse_retry_after_seconds("bad") is None
    assert _parse_retry_after_seconds(None) is None
