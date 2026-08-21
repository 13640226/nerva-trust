from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable
from typing import Any

import pytest

from nerva.context import ExecContext
from nerva.errors import NervaError
from nerva.execution import CapabilityHandler, ExecutionResult, Executor
from nerva.policy import Policy, Rule
from nerva.registry import Registry

CAPABILITY = "test.execute"
USER_ID = "user-001"


def make_context(
    *,
    timeout_ms: int | None = None,
    deadline_unix_ms: int | None = None,
    request_id: str = "request-001",
    user_id: str = USER_ID,
) -> ExecContext:
    return ExecContext(
        request_id=request_id,
        user_id=user_id,
        timeout_ms=timeout_ms,
        deadline_unix_ms=deadline_unix_ms,
    )


def make_allow_policy(
    capability: str = CAPABILITY,
    *,
    budget: int = 100,
) -> Policy:
    # Rule requires at least one constraint in the current Layer 1 contract.
    return Policy(
        [
            Rule(
                capability=capability,
                effect="ALLOW",
                budget=budget,
            )
        ]
    )


def make_executor(
    handler: CapabilityHandler | Any,
    *,
    capability: str = CAPABILITY,
    policy: Policy | None = None,
) -> tuple[Executor, Registry, Policy]:
    registry = Registry()
    registry.register(capability, handler)

    actual_policy = policy or make_allow_policy(capability)

    executor = Executor(
        registry=registry,
        policy=actual_policy,
    )

    return executor, registry, actual_policy


def run(coro: Awaitable[Any]) -> Any:
    return asyncio.run(coro)


async def echo_handler(
    args: dict[str, Any],
    context: ExecContext,
) -> dict[str, Any]:
    return {
        "args": args,
        "request_id": context.request_id,
        "user_id": context.user_id,
    }


# ---------------------------------------------------------------------------
# R-EXEC-001 — Scope and Responsibilities
# ---------------------------------------------------------------------------


def test_ct_exec_001_executes_registered_capability_after_policy() -> None:
    handler = CapabilityHandler(
        version="1.0",
        handler=echo_handler,
        description="Conformance echo handler",
    )

    executor, _, _ = make_executor(handler)

    context = make_context()

    result = run(
        executor.invoke(
            CAPABILITY,
            {"value": 42},
            context,
        )
    )

    assert isinstance(result, ExecutionResult)
    assert result.capability == CAPABILITY
    assert result.output == {
        "args": {"value": 42},
        "request_id": "request-001",
        "user_id": USER_ID,
    }


# ---------------------------------------------------------------------------
# R-EXEC-002 — ExecutionResult
# ---------------------------------------------------------------------------


def test_ct_exec_002_execution_result_contract() -> None:
    handler = CapabilityHandler(
        version="1.0",
        handler=echo_handler,
    )

    executor, _, _ = make_executor(handler)
    result = run(executor.invoke(CAPABILITY, {}, make_context()))

    assert isinstance(result, ExecutionResult)

    # Canonical UUID string.
    from uuid import UUID

    parsed = UUID(result.execution_id)
    assert str(parsed) == result.execution_id

    assert result.capability == CAPABILITY

    assert type(result.duration_ms) is int
    assert result.duration_ms >= 0

    assert dict(result.metadata) == {}


def test_ct_exec_002_metadata_is_immutable_and_empty() -> None:
    handler = CapabilityHandler(
        version="1.0",
        handler=echo_handler,
    )

    executor, _, _ = make_executor(handler)
    result = run(executor.invoke(CAPABILITY, {}, make_context()))

    assert dict(result.metadata) == {}

    with pytest.raises(TypeError):
        result.metadata["new"] = "value"  # type: ignore[index]


