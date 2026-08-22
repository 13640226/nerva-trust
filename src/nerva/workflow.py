from __future__ import annotations

import asyncio
import time
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any
from uuid import uuid4

from .context import ExecContext
from .errors import NervaError
from .execution import ExecutionResult, Executor


@dataclass(frozen=True)
class WorkflowStep:
    id: str
    capability: str
    args: Mapping[str, Any] | None = None
    depends_on: tuple[str, ...] | None = ()

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or self.id == "":
            raise NervaError(
                "INVALID_INPUT",
                message="workflow step id must be a non-empty string",
                details={"field": "id"},
            )

        if not isinstance(self.capability, str) or self.capability == "":
            raise NervaError(
                "INVALID_INPUT",
                message="workflow step capability must be a non-empty string",
                details={"field": "capability"},
            )

        if self.args is None:
            normalized_args: dict[str, Any] = {}
        elif isinstance(self.args, Mapping):
            normalized_args = dict(self.args)
        else:
            raise NervaError(
                "INVALID_INPUT",
                message="workflow step args must be a mapping or None",
                details={"field": "args"},
            )

        if not all(isinstance(key, str) for key in normalized_args):
            raise NervaError(
                "INVALID_INPUT",
                message="workflow step args keys must be strings",
                details={"field": "args"},
            )

        if self.depends_on is None:
            normalized_depends_on: tuple[str, ...] = ()
        elif isinstance(self.depends_on, tuple):
            normalized_depends_on = self.depends_on
        else:
            raise NervaError(
                "INVALID_INPUT",
                message="depends_on must be a tuple or None",
                details={"field": "depends_on"},
            )

        if not all(isinstance(dependency, str) for dependency in normalized_depends_on):
            raise NervaError(
                "INVALID_INPUT",
                message="depends_on entries must be strings",
                details={"field": "depends_on"},
            )

        if len(set(normalized_depends_on)) != len(normalized_depends_on):
            raise NervaError(
                "INVALID_INPUT",
                message="depends_on entries must be unique",
                details={"field": "depends_on"},
            )

        object.__setattr__(
            self,
            "args",
            MappingProxyType(normalized_args),
        )

        object.__setattr__(
            self,
            "depends_on",
            normalized_depends_on,
        )


@dataclass(frozen=True)
class Workflow:
    steps: tuple[WorkflowStep, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.steps, tuple):
            raise NervaError(
                "INVALID_INPUT",
                message="workflow steps must be a tuple",
                details={"field": "steps"},
            )

        if not self.steps:
            raise NervaError(
                "INVALID_INPUT",
                message="workflow steps must not be empty",
                details={"field": "steps"},
            )

        if not all(isinstance(step, WorkflowStep) for step in self.steps):
            raise NervaError(
                "INVALID_INPUT",
                message="workflow steps must contain only WorkflowStep instances",
                details={"field": "steps"},
            )

        step_ids = [step.id for step in self.steps]

        if len(set(step_ids)) != len(step_ids):
            raise NervaError(
                "INVALID_INPUT",
                message="workflow step ids must be unique",
                details={"field": "steps"},
            )

        known_ids = set(step_ids)

        for step in self.steps:
            assert step.depends_on is not None

            for dependency in step.depends_on:
                if dependency not in known_ids:
                    raise NervaError(
                        "INVALID_INPUT",
                        message=("workflow dependency does not reference an existing step"),
                        details={
                            "field": "depends_on",
                            "step_id": step.id,
                            "dependency": dependency,
                        },
                    )

                if dependency == step.id:
                    raise NervaError(
                        "INVALID_INPUT",
                        message="workflow step must not depend on itself",
                        details={
                            "field": "depends_on",
                            "step_id": step.id,
                        },
                    )

        self._validate_acyclic()

    def _validate_acyclic(self) -> None:
        dependencies: dict[str, tuple[str, ...]] = {}

        for step in self.steps:
            assert step.depends_on is not None
            dependencies[step.id] = step.depends_on

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(step_id: str) -> None:
            if step_id in visited:
                return

            if step_id in visiting:
                raise NervaError(
                    "INVALID_INPUT",
                    message="workflow dependency graph must be acyclic",
                    details={"step_id": step_id},
                )

            visiting.add(step_id)

            for dependency in dependencies[step_id]:
                visit(dependency)

            visiting.remove(step_id)
            visited.add(step_id)

        for step in self.steps:
            visit(step.id)


