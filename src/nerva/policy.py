from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from .errors import NervaError


@dataclass(frozen=True)
class RateLimitRule:
    max_requests: int
    window_ms: int

    def __post_init__(self) -> None:
        if type(self.max_requests) is not int or self.max_requests <= 0:
            raise NervaError(
                "INVALID_INPUT",
                message="max_requests must be a positive integer",
                details={"field": "max_requests"},
            )

        if type(self.window_ms) is not int or self.window_ms <= 0:
            raise NervaError(
                "INVALID_INPUT",
                message="window_ms must be a positive integer",
                details={"field": "window_ms"},
            )


@dataclass(frozen=True)
class QuotaRule:
    limit: int
    unit: str

    def __post_init__(self) -> None:
        if type(self.limit) is not int or self.limit <= 0:
            raise NervaError(
                "INVALID_INPUT",
                message="quota limit must be a positive integer",
                details={"field": "limit"},
            )

        if not isinstance(self.unit, str) or not self.unit:
            raise NervaError(
                "INVALID_INPUT",
                message="quota unit must be a non-empty string",
                details={"field": "unit"},
            )


@dataclass(frozen=True)
class Rule:
    capability: str
    effect: str
    rate_limit: RateLimitRule | None = None
    quota: QuotaRule | None = None
    budget: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.capability, str) or not self.capability:
            raise NervaError(
                "INVALID_INPUT",
                message="capability must be a non-empty string",
                details={"field": "capability"},
            )

        if self.effect not in {"ALLOW", "DENY"}:
            raise NervaError(
                "INVALID_INPUT",
                message="effect must be ALLOW or DENY",
                details={"field": "effect"},
            )

        if self.rate_limit is None and self.quota is None and self.budget is None:
            raise NervaError(
                "INVALID_INPUT",
                message=("At least one of rate_limit, quota, or budget must be provided"),
            )

        if self.budget is not None and (type(self.budget) is not int or self.budget <= 0):
            raise NervaError(
                "INVALID_INPUT",
                message="budget must be a positive integer",
                details={"field": "budget"},
            )

    def matches(self, capability: str) -> bool:
        return self.capability == capability


@dataclass(frozen=True)
class PolicyDecision:
    effect: str
    reason: str
    matched_rule: int | None = None
    audit_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "effect": self.effect,
            "reason": self.reason,
            "matched_rule": self.matched_rule,
            "audit_id": self.audit_id,
        }


@dataclass(frozen=True)
class PolicyAuditRecord:
    timestamp: int
    capability: str
    context: dict[str, Any]
    decision: PolicyDecision
    state_delta: dict[str, int]

    def to_dict(self) -> dict[str, object]:
        return {
            "timestamp": self.timestamp,
            "capability": self.capability,
            "context": dict(self.context),
            "decision": self.decision.to_dict(),
            "state_delta": dict(self.state_delta),
        }


@dataclass(frozen=True)
class _Evaluation:
    decision: PolicyDecision
    error_code: str | None
    next_state: dict[str, dict[str, int]]
    state_delta: dict[str, int]


