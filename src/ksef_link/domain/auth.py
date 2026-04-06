"""Domain models representing KSeF authentication data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TokenInfo:
    """Represents a JWT-like token returned by KSeF."""

    token: str
    valid_until: str

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> TokenInfo:
        """Build a token model from a KSeF API payload.

        Args:
            payload: Raw token payload returned by KSeF.

        Returns:
            Parsed token model.
        """
        return cls(token=payload["token"], valid_until=payload["validUntil"])


@dataclass(frozen=True)
class StatusInfo:
    """Represents a status block returned by KSeF."""

    code: int
    description: str
    details: list[str] | None = None

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> StatusInfo:
        """Build a status model from a KSeF API payload.

        Args:
            payload: Raw status payload returned by KSeF.

        Returns:
            Parsed status model.
        """
        raw_details = payload.get("details")
        details = list(raw_details) if isinstance(raw_details, list) else None
        return cls(
            code=int(payload["code"]),
            description=payload["description"],
            details=details,
        )


@dataclass(frozen=True)
class AuthenticationMethodInfo:
    """Describes the authentication method reported by KSeF."""

    category: str
    code: str
    display_name: str

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> AuthenticationMethodInfo:
        """Build an authentication method model from a KSeF API payload.

        Args:
            payload: Raw method payload returned by KSeF.

        Returns:
            Parsed authentication method model.
        """
        return cls(
            category=payload["category"],
            code=payload["code"],
            display_name=payload["displayName"],
        )


@dataclass(frozen=True)
class AuthChallenge:
    """Represents a KSeF authentication challenge."""

    challenge: str
    timestamp: str
    timestamp_ms: int
    client_ip: str

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> AuthChallenge:
        """Build a challenge model from a KSeF API payload.

        Args:
            payload: Raw challenge payload returned by KSeF.

        Returns:
            Parsed challenge model.
        """
        return cls(
            challenge=payload["challenge"],
            timestamp=payload["timestamp"],
            timestamp_ms=int(payload["timestampMs"]),
            client_ip=payload["clientIp"],
        )


@dataclass(frozen=True)
class PublicKeyCertificate:
    """Represents a public certificate returned by KSeF."""

    certificate: str
    valid_from: str
    valid_to: str
    usage: list[str]

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> PublicKeyCertificate:
        """Build a certificate model from a KSeF API payload.

        Args:
            payload: Raw certificate payload returned by KSeF.

        Returns:
            Parsed certificate model.
        """
        return cls(
            certificate=payload["certificate"],
            valid_from=payload["validFrom"],
            valid_to=payload["validTo"],
            usage=list(payload["usage"]),
        )


@dataclass(frozen=True)
class AuthInitResult:
    """Represents the result of starting KSeF authentication."""

    reference_number: str
    authentication_token: TokenInfo

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> AuthInitResult:
        """Build an auth-init model from a KSeF API payload.

        Args:
            payload: Raw init payload returned by KSeF.

        Returns:
            Parsed auth-init model.
        """
        return cls(
            reference_number=payload["referenceNumber"],
            authentication_token=TokenInfo.from_api(payload["authenticationToken"]),
        )


@dataclass(frozen=True)
class AuthStatus:
    """Represents the current status of an authentication session."""

    start_date: str
    authentication_method: str
    authentication_method_info: AuthenticationMethodInfo
    status: StatusInfo
    is_token_redeemed: bool | None = None
    last_token_refresh_date: str | None = None
    refresh_token_valid_until: str | None = None

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> AuthStatus:
        """Build an authentication status model from a KSeF API payload.

        Args:
            payload: Raw status payload returned by KSeF.

        Returns:
            Parsed auth status model.
        """
        return cls(
            start_date=payload["startDate"],
            authentication_method=payload["authenticationMethod"],
            authentication_method_info=AuthenticationMethodInfo.from_api(payload["authenticationMethodInfo"]),
            status=StatusInfo.from_api(payload["status"]),
            is_token_redeemed=payload.get("isTokenRedeemed"),
            last_token_refresh_date=payload.get("lastTokenRefreshDate"),
            refresh_token_valid_until=payload.get("refreshTokenValidUntil"),
        )


@dataclass(frozen=True)
class AuthTokens:
    """Represents final access and refresh tokens issued by KSeF."""

    access_token: TokenInfo
    refresh_token: TokenInfo

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> AuthTokens:
        """Build an auth-tokens model from a KSeF API payload.

        Args:
            payload: Raw token payload returned by KSeF.

        Returns:
            Parsed auth tokens model.
        """
        return cls(
            access_token=TokenInfo.from_api(payload["accessToken"]),
            refresh_token=TokenInfo.from_api(payload["refreshToken"]),
        )


@dataclass(frozen=True)
class AuthenticatedSession:
    """Aggregates all domain objects produced by a full auth flow."""

    challenge: AuthChallenge
    certificate: PublicKeyCertificate
    init_result: AuthInitResult
    status: AuthStatus
    tokens: AuthTokens
