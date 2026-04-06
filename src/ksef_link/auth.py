from __future__ import annotations

import base64
from datetime import UTC, datetime
from typing import Any

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from ksef_link.errors import KsefApiError
from ksef_link.http import KsefHttpClient
from ksef_link.models import (
    AuthChallenge,
    AuthenticatedSession,
    AuthInitResult,
    AuthStatus,
    AuthTokens,
    PublicKeyCertificate,
    TokenInfo,
)

KSEF_TOKEN_ENCRYPTION_USAGE = "KsefTokenEncryption"
SUCCESS_STATUS_CODE = 200
IN_PROGRESS_STATUS_CODE = 100


class KsefAuthService:
    """Authentication-related KSeF operations."""

    def __init__(self, http_client: KsefHttpClient) -> None:
        self._http_client = http_client

    def get_auth_challenge(self) -> AuthChallenge:
        payload = self._http_client.request_json("POST", "/auth/challenge", content=b"")
        return AuthChallenge.from_api(payload)

    def get_public_key_certificates(self) -> list[PublicKeyCertificate]:
        payload = self._http_client.request_json("GET", "/security/public-key-certificates")
        return [PublicKeyCertificate.from_api(item) for item in payload]

    def get_active_encryption_certificate(self) -> PublicKeyCertificate:
        now = datetime.now(UTC)
        matching_certificates = [
            certificate
            for certificate in self.get_public_key_certificates()
            if KSEF_TOKEN_ENCRYPTION_USAGE in certificate.usage
        ]
        if not matching_certificates:
            raise KsefApiError("KSeF nie zwrócił certyfikatu z usage=KsefTokenEncryption.")

        active_certificates = [
            certificate
            for certificate in matching_certificates
            if _parse_datetime(certificate.valid_from) <= now <= _parse_datetime(certificate.valid_to)
        ]
        if active_certificates:
            return max(active_certificates, key=lambda certificate: _parse_datetime(certificate.valid_to))

        return max(matching_certificates, key=lambda certificate: _parse_datetime(certificate.valid_to))

    def encrypt_ksef_token(
        self,
        *,
        ksef_token: str,
        timestamp_ms: int,
        public_certificate_b64: str,
    ) -> str:
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

    def start_token_authentication(
        self,
        *,
        challenge: str,
        context_type: str,
        context_value: str,
        encrypted_token: str,
        authorization_policy: dict[str, Any] | None = None,
    ) -> AuthInitResult:
        payload: dict[str, Any] = {
            "challenge": challenge,
            "contextIdentifier": {
                "type": context_type,
                "value": context_value,
            },
            "encryptedToken": encrypted_token,
        }
        if authorization_policy is not None:
            payload["authorizationPolicy"] = authorization_policy

        response = self._http_client.request_json("POST", "/auth/ksef-token", json_body=payload)
        return AuthInitResult.from_api(response)

    def get_auth_status(
        self,
        *,
        reference_number: str,
        authentication_token: str,
    ) -> AuthStatus:
        payload = self._http_client.request_json(
            "GET",
            f"/auth/{reference_number}",
            bearer_token=authentication_token,
        )
        return AuthStatus.from_api(payload)

    def wait_for_authentication(
        self,
        *,
        reference_number: str,
        authentication_token: str,
        timeout_seconds: float,
        poll_interval: float,
    ) -> AuthStatus:
        start = datetime.now(UTC).timestamp()
        last_status: AuthStatus | None = None

        while datetime.now(UTC).timestamp() - start < timeout_seconds:
            last_status = self.get_auth_status(
                reference_number=reference_number,
                authentication_token=authentication_token,
            )
            if last_status.status.code == SUCCESS_STATUS_CODE:
                return last_status
            if last_status.status.code != IN_PROGRESS_STATUS_CODE:
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

            from time import sleep

            sleep(poll_interval)

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

    def redeem_tokens(self, *, authentication_token: str) -> AuthTokens:
        payload = self._http_client.request_json(
            "POST",
            "/auth/token/redeem",
            bearer_token=authentication_token,
            content=b"",
        )
        return AuthTokens.from_api(payload)

    def refresh_access_token(self, *, refresh_token: str) -> TokenInfo:
        payload = self._http_client.request_json(
            "POST",
            "/auth/token/refresh",
            bearer_token=refresh_token,
            content=b"",
        )
        return TokenInfo.from_api(payload["accessToken"])

    def authenticate_with_ksef_token(
        self,
        *,
        ksef_token: str,
        context_type: str,
        context_value: str,
        authorization_policy: dict[str, Any] | None = None,
        timeout_seconds: float,
        poll_interval: float,
    ) -> AuthenticatedSession:
        challenge = self.get_auth_challenge()
        certificate = self.get_active_encryption_certificate()
        encrypted_token = self.encrypt_ksef_token(
            ksef_token=ksef_token,
            timestamp_ms=challenge.timestamp_ms,
            public_certificate_b64=certificate.certificate,
        )
        init_result = self.start_token_authentication(
            challenge=challenge.challenge,
            context_type=context_type,
            context_value=context_value,
            encrypted_token=encrypted_token,
            authorization_policy=authorization_policy,
        )
        status = self.wait_for_authentication(
            reference_number=init_result.reference_number,
            authentication_token=init_result.authentication_token.token,
            timeout_seconds=timeout_seconds,
            poll_interval=poll_interval,
        )
        tokens = self.redeem_tokens(authentication_token=init_result.authentication_token.token)
        return AuthenticatedSession(
            challenge=challenge,
            certificate=certificate,
            init_result=init_result,
            status=status,
            tokens=tokens,
        )


def _parse_datetime(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed
