from collections.abc import Mapping

import pytest

from nerva.context import ExecContext
from nerva.errors import NervaError


def test_initialization_with_defaults() -> None:
    ctx = ExecContext(
        request_id="req-1",
        user_id="user-1",
    )

    assert ctx.request_id == "req-1"
    assert ctx.user_id == "user-1"
    assert ctx.session_id is None
    assert ctx.trace_id is None
    assert ctx.timeout_ms is None
    assert ctx.deadline_unix_ms is None
    assert ctx.version == "1.0"
    assert ctx.capabilities == ()
    assert ctx.metadata == {}


def test_accepts_list_and_dict_then_converts_internally() -> None:
    ctx = ExecContext(
        request_id="req-1",
        user_id="user-1",
        capabilities=["read", "write"],
        metadata={"key": "value"},
    )

    assert isinstance(ctx.capabilities, tuple)
    assert isinstance(ctx.metadata, Mapping)
    assert not isinstance(ctx.metadata, dict)


def test_rejects_bad_capabilities() -> None:
    with pytest.raises(NervaError) as exc:
        ExecContext(
            request_id="req",
            user_id="user",
            capabilities="read",
        )

    assert exc.value.code == "SCHEMA_VALIDATION_FAILED"

    with pytest.raises(NervaError) as exc:
        ExecContext(
            request_id="req",
            user_id="user",
            capabilities=[1, 2],
        )

    assert exc.value.code == "SCHEMA_VALIDATION_FAILED"


def test_rejects_bad_metadata() -> None:
    with pytest.raises(NervaError) as exc:
        ExecContext(
            request_id="req",
            user_id="user",
            metadata=["key"],
        )

    assert exc.value.code == "SCHEMA_VALIDATION_FAILED"


def test_rejects_unknown_fields() -> None:
    with pytest.raises(NervaError) as exc:
        ExecContext.from_dict(
            {
                "request_id": "req",
                "user_id": "user",
                "unexpected_field": True,
            }
        )

    assert exc.value.code == "SCHEMA_VALIDATION_FAILED"


def test_rejects_credentials_recursively() -> None:
    with pytest.raises(NervaError) as exc:
        ExecContext(
            request_id="req",
            user_id="user",
            metadata={"password": "123"},
        )

    assert exc.value.code == "SCHEMA_VALIDATION_FAILED"

    with pytest.raises(NervaError) as exc:
        ExecContext(
            request_id="req",
            user_id="user",
            metadata={
                "items": (
                    {
                        "Token": "secret",
                    },
                )
            },
        )

    assert exc.value.code == "SCHEMA_VALIDATION_FAILED"


def test_immutability_of_context() -> None:
    ctx = ExecContext(
        request_id="req",
        user_id="user",
    )

    with pytest.raises(AttributeError):
        ctx.request_id = "changed"

    with pytest.raises(AttributeError):
        ctx.capabilities = ("changed",)


def test_immutability_of_nested_metadata() -> None:
    ctx = ExecContext(
        request_id="req",
        user_id="user",
        metadata={
            "nested": {
                "x": 1,
            }
        },
    )

    nested = ctx.metadata["nested"]

    with pytest.raises(TypeError):
        nested["x"] = 2

    source = {
        "nested": {
            "x": 1,
        }
    }

    ctx = ExecContext(
        request_id="req",
        user_id="user",
        metadata=source,
    )

    source["nested"]["x"] = 100

    assert ctx.metadata["nested"]["x"] == 1


def test_to_dict_and_from_dict_roundtrip() -> None:
    ctx = ExecContext(
        request_id="req",
        user_id="user",
        timeout_ms=100,
        capabilities=["read"],
        metadata={
            "key": "value",
        },
    )

    data = ctx.to_dict()

    assert isinstance(data["capabilities"], list)
    assert isinstance(data["metadata"], dict)

    restored = ExecContext.from_dict(data)

    assert restored == ctx