def test_ct_exec_002_output_is_not_deep_frozen() -> None:
    output = {
        "items": [1, 2, 3],
    }

    async def handler(
        args: dict[str, Any],
        context: ExecContext,
    ) -> Any:
        del args, context
        return output

    executor, _, _ = make_executor(
        CapabilityHandler(
            version="1.0",
            handler=handler,
        )
    )

    result = run(executor.invoke(CAPABILITY, {}, make_context()))

    assert result.output is output
    result.output["items"].append(4)
    assert result.output["items"] == [1, 2, 3, 4]


# ---------------------------------------------------------------------------
# R-EXEC-003 — CapabilityHandler
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "version",
    [
        "",
        1,
        None,
        False,
    ],
)
def test_ct_exec_003_handler_rejects_invalid_version(version: Any) -> None:
    with pytest.raises(NervaError) as exc_info:
        CapabilityHandler(
            version=version,
            handler=echo_handler,
        )

    assert exc_info.value.code == "INVALID_INPUT"


@pytest.mark.parametrize(
    "description",
    [
        123,
        False,
        [],
        {},
    ],
)
def test_ct_exec_003_handler_rejects_invalid_description(
    description: Any,
) -> None:
    with pytest.raises(NervaError) as exc_info:
        CapabilityHandler(
            version="1.0",
            handler=echo_handler,
            description=description,
        )

    assert exc_info.value.code == "INVALID_INPUT"


def test_ct_exec_003_handler_accepts_none_description() -> None:
    handler = CapabilityHandler(
        version="1.0",
        handler=echo_handler,
        description=None,
    )

    assert handler.description is None


def test_ct_exec_003_handler_rejects_non_callable() -> None:
    with pytest.raises(NervaError) as exc_info:
        CapabilityHandler(
            version="1.0",
            handler="not-callable",  # type: ignore[arg-type]
        )

    assert exc_info.value.code == "INVALID_INPUT"


def test_ct_exec_003_non_awaitable_result_is_capability_unsupported() -> None:
    def sync_handler(
        args: dict[str, Any],
        context: ExecContext,
    ) -> Any:
        del args, context
        return {"sync": True}

    capability_handler = CapabilityHandler(
        version="1.0",
        handler=sync_handler,  # type: ignore[arg-type]
    )

    executor, _, _ = make_executor(capability_handler)

    with pytest.raises(NervaError) as exc_info:
        run(executor.invoke(CAPABILITY, {}, make_context()))

    assert exc_info.value.code == "CAPABILITY_UNSUPPORTED"


# ---------------------------------------------------------------------------
# R-EXEC-004 — Invocation Validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "capability",
    [
        "",
        None,
        123,
        False,
    ],
)
def test_ct_exec_004_rejects_invalid_capability(capability: Any) -> None:
    handler = CapabilityHandler(
        version="1.0",
        handler=echo_handler,
    )

    executor, _, _ = make_executor(handler)

    with pytest.raises(NervaError) as exc_info:
        run(
            executor.invoke(
                capability,
                {},
                make_context(),
            )
        )

    assert exc_info.value.code == "INVALID_INPUT"


@pytest.mark.parametrize(
    "args",
    [
        [],
        (),
        "bad",
        1,
        False,
    ],
)
def test_ct_exec_004_rejects_invalid_args(args: Any) -> None:
    handler = CapabilityHandler(
        version="1.0",
        handler=echo_handler,
    )

    executor, _, _ = make_executor(handler)

    with pytest.raises(NervaError) as exc_info:
        run(executor.invoke(CAPABILITY, args, make_context()))

    assert exc_info.value.code == "INVALID_INPUT"


def test_ct_exec_004_none_args_normalizes_to_empty_dict() -> None:
    observed: dict[str, Any] = {}

    async def handler(
        args: dict[str, Any],
        context: ExecContext,
    ) -> None:
        del context
        observed["args"] = args

    executor, _, _ = make_executor(
        CapabilityHandler(
            version="1.0",
            handler=handler,
        )
    )

    run(executor.invoke(CAPABILITY, None, make_context()))

    assert observed["args"] == {}
    assert type(observed["args"]) is dict


