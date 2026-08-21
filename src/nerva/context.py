from __future__ import annotations

import copy
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from .errors import NervaError

SUPPORTED_VERSION = "1.0"

FORBIDDEN_METADATA_KEYS = {
    "password",
    "token",
    "secret",
    "credential",
    "authorization",
}


def _is_forbidden_key(key: str) -> bool:
    return key.lower() in FORBIDDEN_METADATA_KEYS


def _contains_forbidden_key(obj: Any) -> tuple[bool, str]:
    if isinstance(obj, Mapping):
        for key, value in obj.items():
            key_text = str(key)

            if _is_forbidden_key(key_text):
                return True, key_text

            found, found_key = _contains_forbidden_key(value)
            if found:
                return True, found_key

    elif isinstance(obj, (list, tuple)):
        for item in obj:
            found, found_key = _contains_forbidden_key(item)
            if found:
                return True, found_key

    return False, ""


def _deep_freeze(obj: Any) -> Any:
    if isinstance(obj, Mapping):
        frozen = {
            str(key): _deep_freeze(value)
            for key, value in obj.items()
        }
        return MappingProxyType(frozen)

    if isinstance(obj, (list, tuple)):
        return tuple(_deep_freeze(value) for value in obj)

    return obj


def _deep_thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _deep_thaw(item)
            for key, item in value.items()
        }

    if isinstance(value, tuple):
        return [_deep_thaw(item) for item in value]

    return value


@dataclass(frozen=True, init=False)
class ExecContext:
    request_id: str
    user_id: str
    session_id: str | None
    trace_id: str | None
    timeout_ms: int | None
    deadline_unix_ms: int | None
    version: str
    capabilities: tuple[str, ...]
    metadata: Mapping[str, Any]

    def __init__(
        self,
        request_id: str,
        user_id: str,
        *,
        session_id: str | None = None,
        trace_id: str | None = None,
        timeout_ms: int | None = None,
        deadline_unix_ms: int | None = None,
        version: str = SUPPORTED_VERSION,
        capabilities: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._validate_required_ids(
            request_id=request_id,
            user_id=user_id,
        )

        self._validate_optional_strings(
            session_id=session_id,
            trace_id=trace_id,
        )

        self._validate_timing(
            timeout_ms=timeout_ms,
            deadline_unix_ms=deadline_unix_ms,
        )

        self._validate_version(version)

        validated_capabilities = self._validate_capabilities(capabilities)
        validated_metadata = self._validate_metadata(metadata)

        object.__setattr__(self, "request_id", request_id)
        object.__setattr__(self, "user_id", user_id)
        object.__setattr__(self, "session_id", session_id)
        object.__setattr__(self, "trace_id", trace_id)
        object.__setattr__(self, "timeout_ms", timeout_ms)
        object.__setattr__(
            self,
            "deadline_unix_ms",
            deadline_unix_ms,
        )
        object.__setattr__(self, "version", version)

        object.__setattr__(
            self,
            "capabilities",
            tuple(validated_capabilities),
        )

        object.__setattr__(
            self,
            "metadata",
            _deep_freeze(copy.deepcopy(validated_metadata)),
        )

    @staticmethod
    def _validate_required_ids(
        *,
        request_id: str,
        user_id: str,
    ) -> None:
        if not isinstance(request_id, str) or not request_id:
            raise NervaError(
                "SCHEMA_VALIDATION_FAILED",
                message="request_id must be a non-empty string",
                details={"field": "request_id"},
            )

        if not isinstance(user_id, str) or not user_id:
            raise NervaError(
                "SCHEMA_VALIDATION_FAILED",
                message="user_id must be a non-empty string",
                details={"field": "user_id"},
            )

    @staticmethod
    def _validate_optional_strings(
        *,
        session_id: str | None,
        trace_id: str | None,
    ) -> None:
        if session_id is not None and not isinstance(session_id, str):
            raise NervaError(
                "SCHEMA_VALIDATION_FAILED",
                message="session_id must be a string or None",
                details={"field": "session_id"},
            )

        if trace_id is not None and not isinstance(trace_id, str):
            raise NervaError(
                "SCHEMA_VALIDATION_FAILED",
                message="trace_id must be a string or None",
                details={"field": "trace_id"},
            )

    @staticmethod
    def _validate_timing(
        *,
        timeout_ms: int | None,
        deadline_unix_ms: int | None,
    ) -> None:
        if timeout_ms is not None and (
            type(timeout_ms) is not int or timeout_ms <= 0
        ):
            raise NervaError(
                "SCHEMA_VALIDATION_FAILED",
                message="timeout_ms must be a positive integer",
                details={"field": "timeout_ms"},
            )

        if deadline_unix_ms is not None and (
            type(deadline_unix_ms) is not int or deadline_unix_ms <= 0
        ):
            raise NervaError(
                "SCHEMA_VALIDATION_FAILED",
                message="deadline_unix_ms must be a positive integer",
                details={"field": "deadline_unix_ms"},
            )

    @staticmethod
    def _validate_version(version: str) -> None:
        if not isinstance(version, str):
            raise NervaError(
                "SCHEMA_VALIDATION_FAILED",
                message="version must be a string",
                details={"field": "version"},
            )

        if version != SUPPORTED_VERSION:
            raise NervaError(
                "UNSUPPORTED_VERSION",
                message=f"Unsupported version: {version}",
                details={"field": "version"},
            )

    @staticmethod
    def _validate_capabilities(
        capabilities: list[str] | None,
    ) -> list[str]:
        if capabilities is None:
            return []

        if not isinstance(capabilities, list):
            raise NervaError(
                "SCHEMA_VALIDATION_FAILED",
                message="capabilities must be a list of strings",
                details={"field": "capabilities"},
            )

        if not all(isinstance(item, str) for item in capabilities):
            raise NervaError(
                "SCHEMA_VALIDATION_FAILED",
                message="capabilities must be a list of strings",
                details={"field": "capabilities"},
            )

        return capabilities

    @staticmethod
    def _validate_metadata(
        metadata: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if metadata is None:
            return {}

        if not isinstance(metadata, dict):
            raise NervaError(
                "SCHEMA_VALIDATION_FAILED",
                message="metadata must be a dictionary",
                details={"field": "metadata"},
            )

        forbidden_found, forbidden_key = _contains_forbidden_key(metadata)

        if forbidden_found:
            raise NervaError(
                "SCHEMA_VALIDATION_FAILED",
                message=(
                    "Credential-bearing fields are forbidden "
                    "in ExecContext metadata"
                ),
                details={"field": forbidden_key},
            )

        return metadata

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "request_id": self.request_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "trace_id": self.trace_id,
            "timeout_ms": self.timeout_ms,
            "deadline_unix_ms": self.deadline_unix_ms,
            "capabilities": list(self.capabilities),
            "metadata": _deep_thaw(self.metadata),
        }

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> ExecContext:
        allowed_fields = {
            "version",
            "request_id",
            "user_id",
            "session_id",
            "trace_id",
            "timeout_ms",
            "deadline_unix_ms",
            "capabilities",
            "metadata",
        }

        unknown_fields = set(data) - allowed_fields

        if unknown_fields:
            raise NervaError(
                "SCHEMA_VALIDATION_FAILED",
                message=f"Unknown fields: {sorted(unknown_fields)}",
                details={
                    "fields": sorted(unknown_fields),
                },
            )

        return cls(**data)
