from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from ksef_link.auth import KsefAuthService, _parse_datetime
from ksef_link.errors import KsefApiError
from ksef_link.models import (
    AuthChallenge,
    AuthenticationMethodInfo,
    AuthInitResult,
    AuthStatus,
    AuthTokens,
    PublicKeyCertificate,
    StatusInfo,
)


class StubHttpClient:
    def __init__(self, responses: dict[tuple[str, str], Any]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    def request_json(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        bearer_token: str | None = None,
        content: bytes | None = None,
    ) -> Any:
        self.calls.append((method, path, {"json_body": json_body, "bearer_token": bearer_token, "content": content}))
        return self.responses[(method, path)]


def build_certificate_b64() -> str:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test")])
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(UTC) - timedelta(days=1))
        .not_valid_after(datetime.now(UTC) + timedelta(days=30))
        .sign(private_key, hashes.SHA256())
    )
    return base64.b64encode(certificate.public_bytes(serialization.Encoding.DER)).decode("ascii")


def build_auth_status(code: int, description: str, details: list[str] | None = None) -> AuthStatus:
    return AuthStatus(
        start_date="2026-04-06T12:00:00+02:00",
        authentication_method="Token",
        authentication_method_info=AuthenticationMethodInfo(
            category="Token",
            code="token.ksef",
            display_name="Token KSeF",
        ),
        status=StatusInfo(code=code, description=description, details=details),
    )


def test_get_auth_challenge_and_token_related_methods() -> None:
    http_client = StubHttpClient(
        {
            ("POST", "/auth/challenge"): {
                "challenge": "challenge",
                "timestamp": "2026-04-06T12:00:00+02:00",
                "timestampMs": 1,
                "clientIp": "127.0.0.1",
            },
            ("POST", "/auth/ksef-token"): {
                "referenceNumber": "ref",
                "authenticationToken": {
                    "token": "auth",
                    "validUntil": "2026-04-06T12:00:00+02:00",
                },
            },
            ("GET", "/auth/ref"): {
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
            },
            ("POST", "/auth/token/redeem"): {
                "accessToken": {"token": "access", "validUntil": "2026-04-06T12:00:00+02:00"},
                "refreshToken": {"token": "refresh", "validUntil": "2026-05-06T12:00:00+02:00"},
            },
            ("POST", "/auth/token/refresh"): {
                "accessToken": {"token": "access2", "validUntil": "2026-04-07T12:00:00+02:00"},
            },
        }
    )
    service = KsefAuthService(http_client)  # type: ignore[arg-type]

    challenge = service.get_auth_challenge()
    init_result = service.start_token_authentication(
        challenge="challenge",
        context_type="Nip",
        context_value="6771086988",
        encrypted_token="encrypted",
        authorization_policy={"allowedIps": {"ip4Addresses": ["127.0.0.1"]}},
    )
    status = service.get_auth_status(reference_number="ref", authentication_token="auth")
    tokens = service.redeem_tokens(authentication_token="auth")
    refreshed = service.refresh_access_token(refresh_token="refresh")

    assert challenge.client_ip == "127.0.0.1"
    assert init_result.reference_number == "ref"
    assert status.status.code == 200
    assert tokens.access_token.token == "access"
    assert refreshed.token == "access2"


def test_get_public_key_certificates_and_active_selection() -> None:
    http_client = StubHttpClient(
        {
            ("GET", "/security/public-key-certificates"): [
                {
                    "certificate": "first",
                    "validFrom": "2026-04-01T00:00:00+00:00",
                    "validTo": "2026-04-10T00:00:00+00:00",
                    "usage": ["KsefTokenEncryption"],
                },
                {
                    "certificate": "second",
                    "validFrom": "2026-04-01T00:00:00+00:00",
                    "validTo": "2026-04-20T00:00:00+00:00",
                    "usage": ["KsefTokenEncryption"],
                },
            ]
        }
    )
    service = KsefAuthService(http_client)  # type: ignore[arg-type]

    certificates = service.get_public_key_certificates()
    selected = service.get_active_encryption_certificate()

    assert len(certificates) == 2
    assert selected.certificate == "second"


def test_get_active_encryption_certificate_falls_back_to_latest_inactive() -> None:
    http_client = StubHttpClient(
        {
            ("GET", "/security/public-key-certificates"): [
                {
                    "certificate": "older",
                    "validFrom": "2025-04-01T00:00:00+00:00",
                    "validTo": "2025-04-10T00:00:00+00:00",
                    "usage": ["KsefTokenEncryption"],
                },
                {
                    "certificate": "newer",
                    "validFrom": "2025-04-01T00:00:00+00:00",
                    "validTo": "2025-04-20T00:00:00+00:00",
                    "usage": ["KsefTokenEncryption"],
                },
            ]
        }
    )
    service = KsefAuthService(http_client)  # type: ignore[arg-type]

    selected = service.get_active_encryption_certificate()

    assert selected.certificate == "newer"


def test_get_active_encryption_certificate_raises_when_usage_missing() -> None:
    http_client = StubHttpClient(
        {
            ("GET", "/security/public-key-certificates"): [
                {
                    "certificate": "x",
                    "validFrom": "2026-04-01T00:00:00+00:00",
                    "validTo": "2026-04-20T00:00:00+00:00",
                    "usage": ["SymmetricKeyEncryption"],
                }
            ]
        }
    )
    service = KsefAuthService(http_client)  # type: ignore[arg-type]

    with pytest.raises(KsefApiError):
        service.get_active_encryption_certificate()