@pytest.mark.parametrize(
    "context",
    [
        None,
        {},
        "context",
        123,
    ],
)
def test_ct_exec_004_rejects_non_exec_context(context: Any) -> None:
    executor, _, _ = make_executor(
        CapabilityHandler(
            version="1.0",
            handler=echo_handler,
        )
    )

    with pytest.raises(NervaError) as exc_info:
        run(executor.invoke(CAPABILITY, {}, context))

    assert exc_info.value.code == "INVALID_INPUT"


# ---------------------------------------------------------------------------
# R-EXEC-005 — Policy Bridge
# ---------------------------------------------------------------------------


def test_ct_exec_005_policy_subject_is_exec_context_user_id() -> None:
    class RecordingPolicy(Policy):
        def __init__(self) -> None:
            super().__init__(
                [
                    Rule(
                        capability=CAPABILITY,
                        effect="ALLOW",
                        budget=100,
                    )
                ]
            )
            self.received_capability: str | None = None
            self.received_context: dict[str, Any] | None = None

        def enforce(
            self,
            capability: str,
            context: dict[str, Any],
        ):
            self.received_capability = capability
            self.received_context = dict(context)
            return super().enforce(capability, context)

    policy = RecordingPolicy()

    executor, _, _ = make_executor(
        CapabilityHandler(
            version="1.0",
            handler=echo_handler,
        ),
        policy=policy,
    )

    run(
        executor.invoke(
            CAPABILITY,
            {},
            make_context(user_id="bridge-user"),
        )
    )

    assert policy.received_capability == CAPABILITY
    assert policy.received_context == {
        "subject": "bridge-user",
    }


def test_ct_exec_005_does_not_invent_usage_cost_or_resource() -> None:
    class RecordingPolicy(Policy):
        def __init__(self) -> None:
            super().__init__(
                [
                    Rule(
                        capability=CAPABILITY,
                        effect="ALLOW",
                        budget=100,
                    )
                ]
            )
            self.received_context: dict[str, Any] | None = None

        def enforce(
            self,
            capability: str,
            context: dict[str, Any],
        ):
            self.received_context = dict(context)
            return super().enforce(capability, context)

    policy = RecordingPolicy()

    executor, _, _ = make_executor(
        CapabilityHandler(
            version="1.0",
            handler=echo_handler,
        ),
        policy=policy,
    )

    context = ExecContext(
        request_id="request-policy-context",
        user_id="policy-user",
        metadata={
            "usage": 99,
            "cost": 77,
            "resource": "secret-resource",
        },
    )

    run(executor.invoke(CAPABILITY, {}, context))

    assert policy.received_context == {
        "subject": "policy-user",
    }


# ---------------------------------------------------------------------------
# R-EXEC-006 — Execution Ordering and Policy Finality
# ---------------------------------------------------------------------------


def test_ct_exec_006_policy_runs_before_registry_resolution() -> None:
    events: list[str] = []

    class RecordingPolicy(Policy):
        def __init__(self) -> None:
            super().__init__(
                [
                    Rule(
                        capability=CAPABILITY,
                        effect="ALLOW",
                        budget=100,
                    )
                ]
            )

        def enforce(
            self,
            capability: str,
            context: dict[str, Any],
        ):
            events.append("policy")
            return super().enforce(capability, context)

    class RecordingRegistry(Registry):
        def get(self, id: str) -> Any:
            events.append("registry")
            return super().get(id)

    policy = RecordingPolicy()
    registry = RecordingRegistry()

    registry.register(
        CAPABILITY,
        CapabilityHandler(
            version="1.0",
            handler=echo_handler,
        ),
    )

    executor = Executor(
        registry=registry,
        policy=policy,
    )

    run(executor.invoke(CAPABILITY, {}, make_context()))

    assert events[:2] == [
        "policy",
        "registry",
    ]


