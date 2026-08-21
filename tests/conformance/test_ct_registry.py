import pytest

from nerva.errors import NervaError
from nerva.registry import Registry


def test_ct_reg_001_register_and_get() -> None:
    registry = Registry()

    registry.register("alpha", "value")

    assert registry.get("alpha") == "value"


def test_ct_reg_002_duplicate_raises_already_exists() -> None:
    registry = Registry()
    registry.register("alpha", 1)

    with pytest.raises(NervaError) as exc:
        registry.register("alpha", 2)

    assert exc.value.code == "ALREADY_EXISTS"


def test_ct_reg_003_missing_get_raises_not_found() -> None:
    registry = Registry()

    with pytest.raises(NervaError) as exc:
        registry.get("missing")

    assert exc.value.code == "NOT_FOUND"


def test_ct_reg_004_missing_unregister_raises_not_found() -> None:
    registry = Registry()

    with pytest.raises(NervaError) as exc:
        registry.unregister("missing")

    assert exc.value.code == "NOT_FOUND"


def test_ct_reg_005_list_matches_registered_ids_as_set() -> None:
    registry = Registry()
    registry.register("a", 1)
    registry.register("b", 2)

    assert set(registry.list()) == {"a", "b"}


def test_ct_reg_006_unregister_removes_item() -> None:
    registry = Registry()
    registry.register("alpha", "value")

    registry.unregister("alpha")

    with pytest.raises(NervaError) as exc:
        registry.get("alpha")

    assert exc.value.code == "NOT_FOUND"


def test_ct_reg_007_transport_neutral_api() -> None:
    registry = Registry()

    registry.register("alpha", "value")
    value = registry.get("alpha")
    ids = registry.list()
    registry.unregister("alpha")

    assert value == "value"
    assert set(ids) == {"alpha"}


def test_ct_reg_008_state_changes_are_observable() -> None:
    registry = Registry()

    registry.register("alpha", 1)
    assert registry.get("alpha") == 1
    assert "alpha" in registry.list()

    registry.unregister("alpha")

    assert "alpha" not in registry.list()


def test_ct_reg_009_invalid_id_raises_invalid_input() -> None:
    registry = Registry()

    with pytest.raises(NervaError) as exc:
        registry.register("", "value")

    assert exc.value.code == "INVALID_INPUT"

    with pytest.raises(NervaError) as exc:
        registry.register(None, "value")  # type: ignore[arg-type]

    assert exc.value.code == "INVALID_INPUT"
