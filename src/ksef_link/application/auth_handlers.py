from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict
from typing import Any

from ksef_link.application.commands import AuthenticateCommandOptions, RefreshCommandOptions
from ksef_link.domain.auth import AuthenticatedSession
from ksef_link.ports.auth import AuthPort
from ksef_link.shared.errors import ConfigurationError


def handle_authenticate_command(
    command: AuthenticateCommandOptions,
    environment: Mapping[str, str],
    auth_port: AuthPort,
) -> dict[str, Any]:
    """Run the authenticate command use case."""
    ksef_token = command.ksef_token or environment.get("KSEF_TOKEN")
    if not ksef_token:
        raise ConfigurationError("Brakuje tokena KSeF. Podaj --ksef-token albo ustaw KSEF_TOKEN.")

    session = auth_port.authenticate_with_ksef_token(
        ksef_token=ksef_token,
        context_type=command.context_type,
        context_value=command.context_value,
        authorization_policy=build_authorization_policy(command),
        timeout_seconds=command.wait_timeout,
        poll_interval=command.poll_interval,
    )
    return authenticated_session_to_payload(session)


def handle_refresh_command(
    command: RefreshCommandOptions,
    auth_port: AuthPort,
) -> dict[str, Any]:
    """Run the refresh command use case."""
    access_token = auth_port.refresh_access_token(refresh_token=command.refresh_token)
    return {
        "accessToken": asdict(access_token),
    }


def build_authorization_policy(command: AuthenticateCommandOptions) -> dict[str, Any] | None:
    """Build KSeF authorization policy payload from CLI values."""
    allowed_ips: dict[str, list[str]] = {}
    if command.allowed_ipv4:
        allowed_ips["ip4Addresses"] = list(command.allowed_ipv4)
    if command.allowed_ipv4_range:
        allowed_ips["ip4Ranges"] = list(command.allowed_ipv4_range)
    if command.allowed_ipv4_mask:
        allowed_ips["ip4Masks"] = list(command.allowed_ipv4_mask)

    if not allowed_ips:
        return None

    return {
        "allowedIps": allowed_ips,
    }


def authenticated_session_to_payload(session: AuthenticatedSession) -> dict[str, Any]:
    return {
        "challenge": {
            "challenge": session.challenge.challenge,
            "timestamp": session.challenge.timestamp,
            "timestampMs": session.challenge.timestamp_ms,
            "clientIp": session.challenge.client_ip,
        },
        "publicKeyCertificate": {
            "validFrom": session.certificate.valid_from,
            "validTo": session.certificate.valid_to,
            "usage": session.certificate.usage,
        },
        "authentication": {
            "referenceNumber": session.init_result.reference_number,
            "authenticationToken": asdict(session.init_result.authentication_token),
            "status": asdict(session.status.status),
        },
        "tokens": {
            "accessToken": asdict(session.tokens.access_token),
            "refreshToken": asdict(session.tokens.refresh_token),
        },
    }