def test_ct_exec_006_denied_request_does_not_probe_registry() -> None:
    events: list[str] = []

    class RecordingRegistry(Registry):
        def get(self, id: str) -> Any:
            events.append("registry")
            return super().get(id)

    registry = RecordingRegistry()

    policy = Policy(
        [
            Rule(
                capability=CAPABILITY,
                effect="DENY",
                budget=100,
            )
        ]
    )

    executor = Executor(
        registry=registry,
        policy=policy,
    )

    with pytest.raises(NervaError) as exc_info:
        run(executor.invoke(CAPABILITY, {}, make_context()))

    assert exc_info.value.code == "PERMISSION_DENIED"
    assert events == []


def test_ct_exec_006_policy_is_final_if_registry_lookup_fails() -> None:
    policy = make_allow_policy(
        CAPABILITY,
        budget=1,
    )
    registry = Registry()

    executor = Executor(
        registry=registry,
        policy=policy,
    )

    with pytest.raises(NervaError) as first_error:
        run(executor.invoke(CAPABILITY, {}, make_context()))

    assert first_error.value.code == "NOT_FOUND"

    # Budget consumption from the successful Policy.enforce() must remain.
    with pytest.raises(NervaError) as second_error:
        run(executor.invoke(CAPABILITY, {}, make_context()))

    assert second_error.value.code == "BUDGET_EXCEEDED"


def test_ct_exec_006_policy_is_final_if_handler_fails() -> None:
    async def failing_handler(
        args: dict[str, Any],
        context: ExecContext,
    ) -> Any:
        del args, context
        raise RuntimeError("must not leak")

    policy = make_allow_policy(
        CAPABILITY,
        budget=1,
    )

    executor, _, _ = make_executor(
        CapabilityHandler(
            version="1.0",
            handler=failing_handler,
        ),
        policy=policy,
    )

    with pytest.raises(NervaError) as first_error:
        run(executor.invoke(CAPABILITY, {}, make_context()))

    assert first_error.value.code == "WORKER_FAILED"

    with pytest.raises(NervaError) as second_error:
        run(executor.invoke(CAPABILITY, {}, make_context()))

    assert second_error.value.code == "BUDGET_EXCEEDED"


# ---------------------------------------------------------------------------
# R-EXEC-007 — Timeout and Deadline Semantics
# ---------------------------------------------------------------------------


def test_ct_exec_007_expired_deadline_fails_before_policy() -> None:
    policy = make_allow_policy(
        CAPABILITY,
        budget=1,
    )

    executor, _, _ = make_executor(
        CapabilityHandler(
            version="1.0",
            handler=echo_handler,
        ),
        policy=policy,
    )

    expired = int(time.time() * 1000) - 1000

    with pytest.raises(NervaError) as exc_info:
        run(
            executor.invoke(
                CAPABILITY,
                {},
                make_context(deadline_unix_ms=expired),
            )
        )

    assert exc_info.value.code == "EXECUTION_TIMEOUT"

    # If Policy had consumed its budget, this would fail.
    result = run(
        executor.invoke(
            CAPABILITY,
            {},
            make_context(),
        )
    )

    assert isinstance(result, ExecutionResult)


def test_ct_exec_007_timeout_ms_is_enforced() -> None:
    async def slow_handler(
        args: dict[str, Any],
        context: ExecContext,
    ) -> None:
        del args, context
        await asyncio.sleep(0.2)

    executor, _, _ = make_executor(
        CapabilityHandler(
            version="1.0",
            handler=slow_handler,
        )
    )

    with pytest.raises(NervaError) as exc_info:
        run(
            executor.invoke(
                CAPABILITY,
                {},
                make_context(timeout_ms=20),
            )
        )

    assert exc_info.value.code == "EXECUTION_TIMEOUT"


def test_ct_exec_007_deadline_is_enforced_during_execution() -> None:
    async def slow_handler(
        args: dict[str, Any],
        context: ExecContext,
    ) -> None:
        del args, context
        await asyncio.sleep(0.2)

    executor, _, _ = make_executor(
        CapabilityHandler(
            version="1.0",
            handler=slow_handler,
        )
    )

    deadline = int(time.time() * 1000) + 30

    with pytest.raises(NervaError) as exc_info:
        run(
            executor.invoke(
                CAPABILITY,
                {},
                make_context(deadline_unix_ms=deadline),
            )
        )

    assert exc_info.value.code == "EXECUTION_TIMEOUT"


