from __future__ import annotations

from typing import Any

import pytest

from ksef_link.application.auth_handlers import (
    build_authorization_policy,
    handle_authenticate_command,
    handle_refresh_command,
)
from ksef_link.application.commands import AuthenticateCommandOptions, RefreshCommandOptions
from ksef_link.domain.auth import (
    AuthChallenge,
    AuthenticatedSession,
    AuthenticationMethodInfo,
    AuthInitResult,
    AuthStatus,
    AuthTokens,
    PublicKeyCertificate,
    StatusInfo,
    TokenInfo,
)
from ksef_link.shared.errors import ConfigurationError


class StubAuthService:
    def __init__(self) -> None:
        self.refresh_calls: list[str] = []
        self.auth_calls: list[tuple[str, str, str]] = []

    def refresh_access_token(self, *, refresh_token: str) -> TokenInfo:
        self.refresh_calls.append(refresh_token)
        return TokenInfo(token="refreshed-access", valid_until="2026-04-06T12:00:00+02:00")

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
        self.auth_calls.append((ksef_token, context_type, context_value))
        return AuthenticatedSession(
            challenge=AuthChallenge(
                challenge="challenge",
                timestamp="2026-04-06T00:00:00+02:00",
                timestamp_ms=1,
                client_ip="127.0.0.1",
            ),
            certificate=PublicKeyCertificate(
                certificate="certificate",
                valid_from="2026-04-01T00:00:00+02:00",
                valid_to="2027-04-01T00:00:00+02:00",
                usage=["KsefTokenEncryption"],
            ),
            init_result=AuthInitResult(
                reference_number="reference",
                authentication_token=TokenInfo(token="auth-token", valid_until="2026-04-06T12:00:00+02:00"),
            ),
            status=AuthStatus(
                start_date="2026-04-06T00:00:00+02:00",
                authentication_method="Token",
                authentication_method_info=AuthenticationMethodInfo(
                    category="Token",
                    code="token.ksef",
                    display_name="Token KSeF",
                ),
                status=StatusInfo(code=200, description="ok"),
            ),
            tokens=AuthTokens(
                access_token=TokenInfo(token="authenticated-access", valid_until="2026-04-06T12:00:00+02:00"),
                refresh_token=TokenInfo(token="refresh", valid_until="2026-04-06T12:00:00+02:00"),
            ),
        )


def test_build_authorization_policy_returns_none_when_not_configured() -> None:
    command = AuthenticateCommandOptions(
        ksef_token=None,
        context_type="Nip",
        context_value="6771086988",
        poll_interval=1.0,
        wait_timeout=60.0,
        allowed_ipv4=(),
        allowed_ipv4_range=(),
        allowed_ipv4_mask=(),
    )

    assert build_authorization_policy(command) is None


def test_build_authorization_policy_includes_all_ip_collections() -> None:
    command = AuthenticateCommandOptions(
        ksef_token="token",
        context_type="Nip",
        context_value="6771086988",
        poll_interval=1.0,
        wait_timeout=60.0,
        allowed_ipv4=("127.0.0.1",),
        allowed_ipv4_range=("10.0.0.1-10.0.0.2",),
        allowed_ipv4_mask=("172.16.0.0/16",),
    )

    assert build_authorization_policy(command) == {
        "allowedIps": {
            "ip4Addresses": ["127.0.0.1"],
            "ip4Ranges": ["10.0.0.1-10.0.0.2"],
            "ip4Masks": ["172.16.0.0/16"],
        }
    }


def test_handle_authenticate_command_uses_environment_token() -> None:
    auth_service = StubAuthService()
    command = AuthenticateCommandOptions(
        ksef_token=None,
        context_type="Nip",
        context_value="6771086988",
        poll_interval=1.0,
        wait_timeout=60.0,
        allowed_ipv4=(),
        allowed_ipv4_range=(),
        allowed_ipv4_mask=(),
    )

    result = handle_authenticate_command(command, {"KSEF_TOKEN": "env-token"}, auth_service)

    assert result["tokens"]["accessToken"]["token"] == "authenticated-access"


def test_handle_authenticate_command_raises_when_token_missing() -> None:
    command = AuthenticateCommandOptions(
        ksef_token=None,
        context_type="Nip",
        context_value="6771086988",
        poll_interval=1.0,
        wait_timeout=60.0,
        allowed_ipv4=(),
        allowed_ipv4_range=(),
        allowed_ipv4_mask=(),
    )

    with pytest.raises(ConfigurationError):
        handle_authenticate_command(command, {}, StubAuthService())


def test_handle_refresh_command_returns_access_token_payload() -> None:
    result = handle_refresh_command(RefreshCommandOptions(refresh_token="refresh"), StubAuthService())

    assert result["accessToken"]["token"] == "refreshed-access"
