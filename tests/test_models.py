from __future__ import annotations

from pathlib import Path

from ksef_link.models import (
    AuthChallenge,
    AuthenticationMethodInfo,
    AuthInitResult,
    AuthStatus,
    AuthTokens,
    CliOptions,
    HttpResponse,
    InvoiceDownload,
    InvoiceQueryResult,
    PublicKeyCertificate,
    RuntimeOptions,
    StatusInfo,
    TokenInfo,
)


def test_token_info_from_api() -> None:
    token_info = TokenInfo.from_api({"token": "abc", "validUntil": "2026-04-06T12:00:00+02:00"})

    assert token_info.token == "abc"
    assert token_info.valid_until == "2026-04-06T12:00:00+02:00"


def test_status_info_from_api_with_details() -> None:
    status_info = StatusInfo.from_api({"code": "200", "description": "OK", "details": ["a", "b"]})

    assert status_info.code == 200
    assert status_info.description == "OK"
    assert status_info.details == ["a", "b"]


def test_authentication_method_info_from_api() -> None:
    method_info = AuthenticationMethodInfo.from_api(
        {"category": "Token", "code": "token.ksef", "displayName": "Token KSeF"}
    )

    assert method_info.category == "Token"
    assert method_info.code == "token.ksef"
    assert method_info.display_name == "Token KSeF"


def test_auth_challenge_from_api() -> None:
    challenge = AuthChallenge.from_api(
        {
            "challenge": "challenge",
            "timestamp": "2026-04-06T12:00:00+02:00",
            "timestampMs": 123,
            "clientIp": "127.0.0.1",
        }
    )

    assert challenge.challenge == "challenge"
    assert challenge.timestamp_ms == 123
    assert challenge.client_ip == "127.0.0.1"


def test_public_key_certificate_from_api() -> None:
    certificate = PublicKeyCertificate.from_api(
        {
            "certificate": "base64",
            "validFrom": "2026-04-01T00:00:00+02:00",
            "validTo": "2027-04-01T00:00:00+02:00",
            "usage": ["KsefTokenEncryption"],
        }
    )

    assert certificate.certificate == "base64"
    assert certificate.usage == ["KsefTokenEncryption"]


def test_auth_init_result_from_api() -> None:
    init_result = AuthInitResult.from_api(
        {
            "referenceNumber": "ref",
            "authenticationToken": {
                "token": "token",
                "validUntil": "2026-04-06T12:00:00+02:00",
            },
        }
    )

    assert init_result.reference_number == "ref"
    assert init_result.authentication_token.token == "token"


def test_auth_status_from_api() -> None:
    auth_status = AuthStatus.from_api(
        {
            "startDate": "2026-04-06T12:00:00+02:00",
            "authenticationMethod": "Token",
            "authenticationMethodInfo": {
                "category": "Token",
                "code": "token.ksef",
                "displayName": "Token KSeF",
            },
            "status": {
                "code": 200,
                "description": "OK",
            },
            "isTokenRedeemed": True,
            "lastTokenRefreshDate": "2026-04-06T12:30:00+02:00",
            "refreshTokenValidUntil": "2026-05-06T12:00:00+02:00",
        }
    )

    assert auth_status.authentication_method == "Token"
    assert auth_status.authentication_method_info.display_name == "Token KSeF"
    assert auth_status.status.code == 200
    assert auth_status.is_token_redeemed is True


def test_auth_tokens_from_api() -> None:
    auth_tokens = AuthTokens.from_api(
        {
            "accessToken": {
                "token": "access",
                "validUntil": "2026-04-06T12:00:00+02:00",
            },
            "refreshToken": {
                "token": "refresh",
                "validUntil": "2026-05-06T12:00:00+02:00",
            },
        }
    )

    assert auth_tokens.access_token.token == "access"
    assert auth_tokens.refresh_token.token == "refresh"


def test_misc_dataclasses_store_values() -> None:
    runtime = RuntimeOptions(base_url="https://api.ksef.mf.gov.pl/v2", timeout=30.0, debug=True, env_file=Path(".env"))
    cli_options = CliOptions(runtime=runtime, command="command")  # type: ignore[arg-type]
    query_result = InvoiceQueryResult(
        has_more=False,
        is_truncated=False,
        permanent_storage_hwm_date=None,
        pages_fetched=1,
        invoices=[],
    )
    invoice_download = InvoiceDownload(ksef_number="ksef", content=b"<xml/>", content_hash="hash")
    response = HttpResponse(status_code=200, body=b"{}", headers={"Content-Type": "application/json"})

    assert cli_options.runtime.debug is True
    assert query_result.pages_fetched == 1
    assert invoice_download.content == b"<xml/>"
    assert response.status_code == 200