def test_encrypt_ksef_token_produces_ciphertext() -> None:
    service = KsefAuthService(StubHttpClient({}))  # type: ignore[arg-type]

    encrypted = service.encrypt_ksef_token(
        ksef_token="secret-token",
        timestamp_ms=123,
        public_certificate_b64=build_certificate_b64(),
    )

    assert isinstance(encrypted, str)
    assert encrypted != "secret-token|123"


def test_start_token_authentication_omits_authorization_policy_when_not_provided() -> None:
    http_client = StubHttpClient(
        {
            ("POST", "/auth/ksef-token"): {
                "referenceNumber": "ref",
                "authenticationToken": {
                    "token": "auth",
                    "validUntil": "2026-04-06T12:00:00+02:00",
                },
            }
        }
    )
    service = KsefAuthService(http_client)  # type: ignore[arg-type]

    result = service.start_token_authentication(
        challenge="challenge",
        context_type="Nip",
        context_value="6771086988",
        encrypted_token="encrypted",
    )

    assert result.reference_number == "ref"
    assert http_client.calls[0][2]["json_body"] == {
        "challenge": "challenge",
        "contextIdentifier": {
            "type": "Nip",
            "value": "6771086988",
        },
        "encryptedToken": "encrypted",
    }


def test_encrypt_ksef_token_raises_for_non_rsa_key(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeKey:
        pass

    class FakeCertificate:
        def public_key(self) -> object:
            return FakeKey()

    service = KsefAuthService(StubHttpClient({}))  # type: ignore[arg-type]
    monkeypatch.setattr("ksef_link.auth.x509.load_der_x509_certificate", lambda data: FakeCertificate())

    with pytest.raises(KsefApiError):
        service.encrypt_ksef_token(ksef_token="secret", timestamp_ms=1, public_certificate_b64="YQ==")


def test_wait_for_authentication_returns_success_after_in_progress(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = KsefAuthService(StubHttpClient({}))  # type: ignore[arg-type]
    statuses = [
        build_auth_status(100, "w toku"),
        build_auth_status(200, "ok"),
    ]

    monkeypatch.setattr(service, "get_auth_status", lambda **kwargs: statuses.pop(0))
    monkeypatch.setattr("time.sleep", lambda seconds: None)

    status = service.wait_for_authentication(
        reference_number="ref",
        authentication_token="token",
        timeout_seconds=10.0,
        poll_interval=0.0,
    )

    assert status.status.code == 200


def test_wait_for_authentication_raises_for_failed_status(monkeypatch: pytest.MonkeyPatch) -> None:
    service = KsefAuthService(StubHttpClient({}))  # type: ignore[arg-type]
    monkeypatch.setattr(service, "get_auth_status", lambda **kwargs: build_auth_status(450, "bad", ["detail"]))

    with pytest.raises(KsefApiError) as error:
        service.wait_for_authentication(
            reference_number="ref",
            authentication_token="token",
            timeout_seconds=10.0,
            poll_interval=0.0,
        )

    assert error.value.error_code == 450


def test_wait_for_authentication_raises_timeout_without_status() -> None:
    service = KsefAuthService(StubHttpClient({}))  # type: ignore[arg-type]

    with pytest.raises(KsefApiError) as error:
        service.wait_for_authentication(
            reference_number="ref",
            authentication_token="token",
            timeout_seconds=0.0,
            poll_interval=0.0,
        )

    assert error.value.body is None


def test_authenticate_with_ksef_token_orchestrates_complete_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    service = KsefAuthService(StubHttpClient({}))  # type: ignore[arg-type]
    challenge = AuthChallenge.from_api(
        {
            "challenge": "challenge",
            "timestamp": "2026-04-06T12:00:00+02:00",
            "timestampMs": 1,
            "clientIp": "127.0.0.1",
        }
    )
    certificate = PublicKeyCertificate.from_api(
        {
            "certificate": "certificate",
            "validFrom": "2026-04-01T00:00:00+00:00",
            "validTo": "2027-04-01T00:00:00+00:00",
            "usage": ["KsefTokenEncryption"],
        }
    )
    init_result = AuthInitResult.from_api(
        {
            "referenceNumber": "ref",
            "authenticationToken": {"token": "auth", "validUntil": "2026-04-06T12:00:00+02:00"},
        }
    )
    status = build_auth_status(200, "OK")
    tokens = AuthTokens.from_api(
        {
            "accessToken": {"token": "access", "validUntil": "2026-04-06T12:00:00+02:00"},
            "refreshToken": {"token": "refresh", "validUntil": "2026-05-06T12:00:00+02:00"},
        }
    )

    monkeypatch.setattr(service, "get_auth_challenge", lambda: challenge)
    monkeypatch.setattr(service, "get_active_encryption_certificate", lambda: certificate)
    monkeypatch.setattr(service, "encrypt_ksef_token", lambda **kwargs: "encrypted")
    monkeypatch.setattr(service, "start_token_authentication", lambda **kwargs: init_result)
    monkeypatch.setattr(service, "wait_for_authentication", lambda **kwargs: status)
    monkeypatch.setattr(service, "redeem_tokens", lambda **kwargs: tokens)

    session = service.authenticate_with_ksef_token(
        ksef_token="secret",
        context_type="Nip",
        context_value="6771086988",
        authorization_policy={"allowedIps": {"ip4Addresses": ["127.0.0.1"]}},
        timeout_seconds=60.0,
        poll_interval=1.0,
    )

    assert session.tokens.access_token.token == "access"
    assert session.status.status.code == 200


def test_parse_datetime_handles_z_and_naive_values() -> None:
    assert _parse_datetime("2026-04-06T12:00:00Z").tzinfo is UTC
    assert _parse_datetime("2026-04-06T12:00:00").tzinfo is UTC
