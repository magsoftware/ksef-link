from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TokenInfo:
    token: str
    valid_until: str

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> TokenInfo:
        return cls(token=payload["token"], valid_until=payload["validUntil"])


@dataclass(frozen=True)
class StatusInfo:
    code: int
    description: str
    details: list[str] | None = None

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> StatusInfo:
        raw_details = payload.get("details")
        details = list(raw_details) if isinstance(raw_details, list) else None
        return cls(
            code=int(payload["code"]),
            description=payload["description"],
            details=details,
        )


@dataclass(frozen=True)
class AuthenticationMethodInfo:
    category: str
    code: str
    display_name: str

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> AuthenticationMethodInfo:
        return cls(
            category=payload["category"],
            code=payload["code"],
            display_name=payload["displayName"],
        )


@dataclass(frozen=True)
class AuthChallenge:
    challenge: str
    timestamp: str
    timestamp_ms: int
    client_ip: str

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> AuthChallenge:
        return cls(
            challenge=payload["challenge"],
            timestamp=payload["timestamp"],
            timestamp_ms=int(payload["timestampMs"]),
            client_ip=payload["clientIp"],
        )


@dataclass(frozen=True)
class PublicKeyCertificate:
    certificate: str
    valid_from: str
    valid_to: str
    usage: list[str]

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> PublicKeyCertificate:
        return cls(
            certificate=payload["certificate"],
            valid_from=payload["validFrom"],
            valid_to=payload["validTo"],
            usage=list(payload["usage"]),
        )


@dataclass(frozen=True)
class AuthInitResult:
    reference_number: str
    authentication_token: TokenInfo

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> AuthInitResult:
        return cls(
            reference_number=payload["referenceNumber"],
            authentication_token=TokenInfo.from_api(payload["authenticationToken"]),
        )


@dataclass(frozen=True)
class AuthStatus:
    start_date: str
    authentication_method: str
    authentication_method_info: AuthenticationMethodInfo
    status: StatusInfo
    is_token_redeemed: bool | None = None
    last_token_refresh_date: str | None = None
    refresh_token_valid_until: str | None = None

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> AuthStatus:
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
    access_token: TokenInfo
    refresh_token: TokenInfo

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> AuthTokens:
        return cls(
            access_token=TokenInfo.from_api(payload["accessToken"]),
            refresh_token=TokenInfo.from_api(payload["refreshToken"]),
        )


@dataclass(frozen=True)
class AuthenticatedSession:
    challenge: AuthChallenge
    certificate: PublicKeyCertificate
    init_result: AuthInitResult
    status: AuthStatus
    tokens: AuthTokens


@dataclass(frozen=True)
class InvoiceQueryResult:
    has_more: bool
    is_truncated: bool
    permanent_storage_hwm_date: str | None
    pages_fetched: int
    invoices: list[dict[str, Any]]


@dataclass(frozen=True)
class InvoiceDownload:
    ksef_number: str
    content: bytes
    content_hash: str | None


@dataclass(frozen=True)
class RuntimeOptions:
    base_url: str
    timeout: float
    debug: bool
    env_file: Path


@dataclass(frozen=True)
class AuthenticateCommandOptions:
    ksef_token: str | None
    context_type: str
    context_value: str
    poll_interval: float
    wait_timeout: float
    allowed_ipv4: tuple[str, ...]
    allowed_ipv4_range: tuple[str, ...]
    allowed_ipv4_mask: tuple[str, ...]


@dataclass(frozen=True)
class RefreshCommandOptions:
    refresh_token: str


@dataclass(frozen=True)
class InvoicesCommandOptions:
    access_token: str | None
    refresh_token: str | None
    ksef_token: str | None
    context_type: str | None
    context_value: str | None
    subject_type: str
    date_type: str
    date_from: str | None
    date_to: str | None
    sort_order: str
    page_size: int
    restrict_to_hwm: bool
    ksef_number: str | None
    invoice_number: str | None
    seller_nip: str | None
    download_dir: Path | None
    poll_interval: float
    wait_timeout: float


CommandOptions = AuthenticateCommandOptions | RefreshCommandOptions | InvoicesCommandOptions


@dataclass(frozen=True)
class CliOptions:
    runtime: RuntimeOptions
    command: CommandOptions


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    body: bytes
    headers: dict[str, str]
