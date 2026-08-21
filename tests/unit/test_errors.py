from nerva.errors import NervaError


def test_unknown_code_fallback() -> None:
    err = NervaError("UNKNOWN_CODE")

    assert err.category == "internal"
    assert err.retryable is False
    assert err.message == "UNKNOWN_CODE"


def test_standard_code_semantics() -> None:
    err = NervaError("PERMISSION_DENIED")

    assert err.category == "authorization"
    assert err.retryable is False
    assert "policy" in err.message.lower()


def test_error_serialization_no_envelope() -> None:
    err = NervaError(
        "WORKER_FAILED",
        request_id="req-1",
    )

    data = err.to_dict()

    assert "error" not in data
    assert data["code"] == "WORKER_FAILED"
    assert data["request_id"] == "req-1"
    assert data["category"] == "internal"


def test_cause_and_request_id() -> None:
    err = NervaError(
        "UNAVAILABLE",
        cause_code="CONFLICT",
        request_id="req-2",
    )

    assert err.cause_code == "CONFLICT"
    assert err.request_id == "req-2"
    assert err.retryable is True
