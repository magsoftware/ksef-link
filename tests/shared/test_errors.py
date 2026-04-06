from __future__ import annotations

from ksef_link.shared.errors import KsefApiError


def test_ksef_api_error_to_payload_excludes_diagnostic_body() -> None:
    error = KsefApiError(
        "boom",
        status_code=403,
        error_code="missing-permissions",
        details=["detail"],
        body={"reason": "missing"},
    )

    assert error.to_payload() == {
        "error": "boom",
        "statusCode": 403,
        "errorCode": "missing-permissions",
        "details": ["detail"],
    }


def test_ksef_api_error_to_log_payload_includes_diagnostic_body() -> None:
    error = KsefApiError(
        "boom",
        status_code=403,
        error_code="missing-permissions",
        details=["detail"],
        body={"reason": "missing"},
    )

    assert error.to_log_payload() == {
        "error": "boom",
        "statusCode": 403,
        "errorCode": "missing-permissions",
        "details": ["detail"],
        "body": {"reason": "missing"},
    }
