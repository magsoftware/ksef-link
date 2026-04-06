from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    body: bytes
    headers: dict[str, str]
