from __future__ import annotations

import asyncio
import inspect
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any
from uuid import uuid4

from .context import ExecContext
from .errors import NervaError
from .policy import Policy
from .registry import Registry

CapabilityCallable = Callable[
    [dict[str, Any], ExecContext],
    Awaitable[Any],
]


def _empty_metadata() -> Mapping[str, Any]:
    return MappingProxyType({})


@dataclass(frozen=True)
class ExecutionResult:
    """Canonical successful result of a Layer 2 capability invocation."""

    execution_id: str
    capability: str
    output: Any
    duration_ms: int
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)


@dataclass(frozen=True)
class CapabilityHandler:
    """Executable contract stored in Registry for a capability."""

    version: str
    handler: CapabilityCallable
    description: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.version, str) or self.version == "":
            raise NervaError(
                "INVALID_INPUT",
                message="version must be a non-empty string",
                details={"field": "version"},
            )

        if not callable(self.handler):
            raise NervaError(
                "INVALID_INPUT",
                message="handler must be callable",
                details={"field": "handler"},
            )

        if self.description is not None and not isinstance(
            self.description,
            str,
        ):
            raise NervaError(
                "INVALID_INPUT",
                message="description must be a string or None",
                details={"field": "description"},
            )


class Executor:
    """Transport-neutral Layer 2 capability executor."""

    def __init__(
        self,
        *,
        registry: Registry,
        policy: Policy,
    ) -> None:
        self._registry = registry
        self._policy = policy

    async def invoke(
        self,
        capability: str,
        args: dict[str, Any] | None,
        context: ExecContext,
    ) -> ExecutionResult:
        normalized_args = self._validate_invocation(
            capability=capability,
            args=args,
            context=context,
        )

        effective_deadline_ms = self._timing_preflight(context)

        policy_context = {
            "subject": context.user_id,
        }

        self._policy.enforce(
            capability,
            policy_context,
        )

        registered = self._registry.get(capability)

        if not isinstance(registered, CapabilityHandler):
            raise NervaError(
                "CAPABILITY_UNSUPPORTED",
                details={"capability": capability},
            )

        remaining_seconds = self._remaining_seconds(
            effective_deadline_ms,
        )

        started_ns = time.monotonic_ns()

        try:
            result = registered.handler(
                normalized_args,
                context,
            )

            if not inspect.isawaitable(result):
                raise NervaError(
                    "CAPABILITY_UNSUPPORTED",
                    details={"capability": capability},
                )

            output = await self._await_handler(
                result,
                remaining_seconds,
            )

        except asyncio.CancelledError as exc:
            raise NervaError(
                "CANCELLED",
                request_id=context.request_id,
            ) from exc

        except (KeyboardInterrupt, SystemExit):
            raise

        except NervaError as exc:
            if exc.code == "CAPABILITY_UNSUPPORTED":
                raise

            raise NervaError(
                "WORKER_FAILED",
                details={
                    "exception_type": type(exc).__name__,
                },
                request_id=context.request_id,
            ) from exc

        except TimeoutError as exc:
            raise NervaError(
                "EXECUTION_TIMEOUT",
                request_id=context.request_id,
            ) from exc

        except Exception as exc:
            raise NervaError(
                "WORKER_FAILED",
                details={
                    "exception_type": type(exc).__name__,
                },
                request_id=context.request_id,
            ) from exc

        duration_ms = (time.monotonic_ns() - started_ns) // 1_000_000

        return ExecutionResult(
            execution_id=str(uuid4()),
            capability=capability,
            output=output,
            duration_ms=duration_ms,
            metadata=MappingProxyType({}),
        )

    @staticmethod
    def _validate_invocation(
        *,
        capability: Any,
        args: Any,
        context: Any,
    ) -> dict[str, Any]:
        if not isinstance(capability, str) or capability == "":
            raise NervaError(
                "INVALID_INPUT",
                message="capability must be a non-empty string",
                details={"field": "capability"},
            )

        if args is None:
            normalized_args: dict[str, Any] = {}
        elif isinstance(args, dict):
            normalized_args = args
        else:
            raise NervaError(
                "INVALID_INPUT",
                message="args must be a dictionary or None",
                details={"field": "args"},
            )

        if not isinstance(context, ExecContext):
            raise NervaError(
                "INVALID_INPUT",
                message="context must be an ExecContext",
                details={"field": "context"},
            )

        return normalized_args

    @staticmethod
    def _timing_preflight(
        context: ExecContext,
    ) -> int | None:
        now_ms = int(time.time() * 1000)

        deadline_ms = context.deadline_unix_ms
        timeout_ms = context.timeout_ms

        if deadline_ms is not None and now_ms >= deadline_ms:
            raise NervaError(
                "EXECUTION_TIMEOUT",
                request_id=context.request_id,
            )

        if timeout_ms is not None and deadline_ms is not None:
            return min(
                now_ms + timeout_ms,
                deadline_ms,
            )

        if timeout_ms is not None:
            return now_ms + timeout_ms

        if deadline_ms is not None:
            return deadline_ms

        return None

    @staticmethod
    def _remaining_seconds(
        effective_deadline_ms: int | None,
    ) -> float | None:
        if effective_deadline_ms is None:
            return None

        now_ms = time.time() * 1000
        remaining_ms = effective_deadline_ms - now_ms

        if remaining_ms <= 0:
            raise NervaError(
                "EXECUTION_TIMEOUT",
            )

        return remaining_ms / 1000.0

    @staticmethod
    async def _await_handler(
        awaitable: Awaitable[Any],
        timeout_seconds: float | None,
    ) -> Any:
        if timeout_seconds is None:
            return await awaitable

        return await asyncio.wait_for(
            awaitable,
            timeout=timeout_seconds,
        )
