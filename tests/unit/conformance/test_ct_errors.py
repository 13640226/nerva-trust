from nerva.errors import ERROR_CATALOG, NervaError


def test_ct_error_001_catalog_has_exact_18_codes() -> None:
    """Must contain exactly the 18 canonical error codes."""
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
    """Unknown codes must use the canonical fallback."""
    err = NervaError("UNKNOWN")

    assert err.category == "internal"
    assert err.retryable is False


def test_ct_error_003_no_envelope() -> None:
    """Serialization must not add an outer error envelope."""
    err = NervaError(
        "PERMISSION_DENIED",
        request_id="r1",
    )

    data = err.to_dict()

    assert "error" not in data
    assert data["code"] == "PERMISSION_DENIED"


def test_ct_error_004_cause_and_request_id() -> None:
    """cause_code and request_id must be preserved."""
    err = NervaError(
        "WORKER_FAILED",
        cause_code="INTERNAL_ERROR",
        request_id="r1",
    )

    assert err.cause_code == "INTERNAL_ERROR"
    assert err.request_id == "r1"


def test_ct_error_005_permission_denied_semantics() -> None:
    """PERMISSION_DENIED has fixed canonical semantics."""
    assert ERROR_CATALOG["PERMISSION_DENIED"]["category"] == "authorization"
    assert ERROR_CATALOG["PERMISSION_DENIED"]["retryable"] is False


def test_ct_error_006_cancelled_semantics() -> None:
    """CANCELLED has fixed canonical semantics."""
    assert ERROR_CATALOG["CANCELLED"]["category"] == "cancelled"
    assert ERROR_CATALOG["CANCELLED"]["retryable"] is False


def test_ct_error_007_unavailable_semantics() -> None:
    """UNAVAILABLE has fixed canonical semantics."""
    assert ERROR_CATALOG["UNAVAILABLE"]["category"] == "unavailable"
    assert ERROR_CATALOG["UNAVAILABLE"]["retryable"] is True
