from __future__ import annotations

import asyncio
import inspect
import uuid
from collections.abc import Callable
from dataclasses import FrozenInstanceError, dataclass
from typing import Any

import pytest

from nerva.context import ExecContext
from nerva.errors import NervaError
from nerva.execution import ExecutionResult
from nerva.workflow import Orchestrator, Workflow, WorkflowResult, WorkflowStep

Handler = Callable[[str, dict[str, Any], ExecContext], Any]


@dataclass
class InvocationRecord:
    capability: str
    args: dict[str, Any]
    context: ExecContext


class FakeExecutor:
    def __init__(self) -> None:
        self.invocations: list[InvocationRecord] = []
        self._handlers: dict[str, Handler] = {}
        self._default_handler: Handler | None = None
        self.started_event: asyncio.Event | None = None

    def set_handler(self, capability: str, handler: Handler) -> None:
        self._handlers[capability] = handler

    def set_default_handler(self, handler: Handler) -> None:
        self._default_handler = handler

    def set_started_event(self, event: asyncio.Event) -> None:
        self.started_event = event

    async def invoke(
        self,
        capability: str,
        args: dict[str, Any],
        context: ExecContext,
    ) -> ExecutionResult:
        self.invocations.append(
            InvocationRecord(
                capability=capability,
                args=args,
                context=context,
            )
        )

        if self.started_event is not None:
            self.started_event.set()

        handler = self._handlers.get(capability, self._default_handler)

        if handler is None:
            output: Any = {
                "capability": capability,
                "args": args,
                "user_id": context.user_id,
            }
        else:
            result = handler(capability, args, context)

            if inspect.isawaitable(result):
                result = await result

            if isinstance(result, ExecutionResult):
                return result

            output = result

        return ExecutionResult(
            execution_id=str(uuid.uuid4()),
            capability=capability,
            output=output,
            duration_ms=0,
            metadata={},
        )


def make_context(
    request_id: str = "req-001",
    user_id: str = "user-001",
) -> ExecContext:
    return ExecContext(
        request_id=request_id,
        user_id=user_id,
    )


def make_step(
    id: str,
    capability: str | None = None,
    args: dict[str, Any] | None = None,
    depends_on: tuple[str, ...] = (),
) -> WorkflowStep:
    if capability is None:
        capability = f"cap.{id}"

    return WorkflowStep(
        id=id,
        capability=capability,
        args={} if args is None else args,
        depends_on=depends_on,
    )


# ============================================================================
# R-WORKFLOW-001 — Workflow Definition
# ============================================================================


def test_workflow_001_empty_steps_raises() -> None:
    with pytest.raises(NervaError) as exc:
        Workflow(steps=())

    assert exc.value.code == "INVALID_INPUT"


def test_workflow_001_single_valid_step() -> None:
    step = make_step("a")

    workflow = Workflow(steps=(step,))

    assert workflow.steps == (step,)


def test_workflow_001_non_tuple_steps_raises() -> None:
    step = make_step("a")

    with pytest.raises(NervaError) as exc:
        Workflow(steps=[step])  # type: ignore[arg-type]

    assert exc.value.code == "INVALID_INPUT"


def test_workflow_001_non_step_object_raises() -> None:
    with pytest.raises(NervaError) as exc:
        Workflow(steps=(object(),))  # type: ignore[arg-type]

    assert exc.value.code == "INVALID_INPUT"


def test_workflow_001_forward_reference_allowed() -> None:
    step_a = make_step("a")
    step_b = make_step("b", depends_on=("a",))

    workflow = Workflow(steps=(step_b, step_a))

    assert workflow.steps == (step_b, step_a)


def test_workflow_001_workflow_is_immutable() -> None:
    step = make_step("a")
    workflow = Workflow(steps=(step,))

    with pytest.raises(FrozenInstanceError):
        workflow.steps = ()  # type: ignore[misc]


# ============================================================================
# R-WORKFLOW-002 — Workflow Step Validation
# ============================================================================


def test_step_002_empty_id_raises() -> None:
    with pytest.raises(NervaError) as exc:
        WorkflowStep(
            id="",
            capability="cap.a",
            args={},
        )

    assert exc.value.code == "INVALID_INPUT"


def test_step_002_empty_capability_raises() -> None:
    with pytest.raises(NervaError) as exc:
        WorkflowStep(
            id="a",
            capability="",
            args={},
        )

    assert exc.value.code == "INVALID_INPUT"


def test_step_002_non_mapping_args_raises() -> None:
    with pytest.raises(NervaError) as exc:
        WorkflowStep(
            id="a",
            capability="cap.a",
            args=[],  # type: ignore[arg-type]
        )

    assert exc.value.code == "INVALID_INPUT"


def test_step_002_non_string_arg_key_raises() -> None:
    with pytest.raises(NervaError) as exc:
        WorkflowStep(
            id="a",
            capability="cap.a",
            args={1: "invalid"},  # type: ignore[dict-item]
        )

    assert exc.value.code == "INVALID_INPUT"


def test_step_002_args_none_normalizes_to_empty() -> None:
    step = WorkflowStep(
        id="a",
        capability="cap.a",
        args=None,
    )

    assert len(step.args) == 0

    with pytest.raises(TypeError):
        step.args["x"] = 1  # type: ignore[index]


def test_step_002_args_mapping_is_immutable() -> None:
    step = WorkflowStep(
        id="a",
        capability="cap.a",
        args={"value": 1},
    )

    with pytest.raises(TypeError):
        step.args["value"] = 2  # type: ignore[index]


def test_step_002_args_isolated_from_source_mapping() -> None:
    source = {"value": 1}

    step = WorkflowStep(
        id="a",
        capability="cap.a",
        args=source,
    )

    source["value"] = 2
    source["added"] = True

    assert step.args["value"] == 1
    assert "added" not in step.args


def test_step_002_depends_on_none_normalizes_to_empty_tuple() -> None:
    step = WorkflowStep(
        id="a",
        capability="cap.a",
        args={},
        depends_on=None,
    )

    assert step.depends_on == ()


def test_step_002_duplicate_dependency_raises() -> None:
    with pytest.raises(NervaError) as exc:
        WorkflowStep(
            id="b",
            capability="cap.b",
            args={},
            depends_on=("a", "a"),
        )

    assert exc.value.code == "INVALID_INPUT"


def test_step_002_non_tuple_depends_on_raises() -> None:
    with pytest.raises(NervaError) as exc:
        WorkflowStep(
            id="b",
            capability="cap.b",
            args={},
            depends_on=["a"],  # type: ignore[arg-type]
        )

    assert exc.value.code == "INVALID_INPUT"


def test_step_002_non_string_dependency_raises() -> None:
    with pytest.raises(NervaError) as exc:
        WorkflowStep(
            id="b",
            capability="cap.b",
            args={},
            depends_on=(1,),  # type: ignore[arg-type]
        )

    assert exc.value.code == "INVALID_INPUT"


def test_step_002_step_is_immutable() -> None:
    step = make_step("a")

    with pytest.raises(FrozenInstanceError):
        step.id = "changed"  # type: ignore[misc]


# ============================================================================
# R-WORKFLOW-003 — Step Identifier Uniqueness
# ============================================================================


def test_workflow_003_duplicate_id_raises() -> None:
    step_a1 = make_step("a")
    step_a2 = make_step("a")

    with pytest.raises(NervaError) as exc:
        Workflow(steps=(step_a1, step_a2))

    assert exc.value.code == "INVALID_INPUT"


def test_workflow_003_case_sensitive_ids() -> None:
    step_lower = make_step("a")
    step_upper = make_step("A")

    workflow = Workflow(steps=(step_lower, step_upper))

    assert len(workflow.steps) == 2


# ============================================================================
# R-WORKFLOW-004 — Dependency Reference Validation
# ============================================================================


def test_workflow_004_missing_dependency_raises() -> None:
    step = make_step(
        "b",
        depends_on=("missing",),
    )

    with pytest.raises(NervaError) as exc:
        Workflow(steps=(step,))

    assert exc.value.code == "INVALID_INPUT"


def test_workflow_004_self_dependency_raises() -> None:
    step = make_step(
        "a",
        depends_on=("a",),
    )

    with pytest.raises(NervaError) as exc:
        Workflow(steps=(step,))

    assert exc.value.code == "INVALID_INPUT"


def test_workflow_004_root_step_allowed() -> None:
    step = make_step(
        "a",
        depends_on=(),
    )

    workflow = Workflow(steps=(step,))

    assert workflow.steps == (step,)


def test_workflow_004_forward_reference_valid() -> None:
    step_b = make_step(
        "b",
        depends_on=("a",),
    )
    step_a = make_step("a")

    workflow = Workflow(steps=(step_b, step_a))

    assert workflow.steps == (step_b, step_a)


# ============================================================================
# R-WORKFLOW-005 — Acyclic Graph Requirement
# ============================================================================


def test_workflow_005_direct_cycle_raises() -> None:
    step_a = make_step(
        "a",
        depends_on=("a",),
    )

    with pytest.raises(NervaError) as exc:
        Workflow(steps=(step_a,))

    assert exc.value.code == "INVALID_INPUT"


def test_workflow_005_indirect_cycle_raises() -> None:
    step_a = make_step(
        "a",
        depends_on=("b",),
    )
    step_b = make_step(
        "b",
        depends_on=("a",),
    )

    with pytest.raises(NervaError) as exc:
        Workflow(steps=(step_a, step_b))

    assert exc.value.code == "INVALID_INPUT"


def test_workflow_005_longer_cycle_raises() -> None:
    step_a = make_step(
        "a",
        depends_on=("c",),
    )
    step_b = make_step(
        "b",
        depends_on=("a",),
    )
    step_c = make_step(
        "c",
        depends_on=("b",),
    )

    with pytest.raises(NervaError) as exc:
        Workflow(steps=(step_a, step_b, step_c))

    assert exc.value.code == "INVALID_INPUT"


def test_workflow_005_acyclic_succeeds() -> None:
    step_a = make_step("a")
    step_b = make_step(
        "b",
        depends_on=("a",),
    )
    step_c = make_step(
        "c",
        depends_on=("b",),
    )

    workflow = Workflow(
        steps=(
            step_a,
            step_b,
            step_c,
        )
    )

    assert len(workflow.steps) == 3


# ============================================================================
# R-WORKFLOW-006 — Step Readiness
# ============================================================================


def test_workflow_006_root_step_executes() -> None:
    async def run() -> None:
        executor = FakeExecutor()
        orchestrator = Orchestrator(executor=executor)  # type: ignore[arg-type]

        workflow = Workflow(steps=(make_step("a"),))

        await orchestrator.invoke(
            workflow,
            make_context(),
        )

        assert [invocation.capability for invocation in executor.invocations] == ["cap.a"]

    asyncio.run(run())


def test_workflow_006_dependent_step_executes_after_dependency() -> None:
    async def run() -> None:
        executor = FakeExecutor()
        orchestrator = Orchestrator(executor=executor)  # type: ignore[arg-type]

        workflow = Workflow(
            steps=(
                make_step("a"),
                make_step(
                    "b",
                    depends_on=("a",),
                ),
            )
        )

        await orchestrator.invoke(
            workflow,
            make_context(),
        )

        capabilities = [invocation.capability for invocation in executor.invocations]

        assert capabilities == [
            "cap.a",
            "cap.b",
        ]

    asyncio.run(run())


def test_workflow_006_dependent_step_not_executed_on_failure() -> None:
    async def run() -> None:
        executor = FakeExecutor()
        orchestrator = Orchestrator(executor=executor)  # type: ignore[arg-type]

        error = NervaError("WORKER_FAILED")

        async def fail_handler(
            capability: str,
            args: dict[str, Any],
            context: ExecContext,
        ) -> Any:
            raise error

        executor.set_handler(
            "cap.a",
            fail_handler,
        )

        workflow = Workflow(
            steps=(
                make_step("a"),
                make_step(
                    "b",
                    depends_on=("a",),
                ),
            )
        )

        with pytest.raises(NervaError) as exc:
            await orchestrator.invoke(
                workflow,
                make_context(),
            )

        assert exc.value is error

        capabilities = [invocation.capability for invocation in executor.invocations]

        assert capabilities == ["cap.a"]

    asyncio.run(run())


def test_workflow_006_step_invoked_exactly_once_per_workflow() -> None:
    async def run() -> None:
        executor = FakeExecutor()
        orchestrator = Orchestrator(executor=executor)  # type: ignore[arg-type]

        workflow = Workflow(steps=(make_step("a"),))
        context = make_context()

        await orchestrator.invoke(
            workflow,
            context,
        )

        assert len(executor.invocations) == 1

        await orchestrator.invoke(
            workflow,
            context,
        )

        assert len(executor.invocations) == 2

        assert all(invocation.capability == "cap.a" for invocation in executor.invocations)

    asyncio.run(run())


# ============================================================================
# R-WORKFLOW-007 — Step Execution
# ============================================================================


def test_workflow_007_successful_step_returns_result() -> None:
    async def run() -> None:
        executor = FakeExecutor()
        orchestrator = Orchestrator(executor=executor)  # type: ignore[arg-type]

        workflow = Workflow(steps=(make_step("a"),))

        result = await orchestrator.invoke(
            workflow,
            make_context(),
        )

        assert isinstance(
            result,
            WorkflowResult,
        )
        assert "a" in result.outputs
        assert result.outputs["a"]["capability"] == "cap.a"

    asyncio.run(run())


def test_workflow_007_failed_step_raises_original_error() -> None:
    async def run() -> None:
        executor = FakeExecutor()
        orchestrator = Orchestrator(executor=executor)  # type: ignore[arg-type]

        error = NervaError("WORKER_FAILED")

        async def fail_handler(
            capability: str,
            args: dict[str, Any],
            context: ExecContext,
        ) -> Any:
            raise error

        executor.set_handler(
            "cap.a",
            fail_handler,
        )

        workflow = Workflow(steps=(make_step("a"),))

        with pytest.raises(NervaError) as exc:
            await orchestrator.invoke(
                workflow,
                make_context(),
            )

        assert exc.value is error
        assert exc.value.code == "WORKER_FAILED"

    asyncio.run(run())


def test_workflow_007_args_shallow_copied_not_mutated() -> None:
    async def run() -> None:
        executor = FakeExecutor()
        orchestrator = Orchestrator(executor=executor)  # type: ignore[arg-type]

        nested = {"inner": "value"}

        source_args: dict[str, Any] = {
            "key": "value",
            "nested": nested,
        }

        captured_args: dict[str, Any] | None = None

        step = make_step(
            "a",
            args=source_args,
        )

        async def capture_handler(
            capability: str,
            args: dict[str, Any],
            context: ExecContext,
        ) -> Any:
            nonlocal captured_args
            captured_args = args

            assert args["nested"] is step.args["nested"]

            args["key"] = "mutated"
            args["new_key"] = "added"

            return {"ok": True}

        executor.set_handler(
            "cap.a",
            capture_handler,
        )

        workflow = Workflow(steps=(step,))

        await orchestrator.invoke(
            workflow,
            make_context(),
        )

        assert step.args["key"] == "value"
        assert "new_key" not in step.args

        assert captured_args is not None
        assert captured_args is not step.args
        assert captured_args["nested"] is step.args["nested"]

    asyncio.run(run())


def test_workflow_007_context_is_passed_through() -> None:
    async def run() -> None:
        executor = FakeExecutor()
        orchestrator = Orchestrator(executor=executor)  # type: ignore[arg-type]

        context = make_context()

        workflow = Workflow(steps=(make_step("a"),))

        await orchestrator.invoke(
            workflow,
            context,
        )

        assert executor.invocations[0].context is context

    asyncio.run(run())


# ============================================================================
# R-WORKFLOW-008 — No Inter-Step Data Binding
# ============================================================================


def test_workflow_008_output_not_injected_into_next_step() -> None:
    async def run() -> None:
        executor = FakeExecutor()
        orchestrator = Orchestrator(executor=executor)  # type: ignore[arg-type]

        async def handler_a(
            capability: str,
            args: dict[str, Any],
            context: ExecContext,
        ) -> Any:
            return {
                "from_a": "data",
            }

        executor.set_handler(
            "cap.a",
            handler_a,
        )

        workflow = Workflow(
            steps=(
                make_step("a"),
                make_step(
                    "b",
                    args={
                        "b_input": "fixed",
                    },
                    depends_on=("a",),
                ),
            )
        )

        await orchestrator.invoke(
            workflow,
            make_context(),
        )

        invocation_b = next(
            invocation for invocation in executor.invocations if invocation.capability == "cap.b"
        )

        assert invocation_b.args == {
            "b_input": "fixed",
        }

    asyncio.run(run())


def test_workflow_008_shared_object_from_caller_allowed() -> None:
    async def run() -> None:
        executor = FakeExecutor()
        orchestrator = Orchestrator(executor=executor)  # type: ignore[arg-type]

        shared = {
            "shared": "object",
        }

        workflow = Workflow(
            steps=(
                make_step(
                    "a",
                    args={"ref": shared},
                ),
                make_step(
                    "b",
                    args={"ref": shared},
                ),
            )
        )

        await orchestrator.invoke(
            workflow,
            make_context(),
        )

        invocation_a = next(
            invocation for invocation in executor.invocations if invocation.capability == "cap.a"
        )

        invocation_b = next(
            invocation for invocation in executor.invocations if invocation.capability == "cap.b"
        )

        assert invocation_a.args["ref"] is shared
        assert invocation_b.args["ref"] is shared

    asyncio.run(run())


# ============================================================================
# R-WORKFLOW-009 — Fail-Fast Semantics
# ============================================================================


def test_workflow_009_single_step_failure_propagates() -> None:
    async def run() -> None:
        executor = FakeExecutor()
        orchestrator = Orchestrator(executor=executor)  # type: ignore[arg-type]

        error = NervaError("EXECUTION_TIMEOUT")

        async def fail_handler(
            capability: str,
            args: dict[str, Any],
            context: ExecContext,
        ) -> Any:
            raise error

        executor.set_handler(
            "cap.a",
            fail_handler,
        )

        workflow = Workflow(steps=(make_step("a"),))

        with pytest.raises(NervaError) as exc:
            await orchestrator.invoke(
                workflow,
                make_context(),
            )

        assert exc.value is error
        assert exc.value.code == "EXECUTION_TIMEOUT"

    asyncio.run(run())


def test_workflow_009_failure_stops_new_steps() -> None:
    async def run() -> None:
        executor = FakeExecutor()
        orchestrator = Orchestrator(executor=executor)  # type: ignore[arg-type]

        async def handler(
            capability: str,
            args: dict[str, Any],
            context: ExecContext,
        ) -> Any:
            if capability == "cap.b":
                raise NervaError("WORKER_FAILED")

            return {"ok": True}

        executor.set_default_handler(handler)

        workflow = Workflow(
            steps=(
                make_step("a"),
                make_step(
                    "b",
                    depends_on=("a",),
                ),
                make_step(
                    "c",
                    depends_on=("b",),
                ),
            )
        )

        with pytest.raises(NervaError) as exc:
            await orchestrator.invoke(
                workflow,
                make_context(),
            )

        assert exc.value.code == "WORKER_FAILED"

        started = {invocation.capability for invocation in executor.invocations}

        assert "cap.c" not in started

    asyncio.run(run())


def test_workflow_009_sibling_cancellation_on_failure() -> None:
    async def run() -> None:
        executor = FakeExecutor()
        orchestrator = Orchestrator(executor=executor)  # type: ignore[arg-type]

        sibling_started = asyncio.Event()
        never_set = asyncio.Event()
        cancellation_observed = asyncio.Event()

        error = NervaError("WORKER_FAILED")

        async def slow_handler(
            capability: str,
            args: dict[str, Any],
            context: ExecContext,
        ) -> Any:
            sibling_started.set()

            try:
                await never_set.wait()
            except asyncio.CancelledError:
                cancellation_observed.set()
                raise

        async def fail_handler(
            capability: str,
            args: dict[str, Any],
            context: ExecContext,
        ) -> Any:
            await sibling_started.wait()
            raise error

        executor.set_handler(
            "cap.a",
            slow_handler,
        )
        executor.set_handler(
            "cap.b",
            fail_handler,
        )

        workflow = Workflow(
            steps=(
                make_step("a"),
                make_step("b"),
            )
        )

        with pytest.raises(NervaError) as exc:
            await orchestrator.invoke(
                workflow,
                make_context(),
            )

        assert exc.value is error
        assert cancellation_observed.is_set()

    asyncio.run(run())


def test_workflow_009_no_partial_result_on_failure() -> None:
    async def run() -> None:
        executor = FakeExecutor()
        orchestrator = Orchestrator(executor=executor)  # type: ignore[arg-type]

        async def fail_handler(
            capability: str,
            args: dict[str, Any],
            context: ExecContext,
        ) -> Any:
            raise NervaError("WORKER_FAILED")

        executor.set_handler(
            "cap.a",
            fail_handler,
        )

        workflow = Workflow(steps=(make_step("a"),))

        with pytest.raises(NervaError):
            await orchestrator.invoke(
                workflow,
                make_context(),
            )

    asyncio.run(run())


# ============================================================================
# R-WORKFLOW-010 — Cancellation
# ============================================================================


def test_workflow_010_caller_cancellation_returns_cancelled() -> None:
    async def run() -> None:
        executor = FakeExecutor()
        orchestrator = Orchestrator(executor=executor)  # type: ignore[arg-type]

        started = asyncio.Event()
        never_set = asyncio.Event()
        cancellation_observed = asyncio.Event()

        executor.set_started_event(started)

        async def blocking_handler(
            capability: str,
            args: dict[str, Any],
            context: ExecContext,
        ) -> Any:
            try:
                await never_set.wait()
            except asyncio.CancelledError:
                cancellation_observed.set()
                raise

        executor.set_handler(
            "cap.a",
            blocking_handler,
        )

        workflow = Workflow(steps=(make_step("a"),))

        task = asyncio.create_task(
            orchestrator.invoke(
                workflow,
                make_context(),
            )
        )

        await started.wait()

        task.cancel()

        with pytest.raises(NervaError) as exc:
            await task

        assert exc.value.code == "CANCELLED"
        assert cancellation_observed.is_set()

    asyncio.run(run())


def test_workflow_010_failfast_cancels_siblings() -> None:
    async def run() -> None:
        executor = FakeExecutor()
        orchestrator = Orchestrator(executor=executor)  # type: ignore[arg-type]

        sibling_started = asyncio.Event()
        never_set = asyncio.Event()
        cancellation_observed = asyncio.Event()

        error = NervaError("WORKER_FAILED")

        async def cancellable_handler(
            capability: str,
            args: dict[str, Any],
            context: ExecContext,
        ) -> Any:
            sibling_started.set()

            try:
                await never_set.wait()
            except asyncio.CancelledError:
                cancellation_observed.set()
                raise

        async def fail_handler(
            capability: str,
            args: dict[str, Any],
            context: ExecContext,
        ) -> Any:
            await sibling_started.wait()
            raise error

        executor.set_handler(
            "cap.a",
            cancellable_handler,
        )
        executor.set_handler(
            "cap.b",
            fail_handler,
        )

        workflow = Workflow(
            steps=(
                make_step("a"),
                make_step("b"),
            )
        )

        with pytest.raises(NervaError) as exc:
            await orchestrator.invoke(
                workflow,
                make_context(),
            )

        assert exc.value is error
        assert cancellation_observed.is_set()

    asyncio.run(run())


def test_workflow_010_sibling_exceptions_do_not_replace_primary() -> None:
    async def run() -> None:
        executor = FakeExecutor()
        orchestrator = Orchestrator(executor=executor)  # type: ignore[arg-type]

        secondary_started = asyncio.Event()
        never_set = asyncio.Event()

        primary_error = NervaError("WORKER_FAILED")

        async def primary_handler(
            capability: str,
            args: dict[str, Any],
            context: ExecContext,
        ) -> Any:
            await secondary_started.wait()
            raise primary_error

        async def secondary_handler(
            capability: str,
            args: dict[str, Any],
            context: ExecContext,
        ) -> Any:
            secondary_started.set()

            try:
                await never_set.wait()
            except asyncio.CancelledError:
                raise NervaError("EXECUTION_TIMEOUT")

        executor.set_handler(
            "cap.a",
            primary_handler,
        )
        executor.set_handler(
            "cap.b",
            secondary_handler,
        )

        workflow = Workflow(
            steps=(
                make_step("a"),
                make_step("b"),
            )
        )

        with pytest.raises(NervaError) as exc:
            await orchestrator.invoke(
                workflow,
                make_context(),
            )

        assert exc.value is primary_error
        assert exc.value.code == "WORKER_FAILED"

    asyncio.run(run())


# ============================================================================
# R-WORKFLOW-011 — Workflow Result
# ============================================================================


def test_workflow_011_result_on_success() -> None:
    async def run() -> None:
        executor = FakeExecutor()
        orchestrator = Orchestrator(executor=executor)  # type: ignore[arg-type]

        workflow = Workflow(
            steps=(
                make_step("a"),
                make_step(
                    "b",
                    depends_on=("a",),
                ),
            )
        )

        result = await orchestrator.invoke(
            workflow,
            make_context(),
        )

        assert isinstance(
            result,
            WorkflowResult,
        )

        assert set(result.outputs.keys()) == {
            "a",
            "b",
        }

    asyncio.run(run())


def test_workflow_011_outputs_exactly_one_per_step() -> None:
    async def run() -> None:
        executor = FakeExecutor()
        orchestrator = Orchestrator(executor=executor)  # type: ignore[arg-type]

        steps = tuple(make_step(str(index)) for index in range(3))

        workflow = Workflow(steps=steps)

        result = await orchestrator.invoke(
            workflow,
            make_context(),
        )

        assert len(result.outputs) == 3

        assert set(result.outputs) == {
            "0",
            "1",
            "2",
        }

    asyncio.run(run())


def test_workflow_011_output_value_is_execution_output() -> None:
    async def run() -> None:
        executor = FakeExecutor()
        orchestrator = Orchestrator(executor=executor)  # type: ignore[arg-type]

        output = object()

        async def handler(
            capability: str,
            args: dict[str, Any],
            context: ExecContext,
        ) -> Any:
            return output

        executor.set_handler(
            "cap.a",
            handler,
        )

        workflow = Workflow(steps=(make_step("a"),))

        result = await orchestrator.invoke(
            workflow,
            make_context(),
        )

        assert result.outputs["a"] is output

    asyncio.run(run())


def test_workflow_011_outputs_immutable() -> None:
    async def run() -> None:
        executor = FakeExecutor()
        orchestrator = Orchestrator(executor=executor)  # type: ignore[arg-type]

        workflow = Workflow(steps=(make_step("a"),))

        result = await orchestrator.invoke(
            workflow,
            make_context(),
        )

        with pytest.raises(TypeError):
            result.outputs["new"] = "value"  # type: ignore[index]

    asyncio.run(run())


