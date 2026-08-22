from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from types import MappingProxyType
from uuid import UUID


class EventType(str, Enum):
    CAPABILITY_INVOCATION_STARTED = "capability.invocation.started"
    CAPABILITY_INVOCATION_COMPLETED = "capability.invocation.completed"
    CAPABILITY_INVOCATION_FAILED = "capability.invocation.failed"

    WORKFLOW_INVOCATION_STARTED = "workflow.invocation.started"
    WORKFLOW_STEP_STARTED = "workflow.step.started"
    WORKFLOW_STEP_COMPLETED = "workflow.step.completed"
    WORKFLOW_STEP_FAILED = "workflow.step.failed"
    WORKFLOW_CANCELLATION_REQUESTED = "workflow.cancellation.requested"
    WORKFLOW_INVOCATION_COMPLETED = "workflow.invocation.completed"
    WORKFLOW_INVOCATION_FAILED = "workflow.invocation.failed"


class Observation:
    event_id: str
    event_type: EventType
    timestamp_unix_ms: int
    request_id: str
    workflow_id: str | None
    step_id: str | None
    capability_id: str | None
    attributes: Mapping[str, object]

    def __init__(
        self,
        *,
        event_id: str,
        event_type: EventType,
        timestamp_unix_ms: int,
        request_id: str,
        workflow_id: str | None = None,
        step_id: str | None = None,
        capability_id: str | None = None,
        attributes: Mapping[str, object] | None = None,
    ) -> None:
        self._validate_event_id(event_id)
        self._validate_event_type(event_type)
        self._validate_timestamp(timestamp_unix_ms)
        self._validate_required_string("request_id", request_id)
        self._validate_optional_string("workflow_id", workflow_id)
        self._validate_optional_string("step_id", step_id)
        self._validate_optional_string("capability_id", capability_id)

        if attributes is None:
            validated_attributes: dict[str, object] = {}
        elif not isinstance(attributes, Mapping):
            raise TypeError("attributes must be a mapping")
        else:
            validated_attributes = dict(attributes)

        object.__setattr__(self, "event_id", event_id)
        object.__setattr__(self, "event_type", event_type)
        object.__setattr__(self, "timestamp_unix_ms", timestamp_unix_ms)
        object.__setattr__(self, "request_id", request_id)
        object.__setattr__(self, "workflow_id", workflow_id)
        object.__setattr__(self, "step_id", step_id)
        object.__setattr__(self, "capability_id", capability_id)
        object.__setattr__(
            self,
            "attributes",
            MappingProxyType(validated_attributes),
        )
        object.__setattr__(self, "_initialized", True)

    def __setattr__(self, name: str, value: object) -> None:
        if getattr(self, "_initialized", False):
            raise AttributeError("Observation is immutable")

        object.__setattr__(self, name, value)

    @staticmethod
    def _validate_event_id(event_id: str) -> None:
        if not isinstance(event_id, str) or not event_id:
            raise ValueError("event_id must be a non-empty UUID string")

        try:
            parsed = UUID(event_id)
        except (ValueError, AttributeError) as exc:
            raise ValueError("event_id must be a valid UUID string") from exc

        if str(parsed) != event_id:
            raise ValueError("event_id must use canonical UUID string form")

    @staticmethod
    def _validate_event_type(event_type: EventType) -> None:
        if not isinstance(event_type, EventType):
            raise TypeError("event_type must be an EventType")

    @staticmethod
    def _validate_timestamp(timestamp_unix_ms: int) -> None:
        if (
            not isinstance(timestamp_unix_ms, int)
            or isinstance(timestamp_unix_ms, bool)
            or timestamp_unix_ms < 0
        ):
            raise ValueError(
                "timestamp_unix_ms must be a non-negative integer"
            )

    @staticmethod
    def _validate_required_string(name: str, value: str) -> None:
        if not isinstance(value, str) or not value:
            raise ValueError(f"{name} must be a non-empty string")

    @staticmethod
    def _validate_optional_string(
        name: str,
        value: str | None,
    ) -> None:
        if value is not None and (
            not isinstance(value, str) or not value
        ):
            raise ValueError(
                f"{name} must be None or a non-empty string"
            )