@dataclass(frozen=True)
class WorkflowResult:
    workflow_id: str
    outputs: Mapping[str, Any]
    duration_ms: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "outputs",
            MappingProxyType(dict(self.outputs)),
        )


class Orchestrator:
    def __init__(
        self,
        *,
        executor: Executor,
    ) -> None:
        self._executor = executor

    async def invoke(
        self,
        workflow: Workflow,
        context: ExecContext,
    ) -> WorkflowResult:
        if not isinstance(workflow, Workflow):
            raise NervaError(
                "INVALID_INPUT",
                message="workflow must be a Workflow",
                details={"field": "workflow"},
            )

        if not isinstance(context, ExecContext):
            raise NervaError(
                "INVALID_INPUT",
                message="context must be an ExecContext",
                details={"field": "context"},
            )

        workflow_id = str(uuid4())
        started_ns = time.monotonic_ns()

        completed: set[str] = set()
        started: set[str] = set()
        outputs: dict[str, Any] = {}

        running: dict[
            asyncio.Task[ExecutionResult],
            WorkflowStep,
        ] = {}

        try:
            while len(completed) < len(workflow.steps):
                ready_steps = [
                    step
                    for step in workflow.steps
                    if self._is_ready(
                        step=step,
                        started=started,
                        completed=completed,
                    )
                ]

                for step in ready_steps:
                    started.add(step.id)

                    task = asyncio.create_task(
                        self._invoke_step(
                            step=step,
                            context=context,
                        )
                    )

                    running[task] = step

                if not running:
                    raise NervaError(
                        "INTERNAL_ERROR",
                        message=("workflow execution reached an invalid scheduler state"),
                        request_id=context.request_id,
                    )

                done, _ = await asyncio.wait(
                    running,
                    return_when=asyncio.FIRST_COMPLETED,
                )

                selected_error: NervaError | None = None

                for task in done:
                    step = running.pop(task)

                    try:
                        execution_result = task.result()

                    except NervaError as exc:
                        if selected_error is None:
                            selected_error = exc

                    except asyncio.CancelledError:
                        if selected_error is None:
                            selected_error = NervaError(
                                "CANCELLED",
                                request_id=context.request_id,
                            )

                    except Exception as exc:  # noqa: BLE001
                        if selected_error is None:
                            selected_error = NervaError(
                                "WORKER_FAILED",
                                request_id=context.request_id,
                                details={
                                    "exception_type": type(exc).__name__,
                                },
                            )

                    else:
                        completed.add(step.id)
                        outputs[step.id] = execution_result.output

                if selected_error is not None:
                    await self._cancel_and_drain(running)
                    raise selected_error

            duration_ms = (time.monotonic_ns() - started_ns) // 1_000_000

            return WorkflowResult(
                workflow_id=workflow_id,
                outputs=outputs,
                duration_ms=duration_ms,
            )

        except asyncio.CancelledError as exc:
            await self._cancel_and_drain(running)

            raise NervaError(
                "CANCELLED",
                request_id=context.request_id,
            ) from exc

    async def _invoke_step(
        self,
        *,
        step: WorkflowStep,
        context: ExecContext,
    ) -> ExecutionResult:
        assert step.args is not None

        args = dict(step.args)

        return await self._executor.invoke(
            step.capability,
            args,
            context,
        )

    @staticmethod
    def _is_ready(
        *,
        step: WorkflowStep,
        started: set[str],
        completed: set[str],
    ) -> bool:
        if step.id in started:
            return False

        assert step.depends_on is not None

        return all(dependency in completed for dependency in step.depends_on)

    @staticmethod
    async def _cancel_and_drain(
        running: dict[
            asyncio.Task[ExecutionResult],
            WorkflowStep,
        ],
    ) -> None:
        tasks = tuple(running)

        for task in tasks:
            if not task.done():
                task.cancel()

        if tasks:
            await asyncio.gather(
                *tasks,
                return_exceptions=True,
            )

        running.clear()
