from collections.abc import Mapping

import pytest

from nerva.context import ExecContext
from nerva.errors import NervaError


def test_ct_ctx_001_rejects_empty_ids() -> None:
    """R-CTX-1: request_id and user_id must be non-empty strings."""
    with pytest.raises(NervaError):
        ExecContext(request_id="", user_id="u")

    with pytest.raises(NervaError):
        ExecContext(request_id="r", user_id="")


def test_ct_ctx_002_rejects_invalid_timeout_and_bool() -> None:
    """R-CTX-3: timeout/deadline must be positive ints; bool is invalid."""
    with pytest.raises(NervaError):
        ExecContext(request_id="r", user_id="u", timeout_ms=True)

    with pytest.raises(NervaError):
        ExecContext(request_id="r", user_id="u", deadline_unix_ms=-10)


def test_ct_ctx_003_rejects_invalid_optional_strings() -> None:
    """R-CTX-2: session_id and trace_id must be strings or None."""
    with pytest.raises(NervaError):
        ExecContext(request_id="r", user_id="u", session_id=123)

    with pytest.raises(NervaError):
        ExecContext(request_id="r", user_id="u", trace_id=1.5)


def test_ct_ctx_004_rejects_non_string_version() -> None:
    """R-CTX-4: version must be a string."""
    with pytest.raises(NervaError):
        ExecContext(request_id="r", user_id="u", version=123)


def test_ct_ctx_005_unsupported_version_raises() -> None:
    """R-CTX-4: Unsupported versions must raise UNSUPPORTED_VERSION."""
    with pytest.raises(NervaError) as exc:
        ExecContext(request_id="r", user_id="u", version="2.0")

    assert exc.value.code == "UNSUPPORTED_VERSION"


def test_ct_ctx_006_rejects_non_list_capabilities() -> None:
    """R-CTX-5: capabilities must be a list of strings."""
    with pytest.raises(NervaError):
        ExecContext(
            request_id="r",
            user_id="u",
            capabilities="read",
        )


def test_ct_ctx_007_rejects_non_dict_metadata() -> None:
    """R-CTX-6: metadata must be a dictionary."""
    with pytest.raises(NervaError):
        ExecContext(
            request_id="r",
            user_id="u",
            metadata=["k"],
        )


def test_ct_ctx_008_unknown_fields_rejected() -> None:
    """R-CTX-8: from_dict must reject unknown fields."""
    with pytest.raises(NervaError) as exc:
        ExecContext.from_dict(
            {
                "request_id": "r",
                "user_id": "u",
                "random": True,
            }
        )

    assert exc.value.code == "SCHEMA_VALIDATION_FAILED"


def test_ct_ctx_009_roundtrip() -> None:
    """R-CTX-7: to_dict and from_dict must be reversible."""
    ctx = ExecContext(
        request_id="r",
        user_id="u",
        capabilities=["read"],
    )

    assert ExecContext.from_dict(ctx.to_dict()) == ctx


def test_ct_ctx_010_deep_immutability_enforced() -> None:
    """R-CTX-9: Context and nested metadata must be immutable."""
    ctx = ExecContext(
        request_id="r",
        user_id="u",
        capabilities=["read"],
        metadata={"nested": {"x": 1}},
    )

    with pytest.raises(AttributeError):
        ctx.capabilities = ("write",)

    assert isinstance(ctx.metadata, Mapping)
    assert not isinstance(ctx.metadata, dict)

    nested = ctx.metadata["nested"]

    with pytest.raises(TypeError):
        nested["x"] = 2


def test_ct_ctx_011_credentials_rejected() -> None:
    """R-CTX-10: Credential-bearing metadata must be rejected."""
    with pytest.raises(NervaError) as exc:
        ExecContext(
            request_id="r",
            user_id="u",
            metadata={"password": "hunter2"},
        )

    assert exc.value.code == "SCHEMA_VALIDATION_FAILED"
    assert "Credential" in exc.value.message
