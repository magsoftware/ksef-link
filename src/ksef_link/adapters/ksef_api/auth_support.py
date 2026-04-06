"""Support components used by the KSeF authentication adapter."""

from __future__ import annotations

import base64
import time
from collections.abc import Callable
from datetime import UTC, datetime
from enum import IntEnum

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from ksef_link.domain.auth import AuthStatus, PublicKeyCertificate
from ksef_link.shared.errors import KsefApiError

KSEF_TOKEN_ENCRYPTION_USAGE = "KsefTokenEncryption"


class AuthenticationStatusCode(IntEnum):
    """Authentication status codes returned by KSeF."""

    IN_PROGRESS = 100
    SUCCESS = 200


class CertificateSelector:
    """Select the most suitable KSeF encryption certificate."""

    def select_active_encryption_certificate(
        self,
        certificates: list[PublicKeyCertificate],
        *,
        now: datetime | None = None,
    ) -> PublicKeyCertificate:
        """Select the newest active certificate for token encryption.

        Args:
            certificates: Certificates published by KSeF.
            now: Optional current time override used mainly by tests.

        Returns:
            Best matching active certificate.

        Raises:
            KsefApiError: If no suitable active certificate is available.
        """
        current_time = now or datetime.now(UTC)
        matching_certificates = [
            certificate
            for certificate in certificates
            if KSEF_TOKEN_ENCRYPTION_USAGE in certificate.usage
        ]
        if not matching_certificates:
            raise KsefApiError("KSeF nie zwrócił certyfikatu z usage=KsefTokenEncryption.")

        active_certificates = [
            certificate
            for certificate in matching_certificates
            if _parse_datetime(certificate.valid_from) <= current_time <= _parse_datetime(certificate.valid_to)
        ]
        if active_certificates:
            return max(active_certificates, key=lambda certificate: _parse_datetime(certificate.valid_to))

        raise KsefApiError("KSeF nie zwrócił aktywnego certyfikatu z usage=KsefTokenEncryption.")


class TokenEncryptor:
    """Encrypt KSeF token payload with the ministry public key certificate."""

    def encrypt(
        self,
        *,
        ksef_token: str,
        timestamp_ms: int,
        public_certificate_b64: str,
    ) -> str:
        """Encrypt the raw KSeF token payload.

        Args:
            ksef_token: Raw KSeF token.
            timestamp_ms: Challenge timestamp in milliseconds.
            public_certificate_b64: Base64-encoded DER certificate.

        Returns:
            Base64-encoded ciphertext expected by KSeF.

        Raises:
            KsefApiError: If the certificate does not contain an RSA key.
        """
        plaintext = f"{ksef_token}|{timestamp_ms}".encode()
        certificate_der = base64.b64decode(public_certificate_b64)
        certificate = x509.load_der_x509_certificate(certificate_der)
        public_key = certificate.public_key()
        if not isinstance(public_key, rsa.RSAPublicKey):
            raise KsefApiError("Certyfikat klucza publicznego KSeF nie zawiera klucza RSA.")

        encrypted = public_key.encrypt(
            plaintext,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
        return base64.b64encode(encrypted).decode("ascii")


class AuthenticationPoller:
    """Poll KSeF authentication status until success, error or timeout."""

    def __init__(
        self,
        *,
        sleep_fn: Callable[[float], None] | None = None,
        now_fn: Callable[[], float] | None = None,
    ) -> None:
        """Initialize the poller.

        Args:
            sleep_fn: Optional sleep implementation used mainly by tests.
            now_fn: Optional clock implementation used mainly by tests.
        """
        self._sleep = sleep_fn or time.sleep
        self._now = now_fn or (lambda: datetime.now(UTC).timestamp())

    def wait_for_authentication(
        self,
        *,
        reference_number: str,
        authentication_token: str,
        timeout_seconds: float,
        poll_interval: float,
        get_auth_status: Callable[[str, str, float], AuthStatus],
    ) -> AuthStatus:
        """Poll authentication status until success, failure or timeout.

        Args:
            reference_number: Authentication reference number.
            authentication_token: Temporary authentication token.
            timeout_seconds: End-to-end timeout budget for polling.
            poll_interval: Delay between polling attempts.
            get_auth_status: Callback fetching the current auth status.

        Returns:
            Final successful authentication status.

        Raises:
            KsefApiError: If authentication fails or the timeout budget is exhausted.
        """
        start = self._now()
        last_status: AuthStatus | None = None

        while True:
            elapsed = self._now() - start
            remaining_budget = timeout_seconds - elapsed
            if remaining_budget <= 0:
                break

            last_status = get_auth_status(reference_number, authentication_token, remaining_budget)
            if last_status.status.code == AuthenticationStatusCode.SUCCESS:
                return last_status
            if last_status.status.code != AuthenticationStatusCode.IN_PROGRESS:
                raise KsefApiError(
                    "Uwierzytelnienie KSeF zakończyło się błędem.",
                    error_code=last_status.status.code,
                    details=last_status.status.details,
                    body={
                        "code": last_status.status.code,
                        "description": last_status.status.description,
                        "details": last_status.status.details,
                    },
                )

            elapsed = self._now() - start
            remaining_budget = timeout_seconds - elapsed
            if remaining_budget <= 0:
                break

            self._sleep(min(poll_interval, remaining_budget))

        raise KsefApiError(
            "Przekroczono czas oczekiwania na zakończenie uwierzytelnienia.",
            body=(
                {
                    "code": last_status.status.code,
                    "description": last_status.status.description,
                    "details": last_status.status.details,
                }
                if last_status is not None
                else None
            ),
        )


def _parse_datetime(value: str) -> datetime:
    """Parse a KSeF datetime string into an aware ``datetime``.

    Args:
        value: Datetime string returned by KSeF.

    Returns:
        Parsed aware datetime.

    Raises:
        KsefApiError: If the value cannot be parsed.
    """
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise KsefApiError(
            "KSeF zwrócił nieprawidłową wartość daty/czasu.",
            details={"value": value},
        ) from error
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed
