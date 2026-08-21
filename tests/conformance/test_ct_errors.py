from nerva.errors import ERROR_CATALOG, NervaError


def test_ct_error_001_catalog_has_exact_18_codes() -> None:
    """Must contain exactly the 18 canonical codes defined in Appendix B."""
    assert set(ERROR_CATALOG) == {
        "EXECUTION_TIMEOUT",
        "CANCELLED",
        "WORKER_FAILED",
        "INTERNAL_ERROR",
        "PERMISSION_DENIED",
        "RATE_LIMIT_EXCEEDED",
        "QUOTA_EXCEEDED",
        "BUDGET_EXCEEDED",
        "RESOURCE_EXHAUSTED",
        "INVALID_INPUT",
        "SCHEMA_VALIDATION_FAILED",
        "NOT_FOUND",
        "ALREADY_EXISTS",
        "CONFLICT",
        "UNAVAILABLE",
        "UNSUPPORTED_VERSION",
        "CAPABILITY_UNSUPPORTED",
        "SERIALIZATION_FAILED",
    }


def test_ct_error_002_unknown_fallback() -> None:
    """Unknown codes must default to internal category and retryable=False."""
    err = NervaError("UNKNOWN")

    assert err.category == "internal"
    assert err.retryable is False


def test_ct_error_003_no_envelope() -> None:
    """to_dict() must return the canonical object without an outer envelope."""
    err = NervaError("PERMISSION_DENIED", request_id="r1")

    data = err.to_dict()

    assert "error" not in data
    assert data["code"] == "PERMISSION_DENIED"


def test_ct_error_004_cause_and_request_id() -> None:
    """cause_code and request_id must be preserved in the error object."""
    err = NervaError(
        "WORKER_FAILED",
        cause_code="INTERNAL_ERROR",
        request_id="r1",
    )

    assert err.cause_code == "INTERNAL_ERROR"
    assert err.request_id == "r1"


def test_ct_error_005_permission_denied_semantics() -> None:
    """PERMISSION_DENIED must be authorization and non-retryable."""
    assert ERROR_CATALOG["PERMISSION_DENIED"]["category"] == "authorization"
    assert ERROR_CATALOG["PERMISSION_DENIED"]["retryable"] is False


def test_ct_error_006_cancelled_semantics() -> None:
    """CANCELLED must be in cancelled category and non-retryable."""
    assert ERROR_CATALOG["CANCELLED"]["category"] == "cancelled"
    assert ERROR_CATALOG["CANCELLED"]["retryable"] is False


def test_ct_error_007_unavailable_semantics() -> None:
    """UNAVAILABLE must be in unavailable category and retryable."""
    assert ERROR_CATALOG["UNAVAILABLE"]["category"] == "unavailable"
    assert ERROR_CATALOG["UNAVAILABLE"]["retryable"] is True