def test_workflow_011_result_is_immutable() -> None:
    async def run() -> None:
        executor = FakeExecutor()
        orchestrator = Orchestrator(executor=executor)  # type: ignore[arg-type]

        workflow = Workflow(steps=(make_step("a"),))

        result = await orchestrator.invoke(
            workflow,
            make_context(),
        )

        with pytest.raises(FrozenInstanceError):
            result.workflow_id = "changed"  # type: ignore[misc]

    asyncio.run(run())


def test_workflow_011_workflow_id_is_valid_uuid() -> None:
    async def run() -> None:
        executor = FakeExecutor()
        orchestrator = Orchestrator(executor=executor)  # type: ignore[arg-type]

        workflow = Workflow(steps=(make_step("a"),))

        result = await orchestrator.invoke(
            workflow,
            make_context(),
        )

        parsed = uuid.UUID(result.workflow_id)

        assert str(parsed) == result.workflow_id

    asyncio.run(run())


def test_workflow_011_duration_ms_non_negative_integer() -> None:
    async def run() -> None:
        executor = FakeExecutor()
        orchestrator = Orchestrator(executor=executor)  # type: ignore[arg-type]

        workflow = Workflow(steps=(make_step("a"),))

        result = await orchestrator.invoke(
            workflow,
            make_context(),
        )

        assert isinstance(
            result.duration_ms,
            int,
        )
        assert not isinstance(
            result.duration_ms,
            bool,
        )
        assert result.duration_ms >= 0

    asyncio.run(run())


def test_workflow_011_no_result_on_failure() -> None:
    async def run() -> None:
        executor = FakeExecutor()
        orchestrator = Orchestrator(executor=executor)  # type: ignore[arg-type]

        async def fail_handler(
            capability: str,
            args: dict[str, Any],
            context: ExecContext,
        ) -> Any:
            raise NervaError("WORKER_FAILED")

        executor.set_handler(
            "cap.a",
            fail_handler,
        )

        workflow = Workflow(steps=(make_step("a"),))

        with pytest.raises(NervaError):
            await orchestrator.invoke(
                workflow,
                make_context(),
            )

    asyncio.run(run())


# ============================================================================
# R-WORKFLOW-012 — Orchestrator Boundaries
# ============================================================================


def test_workflow_012_non_workflow_object_raises() -> None:
    async def run() -> None:
        executor = FakeExecutor()
        orchestrator = Orchestrator(executor=executor)  # type: ignore[arg-type]

        with pytest.raises(NervaError) as exc:
            await orchestrator.invoke(
                "not-a-workflow",  # type: ignore[arg-type]
                make_context(),
            )

        assert exc.value.code == "INVALID_INPUT"

    asyncio.run(run())


def test_workflow_012_invalid_context_raises() -> None:
    async def run() -> None:
        executor = FakeExecutor()
        orchestrator = Orchestrator(executor=executor)  # type: ignore[arg-type]

        workflow = Workflow(steps=(make_step("a"),))

        with pytest.raises(NervaError) as exc:
            await orchestrator.invoke(
                workflow,
                None,  # type: ignore[arg-type]
            )

        assert exc.value.code == "INVALID_INPUT"

    asyncio.run(run())


def test_workflow_012_stateless_across_invocations() -> None:
    async def run() -> None:
        executor = FakeExecutor()
        orchestrator = Orchestrator(executor=executor)  # type: ignore[arg-type]

        workflow = Workflow(steps=(make_step("a"),))
        context = make_context()

        result_1 = await orchestrator.invoke(
            workflow,
            context,
        )

        assert len(executor.invocations) == 1

        result_2 = await orchestrator.invoke(
            workflow,
            context,
        )

        assert len(executor.invocations) == 2

        assert result_1.workflow_id != result_2.workflow_id
