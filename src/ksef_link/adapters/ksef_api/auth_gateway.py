"""Authentication-focused KSeF API adapter."""

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
        """Initialize the authentication gateway.

        Args:
            http_client: Shared HTTP client used to talk to KSeF.
            certificate_selector: Optional strategy for picking certificates.
            token_encryptor: Optional strategy for encrypting token payloads.
            authentication_poller: Optional strategy for polling auth status.
        """
        self._http_client = http_client
        self._certificate_selector = certificate_selector or CertificateSelector()
        self._token_encryptor = token_encryptor or TokenEncryptor()
        self._authentication_poller = authentication_poller or AuthenticationPoller()

    def get_auth_challenge(self) -> AuthChallenge:
        """Request a new KSeF authentication challenge.

        Returns:
            Parsed authentication challenge.
        """
        payload = self._http_client.request_json("POST", "/auth/challenge", content=b"")
        return AuthChallenge.from_api(payload)

    def get_public_key_certificates(self) -> list[PublicKeyCertificate]:
        """Fetch public certificates published by KSeF.

        Returns:
            Parsed list of public certificates.
        """
        payload = self._http_client.request_json("GET", "/security/public-key-certificates")
        return [PublicKeyCertificate.from_api(item) for item in payload]

    def get_active_encryption_certificate(self) -> PublicKeyCertificate:
        """Select the active public certificate used for token encryption.

        Returns:
            Active encryption certificate.
        """
        return self._certificate_selector.select_active_encryption_certificate(self.get_public_key_certificates())

    def encrypt_ksef_token(
        self,
        *,
        ksef_token: str,
        timestamp_ms: int,
        public_certificate_b64: str,
    ) -> str:
        """Encrypt the KSeF token payload for ``/auth/ksef-token``.

        Args:
            ksef_token: Raw KSeF token.
            timestamp_ms: Challenge timestamp in milliseconds.
            public_certificate_b64: Base64-encoded DER certificate.

        Returns:
            Base64-encoded encrypted token payload.
        """
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
        """Start authentication using an encrypted KSeF token.

        Args:
            challenge: Challenge string returned by KSeF.
            context_type: KSeF context identifier type.
            context_value: KSeF context identifier value.
            encrypted_token: Encrypted token payload.
            authorization_policy: Optional IP restriction payload.

        Returns:
            Authentication initialization result.
        """
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
        """Fetch the current status of an authentication request.

        Args:
            reference_number: Authentication reference number.
            authentication_token: Temporary authentication token.
            timeout: Optional per-request timeout override.

        Returns:
            Parsed authentication status.
        """
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
        """Poll KSeF until authentication succeeds or times out.

        Args:
            reference_number: Authentication reference number.
            authentication_token: Temporary authentication token.
            timeout_seconds: End-to-end timeout budget for polling.
            poll_interval: Delay between polling attempts.

        Returns:
            Final successful authentication status.
        """
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
        """Redeem the temporary authentication token for final tokens.

        Args:
            authentication_token: Temporary authentication token.

        Returns:
            Final access and refresh tokens.
        """
        payload = self._http_client.request_json(
            "POST",
            "/auth/token/redeem",
            bearer_token=authentication_token,
            content=b"",
        )
        return AuthTokens.from_api(payload)

    def refresh_access_token(self, *, refresh_token: str) -> TokenInfo:
        """Refresh the access token using a refresh token.

        Args:
            refresh_token: Refresh token issued by KSeF.

        Returns:
            Refreshed access token info.
        """
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
        """Run the complete KSeF token authentication flow.

        Args:
            ksef_token: Raw KSeF token.
            context_type: KSeF context identifier type.
            context_value: KSeF context identifier value.
            authorization_policy: Optional IP restriction payload.
            timeout_seconds: End-to-end timeout budget for polling.
            poll_interval: Delay between polling attempts.

        Returns:
            Aggregated authenticated session data.
        """
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
