from __future__ import annotations

from typing import Any

from ksef_link.adapters.ksef_api.auth_support import (
    AuthenticationPoller,
    CertificateSelector,
    TokenEncryptor,
)
from ksef_link.adapters.ksef_api.http_client import KsefHttpClient
from ksef_link.domain.auth import (
    AuthChallenge,
    AuthenticatedSession,
    AuthInitResult,
    AuthStatus,
    AuthTokens,
    PublicKeyCertificate,
    TokenInfo,
)


class KsefAuthService:
    """KSeF authentication gateway adapter."""

    def __init__(
        self,
        http_client: KsefHttpClient,
        *,
        certificate_selector: CertificateSelector | None = None,
        token_encryptor: TokenEncryptor | None = None,
        authentication_poller: AuthenticationPoller | None = None,
    ) -> None:
        self._http_client = http_client
        self._certificate_selector = certificate_selector or CertificateSelector()
        self._token_encryptor = token_encryptor or TokenEncryptor()
        self._authentication_poller = authentication_poller or AuthenticationPoller()

    def get_auth_challenge(self) -> AuthChallenge:
        payload = self._http_client.request_json("POST", "/auth/challenge", content=b"")
        return AuthChallenge.from_api(payload)

    def get_public_key_certificates(self) -> list[PublicKeyCertificate]:
        payload = self._http_client.request_json("GET", "/security/public-key-certificates")
        return [PublicKeyCertificate.from_api(item) for item in payload]

    def get_active_encryption_certificate(self) -> PublicKeyCertificate:
        return self._certificate_selector.select_active_encryption_certificate(self.get_public_key_certificates())

    def encrypt_ksef_token(
        self,
        *,
        ksef_token: str,
        timestamp_ms: int,
        public_certificate_b64: str,
    ) -> str:
        return self._token_encryptor.encrypt(
            ksef_token=ksef_token,
            timestamp_ms=timestamp_ms,
            public_certificate_b64=public_certificate_b64,
        )

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
        timeout: float | None = None,
    ) -> AuthStatus:
        payload = self._http_client.request_json(
            "GET",
            f"/auth/{reference_number}",
            bearer_token=authentication_token,
            timeout=timeout,
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
        return self._authentication_poller.wait_for_authentication(
            reference_number=reference_number,
            authentication_token=authentication_token,
            timeout_seconds=timeout_seconds,
            poll_interval=poll_interval,
            get_auth_status=lambda ref, token, request_timeout: self.get_auth_status(
                reference_number=ref,
                authentication_token=token,
                timeout=request_timeout,
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
