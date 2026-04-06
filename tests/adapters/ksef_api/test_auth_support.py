from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from ksef_link.adapters.ksef_api.auth_support import (
    AuthenticationPoller,
    CertificateSelector,
    TokenEncryptor,
    _parse_datetime,
)
from ksef_link.domain.auth import AuthenticationMethodInfo, AuthStatus, PublicKeyCertificate, StatusInfo
from ksef_link.shared.errors import KsefApiError


def _build_certificate_b64() -> str:
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


def _build_public_certificate(
    *,
    certificate: str,
    valid_from: str,
    valid_to: str,
    usage: list[str],
) -> PublicKeyCertificate:
    return PublicKeyCertificate(
        certificate=certificate,
        valid_from=valid_from,
        valid_to=valid_to,
        usage=usage,
    )


def _build_auth_status(code: int, description: str, details: list[str] | None = None) -> AuthStatus:
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


def test_certificate_selector_prefers_latest_active_certificate() -> None:
    selector = CertificateSelector()

    selected = selector.select_active_encryption_certificate(
        [
            _build_public_certificate(
                certificate="older",
                valid_from="2026-04-01T00:00:00+00:00",
                valid_to="2026-04-10T00:00:00+00:00",
                usage=["KsefTokenEncryption"],
            ),
            _build_public_certificate(
                certificate="newer",
                valid_from="2026-04-01T00:00:00+00:00",
                valid_to="2026-04-20T00:00:00+00:00",
                usage=["KsefTokenEncryption"],
            ),
        ],
        now=datetime(2026, 4, 6, tzinfo=UTC),
    )

    assert selected.certificate == "newer"


def test_certificate_selector_raises_when_only_inactive_certificates_are_available() -> None:
    selector = CertificateSelector()

    with pytest.raises(KsefApiError):
        selector.select_active_encryption_certificate(
            [
                _build_public_certificate(
                    certificate="older",
                    valid_from="2025-04-01T00:00:00+00:00",
                    valid_to="2025-04-10T00:00:00+00:00",
                    usage=["KsefTokenEncryption"],
                ),
                _build_public_certificate(
                    certificate="newer",
                    valid_from="2025-04-01T00:00:00+00:00",
                    valid_to="2025-04-20T00:00:00+00:00",
                    usage=["KsefTokenEncryption"],
                ),
            ],
            now=datetime(2026, 4, 6, tzinfo=UTC),
        )


def test_certificate_selector_raises_when_usage_missing() -> None:
    selector = CertificateSelector()

    with pytest.raises(KsefApiError):
        selector.select_active_encryption_certificate(
            [
                _build_public_certificate(
                    certificate="x",
                    valid_from="2026-04-01T00:00:00+00:00",
                    valid_to="2026-04-20T00:00:00+00:00",
                    usage=["SymmetricKeyEncryption"],
                )
            ]
        )


def test_token_encryptor_produces_ciphertext() -> None:
    encryptor = TokenEncryptor()

    encrypted = encryptor.encrypt(
        ksef_token="secret-token",
        timestamp_ms=123,
        public_certificate_b64=_build_certificate_b64(),
    )

    assert isinstance(encrypted, str)
    assert encrypted != "secret-token|123"


def test_token_encryptor_raises_for_non_rsa_key(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeKey:
        pass

    class FakeCertificate:
        def public_key(self) -> object:
            return FakeKey()

    encryptor = TokenEncryptor()
    monkeypatch.setattr(
        "ksef_link.adapters.ksef_api.auth_support.x509.load_der_x509_certificate",
        lambda data: FakeCertificate(),
    )

    with pytest.raises(KsefApiError):
        encryptor.encrypt(ksef_token="secret", timestamp_ms=1, public_certificate_b64="YQ==")


def test_authentication_poller_returns_success_after_in_progress() -> None:
    now_values = iter([0.0, 0.0, 0.5, 1.0])
    sleep_calls: list[float] = []
    request_timeouts: list[float] = []
    poller = AuthenticationPoller(sleep_fn=sleep_calls.append, now_fn=lambda: next(now_values))
    statuses = iter([_build_auth_status(100, "w toku"), _build_auth_status(200, "ok")])

    def get_auth_status(ref: str, token: str, timeout: float) -> AuthStatus:
        request_timeouts.append(timeout)
        return next(statuses)

    status = poller.wait_for_authentication(
        reference_number="ref",
        authentication_token="token",
        timeout_seconds=10.0,
        poll_interval=1.5,
        get_auth_status=get_auth_status,
    )

    assert status.status.code == 200
    assert sleep_calls == [1.5]
    assert request_timeouts == [10.0, 9.0]


def test_authentication_poller_raises_for_failed_status() -> None:
    poller = AuthenticationPoller(sleep_fn=lambda seconds: None, now_fn=lambda: 0.0)

    with pytest.raises(KsefApiError) as error:
        poller.wait_for_authentication(
            reference_number="ref",
            authentication_token="token",
            timeout_seconds=10.0,
            poll_interval=0.0,
            get_auth_status=lambda ref, token, timeout: _build_auth_status(450, "bad", ["detail"]),
        )

    assert error.value.error_code == 450


def test_authentication_poller_raises_timeout_without_status() -> None:
    now_values = iter([0.0, 0.0, 1.0])
    poller = AuthenticationPoller(sleep_fn=lambda seconds: None, now_fn=lambda: next(now_values))

    with pytest.raises(KsefApiError) as error:
        poller.wait_for_authentication(
            reference_number="ref",
            authentication_token="token",
            timeout_seconds=0.0,
            poll_interval=0.0,
            get_auth_status=lambda ref, token, timeout: _build_auth_status(100, "w toku"),
        )

    assert error.value.body is None


def test_authentication_poller_caps_sleep_to_remaining_budget() -> None:
    now_values = iter([0.0, 0.5, 4.0, 5.0])
    sleep_calls: list[float] = []
    poller = AuthenticationPoller(sleep_fn=sleep_calls.append, now_fn=lambda: next(now_values))

    with pytest.raises(KsefApiError):
        poller.wait_for_authentication(
            reference_number="ref",
            authentication_token="token",
            timeout_seconds=5.0,
            poll_interval=10.0,
            get_auth_status=lambda ref, token, timeout: _build_auth_status(100, "w toku"),
        )

    assert sleep_calls == [1.0]


def test_authentication_poller_raises_timeout_after_request_consumes_budget() -> None:
    now_values = iter([0.0, 0.0, 5.0])
    sleep_calls: list[float] = []
    poller = AuthenticationPoller(sleep_fn=sleep_calls.append, now_fn=lambda: next(now_values))

    with pytest.raises(KsefApiError) as error:
        poller.wait_for_authentication(
            reference_number="ref",
            authentication_token="token",
            timeout_seconds=5.0,
            poll_interval=10.0,
            get_auth_status=lambda ref, token, timeout: _build_auth_status(100, "w toku"),
        )

    assert error.value.body == {
        "code": 100,
        "description": "w toku",
        "details": None,
    }
    assert sleep_calls == []


def test_parse_datetime_supports_zulu_and_naive() -> None:
    assert _parse_datetime("2026-04-06T10:15:00Z").tzinfo is not None
    assert _parse_datetime("2026-04-06T10:15:00").tzinfo is not None


def test_parse_datetime_raises_ksef_api_error_for_invalid_value() -> None:
    with pytest.raises(KsefApiError) as error:
        _parse_datetime("not-a-date")

    assert error.value.details == {"value": "not-a-date"}
