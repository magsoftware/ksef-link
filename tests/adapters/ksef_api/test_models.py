from __future__ import annotations

from ksef_link.adapters.ksef_api.models import HttpResponse


def test_http_response_dataclass_stores_values() -> None:
    response = HttpResponse(status_code=200, body=b"{}", headers={"Content-Type": "application/json"})

    assert response.status_code == 200