def test_ct_exec_007_earliest_of_timeout_and_deadline_wins() -> None:
    async def slow_handler(
        args: dict[str, Any],
        context: ExecContext,
    ) -> None:
        del args, context
        await asyncio.sleep(0.3)

    executor, _, _ = make_executor(
        CapabilityHandler(
            version="1.0",
            handler=slow_handler,
        )
    )

    deadline = int(time.time() * 1000) + 500

    start = time.monotonic()

    with pytest.raises(NervaError) as exc_info:
        run(
            executor.invoke(
                CAPABILITY,
                {},
                make_context(
                    timeout_ms=30,
                    deadline_unix_ms=deadline,
                ),
            )
        )

    elapsed = time.monotonic() - start

    assert exc_info.value.code == "EXECUTION_TIMEOUT"
    assert elapsed < 0.25


def test_ct_exec_007_no_default_timeout() -> None:
    async def handler(
        args: dict[str, Any],
        context: ExecContext,
    ) -> str:
        del args, context
        await asyncio.sleep(0.03)
        return "completed"

    executor, _, _ = make_executor(
        CapabilityHandler(
            version="1.0",
            handler=handler,
        )
    )

    result = run(executor.invoke(CAPABILITY, {}, make_context()))

    assert result.output == "completed"


# ---------------------------------------------------------------------------
# R-EXEC-008 — Cancellation Semantics
# ---------------------------------------------------------------------------


def test_ct_exec_008_cancelled_error_normalizes_to_cancelled() -> None:
    async def cancelled_handler(
        args: dict[str, Any],
        context: ExecContext,
    ) -> None:
        del args, context
        raise asyncio.CancelledError

    executor, _, _ = make_executor(
        CapabilityHandler(
            version="1.0",
            handler=cancelled_handler,
        )
    )

    with pytest.raises(NervaError) as exc_info:
        run(executor.invoke(CAPABILITY, {}, make_context()))

    assert exc_info.value.code == "CANCELLED"


# ---------------------------------------------------------------------------
# R-EXEC-009 — Exception Normalization
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "exception",
    [
        TimeoutError(),
        asyncio.TimeoutError(),
    ],
)
def test_ct_exec_009_timeout_exceptions_normalize(
    exception: BaseException,
) -> None:
    async def handler(
        args: dict[str, Any],
        context: ExecContext,
    ) -> None:
        del args, context
        raise exception

    executor, _, _ = make_executor(
        CapabilityHandler(
            version="1.0",
            handler=handler,
        )
    )

    with pytest.raises(NervaError) as exc_info:
        run(executor.invoke(CAPABILITY, {}, make_context()))

    assert exc_info.value.code == "EXECUTION_TIMEOUT"


def test_ct_exec_009_other_exception_becomes_worker_failed() -> None:
    class CustomWorkerError(Exception):
        pass

    async def handler(
        args: dict[str, Any],
        context: ExecContext,
    ) -> None:
        del args, context
        raise CustomWorkerError("sensitive internal message")

    executor, _, _ = make_executor(
        CapabilityHandler(
            version="1.0",
            handler=handler,
        )
    )

    with pytest.raises(NervaError) as exc_info:
        run(executor.invoke(CAPABILITY, {}, make_context()))

    error = exc_info.value

    assert error.code == "WORKER_FAILED"
    assert error.details["exception_type"] == "CustomWorkerError"

    serialized = str(error.to_dict())

    assert "sensitive internal message" not in serialized


