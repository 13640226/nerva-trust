ERROR_CATALOG: dict[str, dict[str, object]] = {
    "EXECUTION_TIMEOUT": {
        "category": "deadline_exceeded",
        "default_message": ("The operation exceeded its permitted execution deadline or timeout."),
        "retryable": True,
    },
    "CANCELLED": {
        "category": "cancelled",
        "default_message": "The operation was cancelled.",
        "retryable": False,
    },
    "WORKER_FAILED": {
        "category": "internal",
        "default_message": (
            "A worker execution scope failed without exposing unsafe internal diagnostics."
        ),
        "retryable": False,
    },
    "INTERNAL_ERROR": {
        "category": "internal",
        "default_message": "An unexpected internal error occurred.",
        "retryable": False,
    },
    "PERMISSION_DENIED": {
        "category": "authorization",
        "default_message": ("The requested operation is not permitted by the active policy."),
        "retryable": False,
    },
    "RATE_LIMIT_EXCEEDED": {
        "category": "resource_exhausted",
        "default_message": "The operation exceeded an applicable rate limit.",
        "retryable": True,
    },
    "QUOTA_EXCEEDED": {
        "category": "resource_exhausted",
        "default_message": "The operation exceeded an applicable quota.",
        "retryable": False,
    },
    "BUDGET_EXCEEDED": {
        "category": "resource_exhausted",
        "default_message": "The operation exceeded the assigned budget.",
        "retryable": False,
    },
    "RESOURCE_EXHAUSTED": {
        "category": "resource_exhausted",
        "default_message": "The system resources are exhausted.",
        "retryable": True,
    },
    "INVALID_INPUT": {
        "category": "invalid_argument",
        "default_message": "The input is structurally invalid.",
        "retryable": False,
    },
    "SCHEMA_VALIDATION_FAILED": {
        "category": "invalid_argument",
        "default_message": ("Input or output did not satisfy the declared schema contract."),
        "retryable": False,
    },
    "NOT_FOUND": {
        "category": "not_found",
        "default_message": "The requested resource or handler was not found.",
        "retryable": False,
    },
    "ALREADY_EXISTS": {
        "category": "conflict",
        "default_message": "The resource already exists.",
        "retryable": False,
    },
    "CONFLICT": {
        "category": "conflict",
        "default_message": "The operation conflicts with the current state.",
        "retryable": False,
    },
    "UNAVAILABLE": {
        "category": "unavailable",
        "default_message": "The service or resource is currently unavailable.",
        "retryable": True,
    },
    "UNSUPPORTED_VERSION": {
        "category": "invalid_argument",
        "default_message": "The requested version is not supported.",
        "retryable": False,
    },
    "CAPABILITY_UNSUPPORTED": {
        "category": "invalid_argument",
        "default_message": ("The requested capability is not supported by this implementation."),
        "retryable": False,
    },
    "SERIALIZATION_FAILED": {
        "category": "invalid_argument",
        "default_message": "The serialization or deserialization process failed.",
        "retryable": False,
    },
}


class NervaError(Exception):
    def __init__(
        self,
        code: str,
        *,
        message: str | None = None,
        request_id: str | None = None,
        category: str | None = None,
        retryable: bool | None = None,
        details: dict[str, object] | None = None,
        cause_code: str | None = None,
    ) -> None:
        entry = ERROR_CATALOG.get(code)

        if entry is None:
            resolved_category = category or "internal"
            resolved_retryable = False if retryable is None else retryable
            resolved_message = message or code
        else:
            resolved_category = category or str(entry["category"])
            resolved_retryable = bool(entry["retryable"]) if retryable is None else retryable
            resolved_message = message or str(entry["default_message"])

        super().__init__(resolved_message)

        self.code = code
        self.category = resolved_category
        self.message = resolved_message
        self.retryable = resolved_retryable
        self.request_id = request_id
        self.details = details or {}
        self.cause_code = cause_code

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "category": self.category,
            "message": self.message,
            "retryable": self.retryable,
            "details": self.details,
            "cause_code": self.cause_code,
            "request_id": self.request_id,
        }