class Policy:
    def __init__(self, rules: list[Rule]) -> None:
        if not isinstance(rules, list):
            raise NervaError(
                "INVALID_INPUT",
                message="rules must be a list",
                details={"field": "rules"},
            )

        if not all(isinstance(rule, Rule) for rule in rules):
            raise NervaError(
                "INVALID_INPUT",
                message="rules must contain only Rule objects",
                details={"field": "rules"},
            )

        self._rules = list(rules)
        self._counters: dict[str, dict[str, int]] = {}
        self._audit_log: list[PolicyAuditRecord] = []

    def evaluate(
        self,
        capability: str,
        context: dict[str, Any],
    ) -> PolicyDecision:
        self._validate_request(capability, context)

        evaluation = self._evaluate_internal(
            capability=capability,
            context=context,
            now_ms=self._now_ms(),
        )

        return evaluation.decision

    def enforce(
        self,
        capability: str,
        context: dict[str, Any],
    ) -> PolicyDecision:
        self._validate_request(capability, context)

        now_ms = self._now_ms()

        evaluation = self._evaluate_internal(
            capability=capability,
            context=context,
            now_ms=now_ms,
        )

        audit_id = str(uuid4())

        decision = PolicyDecision(
            effect=evaluation.decision.effect,
            reason=evaluation.decision.reason,
            matched_rule=evaluation.decision.matched_rule,
            audit_id=audit_id,
        )

        if evaluation.error_code is None:
            self._counters = evaluation.next_state

        record = PolicyAuditRecord(
            timestamp=now_ms,
            capability=capability,
            context=self._summarize_context(context),
            decision=decision,
            state_delta=dict(evaluation.state_delta),
        )
        self._audit_log.append(record)

        if evaluation.error_code is not None:
            raise NervaError(
                evaluation.error_code,
                message=decision.reason,
                details={
                    "capability": capability,
                    "audit_id": audit_id,
                },
            )

        return decision

    def get_audit_log(self) -> list[dict[str, object]]:
        return [record.to_dict() for record in self._audit_log]

    def _evaluate_internal(
        self,
        *,
        capability: str,
        context: dict[str, Any],
        now_ms: int,
    ) -> _Evaluation:
        matched_index, rule = self._find_rule(capability)

        if rule is None:
            return self._deny(
                reason="No matching rule (deny by default)",
                error_code="PERMISSION_DENIED",
            )

        if rule.effect == "DENY":
            return self._deny(
                reason="Explicit deny by rule",
                error_code="PERMISSION_DENIED",
                matched_rule=matched_index,
            )

        subject = context.get("subject", "anonymous")
        scope = f"{capability}:{subject}"

        next_state = {key: dict(value) for key, value in self._counters.items()}
        state_delta: dict[str, int] = {}

        if rule.rate_limit is not None:
            error = self._evaluate_rate_limit(
                rule=rule.rate_limit,
                scope=scope,
                now_ms=now_ms,
                next_state=next_state,
                state_delta=state_delta,
                matched_rule=matched_index,
            )
            if error is not None:
                return error

        if rule.quota is not None:
            usage = self._positive_context_integer(
                context=context,
                field="usage",
            )

            error = self._evaluate_quota(
                rule=rule.quota,
                scope=scope,
                usage=usage,
                next_state=next_state,
                state_delta=state_delta,
                matched_rule=matched_index,
            )
            if error is not None:
                return error

        if rule.budget is not None:
            cost = self._positive_context_integer(
                context=context,
                field="cost",
            )

            error = self._evaluate_budget(
                budget=rule.budget,
                scope=scope,
                cost=cost,
                next_state=next_state,
                state_delta=state_delta,
                matched_rule=matched_index,
            )
            if error is not None:
                return error

        return _Evaluation(
            decision=PolicyDecision(
                effect="ALLOW",
                reason="All constraints satisfied",
                matched_rule=matched_index,
            ),
            error_code=None,
            next_state=next_state,
            state_delta=state_delta,
        )

    def _evaluate_rate_limit(
        self,
        *,
        rule: RateLimitRule,
        scope: str,
        now_ms: int,
        next_state: dict[str, dict[str, int]],
        state_delta: dict[str, int],
        matched_rule: int | None,
    ) -> _Evaluation | None:
        key = f"rate:{scope}"

        state = dict(
            next_state.get(
                key,
                {
                    "count": 0,
                    "window_start": now_ms,
                },
            )
        )

        window_start = state["window_start"]

        if now_ms >= window_start + rule.window_ms:
            state = {
                "count": 0,
                "window_start": now_ms,
            }

        if state["count"] >= rule.max_requests:
            return self._deny(
                reason="Rate limit exceeded",
                error_code="RATE_LIMIT_EXCEEDED",
                matched_rule=matched_rule,
            )

        state["count"] += 1
        next_state[key] = state
        state_delta[key] = 1

        return None

    def _evaluate_quota(
        self,
        *,
        rule: QuotaRule,
        scope: str,
        usage: int,
        next_state: dict[str, dict[str, int]],
        state_delta: dict[str, int],
        matched_rule: int | None,
    ) -> _Evaluation | None:
        key = f"quota:{scope}:{rule.unit}"
        current = next_state.get(key, {}).get("usage", 0)

        if current + usage > rule.limit:
            return self._deny(
                reason="Quota exceeded",
                error_code="QUOTA_EXCEEDED",
                matched_rule=matched_rule,
            )

        next_state[key] = {"usage": current + usage}
        state_delta[key] = usage

        return None

    def _evaluate_budget(
        self,
        *,
        budget: int,
        scope: str,
        cost: int,
        next_state: dict[str, dict[str, int]],
        state_delta: dict[str, int],
        matched_rule: int | None,
    ) -> _Evaluation | None:
        key = f"budget:{scope}"
        current = next_state.get(key, {}).get("spent", 0)

        if current + cost > budget:
            return self._deny(
                reason="Budget exceeded",
                error_code="BUDGET_EXCEEDED",
                matched_rule=matched_rule,
            )

        next_state[key] = {"spent": current + cost}
        state_delta[key] = cost

        return None

    def _find_rule(
        self,
        capability: str,
    ) -> tuple[int | None, Rule | None]:
        for index, rule in enumerate(self._rules):
            if rule.matches(capability):
                return index, rule

        return None, None

    @staticmethod
    def _deny(
        *,
        reason: str,
        error_code: str,
        matched_rule: int | None = None,
    ) -> _Evaluation:
        return _Evaluation(
            decision=PolicyDecision(
                effect="DENY",
                reason=reason,
                matched_rule=matched_rule,
            ),
            error_code=error_code,
            next_state={},
            state_delta={},
        )

    @staticmethod
    def _validate_request(
        capability: str,
        context: dict[str, Any],
    ) -> None:
        if not isinstance(capability, str) or not capability:
            raise NervaError(
                "INVALID_INPUT",
                message="capability must be a non-empty string",
                details={"field": "capability"},
            )

        if not isinstance(context, dict):
            raise NervaError(
                "INVALID_INPUT",
                message="context must be a dictionary",
                details={"field": "context"},
            )

    @staticmethod
    def _positive_context_integer(
        *,
        context: dict[str, Any],
        field: str,
    ) -> int:
        value = context.get(field, 1)

        if type(value) is not int or value <= 0:
            raise NervaError(
                "INVALID_INPUT",
                message=f"{field} must be a positive integer",
                details={"field": field},
            )

        return value

    @staticmethod
    def _summarize_context(
        context: dict[str, Any],
    ) -> dict[str, Any]:
        summary: dict[str, Any] = {
            "subject": context.get("subject", "anonymous"),
        }

        for field in ("resource", "usage", "cost"):
            if field in context:
                summary[field] = context[field]

        return summary

    @staticmethod
    def _now_ms() -> int:
        return int(time.time() * 1000)
