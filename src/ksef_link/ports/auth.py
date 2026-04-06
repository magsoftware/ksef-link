from __future__ import annotations

from typing import Any, Protocol

from ksef_link.domain.auth import AuthenticatedSession, TokenInfo


class AuthPort(Protocol):
    def refresh_access_token(self, *, refresh_token: str) -> TokenInfo:
        ...

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
        ...
