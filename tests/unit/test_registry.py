import pytest

from nerva.errors import NervaError
from nerva.registry import Registry


class TestRegistry:
    def test_register_and_get(self) -> None:
        reg = Registry()
        reg.register("a", 42)
        assert reg.get("a") == 42

    def test_register_duplicate(self) -> None:
        reg = Registry()
        reg.register("a", 1)
        with pytest.raises(NervaError) as exc:
            reg.register("a", 2)
        assert exc.value.code == "ALREADY_EXISTS"

    def test_get_not_found(self) -> None:
        reg = Registry()
        with pytest.raises(NervaError) as exc:
            reg.get("missing")
        assert exc.value.code == "NOT_FOUND"

    def test_unregister(self) -> None:
        reg = Registry()
        reg.register("a", 42)
        reg.unregister("a")
        with pytest.raises(NervaError):
            reg.get("a")

    def test_unregister_not_found(self) -> None:
        reg = Registry()
        with pytest.raises(NervaError) as exc:
            reg.unregister("missing")
        assert exc.value.code == "NOT_FOUND"

    def test_list(self) -> None:
        reg = Registry()
        reg.register("x", 1)
        reg.register("y", 2)
        assert reg.list() == {"x", "y"}

    def test_invalid_id_empty(self) -> None:
        reg = Registry()
        with pytest.raises(NervaError) as exc:
            reg.register("", 123)
        assert exc.value.code == "INVALID_INPUT"

    def test_invalid_id_non_string(self) -> None:
        reg = Registry()
        with pytest.raises(NervaError) as exc:
            reg.register(123, "test")  # type: ignore[arg-type]
        assert exc.value.code == "INVALID_INPUT"