def test_ct_exec_009_keyboard_interrupt_propagates() -> None:
    async def handler(
        args: dict[str, Any],
        context: ExecContext,
    ) -> None:
        del args, context
        raise KeyboardInterrupt

    executor, _, _ = make_executor(
        CapabilityHandler(
            version="1.0",
            handler=handler,
        )
    )

    with pytest.raises(KeyboardInterrupt):
        run(executor.invoke(CAPABILITY, {}, make_context()))


def test_ct_exec_009_system_exit_propagates() -> None:
    async def handler(
        args: dict[str, Any],
        context: ExecContext,
    ) -> None:
        del args, context
        raise SystemExit(7)

    executor, _, _ = make_executor(
        CapabilityHandler(
            version="1.0",
            handler=handler,
        )
    )

    with pytest.raises(SystemExit) as exc_info:
        run(executor.invoke(CAPABILITY, {}, make_context()))

    assert exc_info.value.code == 7


# ---------------------------------------------------------------------------
# R-EXEC-010 — Registry Executable Contract
# ---------------------------------------------------------------------------


def test_ct_exec_010_missing_registry_entry_raises_not_found() -> None:
    executor = Executor(
        registry=Registry(),
        policy=make_allow_policy(),
    )

    with pytest.raises(NervaError) as exc_info:
        run(executor.invoke(CAPABILITY, {}, make_context()))

    assert exc_info.value.code == "NOT_FOUND"


@pytest.mark.parametrize(
    "registered_value",
    [
        object(),
        "handler",
        123,
        {},
        echo_handler,
    ],
)
def test_ct_exec_010_non_capability_handler_is_unsupported(
    registered_value: Any,
) -> None:
    registry = Registry()
    registry.register(CAPABILITY, registered_value)

    executor = Executor(
        registry=registry,
        policy=make_allow_policy(),
    )

    with pytest.raises(NervaError) as exc_info:
        run(executor.invoke(CAPABILITY, {}, make_context()))

    assert exc_info.value.code == "CAPABILITY_UNSUPPORTED"


# ---------------------------------------------------------------------------
# R-EXEC-011 — Transport Neutrality
# ---------------------------------------------------------------------------


def test_ct_exec_011_returns_python_objects_without_transport_envelope() -> None:
    opaque_output = {
        "ok": True,
        "items": [1, 2, 3],
    }

    async def handler(
        args: dict[str, Any],
        context: ExecContext,
    ) -> Any:
        del args, context
        return opaque_output

    executor, _, _ = make_executor(
        CapabilityHandler(
            version="1.0",
            handler=handler,
        )
    )

    result = run(executor.invoke(CAPABILITY, {}, make_context()))

    assert isinstance(result, ExecutionResult)
    assert result.output is opaque_output
    assert not isinstance(result, bytes)
    assert not isinstance(result.output, bytes)


# ---------------------------------------------------------------------------
# R-EXEC-012 — State and Side-Effect Boundaries
# ---------------------------------------------------------------------------


def test_ct_exec_012_exec_context_is_not_mutated() -> None:
    context = ExecContext(
        request_id="immutability-request",
        user_id="immutability-user",
        capabilities=["alpha"],
        metadata={
            "nested": {
                "values": [1, 2, 3],
            }
        },
    )

    before = context.to_dict()

    executor, _, _ = make_executor(
        CapabilityHandler(
            version="1.0",
            handler=echo_handler,
        )
    )

    run(executor.invoke(CAPABILITY, {}, context))

    after = context.to_dict()

    assert after == before


def test_ct_exec_012_executor_does_not_require_persistent_state() -> None:
    calls = 0

    async def handler(
        args: dict[str, Any],
        context: ExecContext,
    ) -> int:
        nonlocal calls
        del args, context
        calls += 1
        return calls

    executor, _, _ = make_executor(
        CapabilityHandler(
            version="1.0",
            handler=handler,
        ),
        policy=make_allow_policy(
            CAPABILITY,
            budget=10,
        ),
    )

    first = run(executor.invoke(CAPABILITY, {}, make_context()))
    second = run(executor.invoke(CAPABILITY, {}, make_context()))

    assert first.output == 1
    assert second.output == 2
