from __future__ import annotations

from typing import Any

from .errors import NervaError


class Registry:
    """Transport-neutral registry for values addressed by unique string IDs."""

    def __init__(self) -> None:
        self._items: dict[str, Any] = {}

    def register(self, id: str, value: Any) -> None:
        self._validate_id(id)

        if id in self._items:
            raise NervaError(
                "ALREADY_EXISTS",
                message=f"Item with id '{id}' already exists",
                details={"id": id},
            )

        self._items[id] = value

    def get(self, id: str) -> Any:
        self._validate_id(id)

        try:
            return self._items[id]
        except KeyError:
            raise NervaError(
                "NOT_FOUND",
                message=f"Item with id '{id}' not found",
                details={"id": id},
            ) from None

    def unregister(self, id: str) -> None:
        self._validate_id(id)

        if id not in self._items:
            raise NervaError(
                "NOT_FOUND",
                message=f"Item with id '{id}' not found",
                details={"id": id},
            )

        del self._items[id]

    def list(self) -> set[str]:
        return set(self._items)

    @staticmethod
    def _validate_id(id: str) -> None:
        if not isinstance(id, str):
            raise NervaError(
                "INVALID_INPUT",
                message="id must be a string",
                details={"field": "id"},
            )

        if id == "":
            raise NervaError(
                "INVALID_INPUT",
                message="id must not be empty",
                details={"field": "id"},
            )
