from types import MappingProxyType
from uuid import uuid4

import pytest

from nerva.observability import EventType, Observation


def make_observation(**overrides: object) -> Observation:
    values: dict[str, object] = {
        "event_id": str(uuid4()),
        "event_type": EventType.CAPABILITY_INVOCATION_STARTED,
        "timestamp_unix_ms": 1,
        "request_id": "req-1",
        "workflow_id": None,
        "step_id": None,
        "capability_id": "cap-1",
        "attributes": {"source": "test"},
    }
    values.update(overrides)
    return Observation(**values)  # type: ignore[arg-type]


def test_event_type_catalog_is_closed_and_complete() -> None:
    assert tuple(EventType) == (
        EventType.CAPABILITY_INVOCATION_STARTED,
        EventType.CAPABILITY_INVOCATION_COMPLETED,
        EventType.CAPABILITY_INVOCATION_FAILED,
        EventType.WORKFLOW_INVOCATION_STARTED,
        EventType.WORKFLOW_STEP_STARTED,
        EventType.WORKFLOW_STEP_COMPLETED,
        EventType.WORKFLOW_STEP_FAILED,
        EventType.WORKFLOW_CANCELLATION_REQUESTED,
        EventType.WORKFLOW_INVOCATION_COMPLETED,
        EventType.WORKFLOW_INVOCATION_FAILED,
    )


def test_event_type_catalog_values_are_stable() -> None:
    assert [item.value for item in EventType] == [
        "capability.invocation.started",
        "capability.invocation.completed",
        "capability.invocation.failed",
        "workflow.invocation.started",
        "workflow.step.started",
        "workflow.step.completed",
        "workflow.step.failed",
        "workflow.cancellation.requested",
        "workflow.invocation.completed",
        "workflow.invocation.failed",
    ]


def test_observation_accepts_valid_values() -> None:
    event_id = str(uuid4())

    observation = Observation(
        event_id=event_id,
        event_type=EventType.WORKFLOW_STEP_STARTED,
        timestamp_unix_ms=0,
        request_id="req-1",
        workflow_id="wf-1",
        step_id="step-1",
        capability_id="cap-1",
        attributes={"attempt": 1},
    )

    assert observation.event_id == event_id
    assert observation.event_type is EventType.WORKFLOW_STEP_STARTED
    assert observation.timestamp_unix_ms == 0
    assert observation.request_id == "req-1"
    assert observation.workflow_id == "wf-1"
    assert observation.step_id == "step-1"
    assert observation.capability_id == "cap-1"
    assert observation.attributes == {"attempt": 1}


def test_observation_is_immutable() -> None:
    observation = make_observation()

    with pytest.raises(AttributeError, match="Observation is immutable"):
        observation.request_id = "changed"


def test_attributes_are_immutable() -> None:
    source = {"attempt": 1}
    observation = make_observation(attributes=source)

    assert isinstance(observation.attributes, MappingProxyType)

    source["attempt"] = 2
    assert observation.attributes["attempt"] == 1

    with pytest.raises(TypeError):
        observation.attributes["attempt"] = 3  # type: ignore[index]


@pytest.mark.parametrize(
    "event_id",
    [
        "",
        "not-a-uuid",
        "550E8400-E29B-41D4-A716-446655440000",
    ],
)
def test_rejects_non_canonical_event_id(event_id: str) -> None:
    with pytest.raises(ValueError):
        make_observation(event_id=event_id)


def test_rejects_non_event_type() -> None:
    with pytest.raises(TypeError, match="event_type must be an EventType"):
        make_observation(event_type="workflow.step.started")


@pytest.mark.parametrize(
    "timestamp",
    [
        -1,
        True,
        1.5,
        "1",
    ],
)
def test_rejects_invalid_timestamp(timestamp: object) -> None:
    with pytest.raises(ValueError):
        make_observation(timestamp_unix_ms=timestamp)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("request_id", ""),
        ("workflow_id", ""),
        ("step_id", ""),
        ("capability_id", ""),
    ],
)
def test_rejects_empty_identifier(field: str, value: str) -> None:
    with pytest.raises(ValueError):
        make_observation(**{field: value})


def test_rejects_non_mapping_attributes() -> None:
    with pytest.raises(TypeError, match="attributes must be a mapping"):
        make_observation(attributes=["not", "a", "mapping"])