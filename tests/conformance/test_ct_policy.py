import pytest

from nerva.errors import NervaError
from nerva.policy import (
    Policy,
    PolicyDecision,
    QuotaRule,
    RateLimitRule,
    Rule,
)


def test_policy_decision_is_immutable() -> None:
    decision = PolicyDecision(
        effect="ALLOW",
        reason="Allowed",
    )

    with pytest.raises(AttributeError):
        decision.effect = "DENY"


def test_rule_rejects_invalid_effect() -> None:
    with pytest.raises(NervaError) as exc:
        Rule(
            capability="read",
            effect="MAYBE",
            budget=1,
        )

    assert exc.value.code == "INVALID_INPUT"


def test_rule_rejects_bool_numeric_values() -> None:
    with pytest.raises(NervaError):
        RateLimitRule(
            max_requests=True,
            window_ms=1000,
        )

    with pytest.raises(NervaError):
        QuotaRule(
            limit=True,
            unit="requests",
        )

    with pytest.raises(NervaError):
        Rule(
            capability="read",
            effect="ALLOW",
            budget=True,
        )


def test_evaluate_is_pure() -> None:
    policy = Policy(
        [
            Rule(
                capability="read",
                effect="ALLOW",
                rate_limit=RateLimitRule(
                    max_requests=1,
                    window_ms=1000,
                ),
            )
        ]
    )

    first = policy.evaluate(
        "read",
        {"subject": "alice"},
    )
    second = policy.evaluate(
        "read",
        {"subject": "alice"},
    )

    assert first.effect == "ALLOW"
    assert second.effect == "ALLOW"
    assert policy.get_audit_log() == []


def test_enforce_commits_rate_limit_state() -> None:
    policy = Policy(
        [
            Rule(
                capability="read",
                effect="ALLOW",
                rate_limit=RateLimitRule(
                    max_requests=1,
                    window_ms=1000,
                ),
            )
        ]
    )

    decision = policy.enforce(
        "read",
        {"subject": "alice"},
    )

    assert decision.effect == "ALLOW"

    with pytest.raises(NervaError) as exc:
        policy.enforce(
            "read",
            {"subject": "alice"},
        )

    assert exc.value.code == "RATE_LIMIT_EXCEEDED"


def test_quota_uses_usage() -> None:
    policy = Policy(
        [
            Rule(
                capability="read",
                effect="ALLOW",
                quota=QuotaRule(
                    limit=3,
                    unit="requests",
                ),
            )
        ]
    )

    policy.enforce(
        "read",
        {
            "subject": "alice",
            "usage": 2,
        },
    )

    with pytest.raises(NervaError) as exc:
        policy.enforce(
            "read",
            {
                "subject": "alice",
                "usage": 2,
            },
        )

    assert exc.value.code == "QUOTA_EXCEEDED"


def test_budget_uses_cost() -> None:
    policy = Policy(
        [
            Rule(
                capability="write",
                effect="ALLOW",
                budget=3,
            )
        ]
    )

    policy.enforce(
        "write",
        {
            "subject": "alice",
            "cost": 2,
        },
    )

    with pytest.raises(NervaError) as exc:
        policy.enforce(
            "write",
            {
                "subject": "alice",
                "cost": 2,
            },
        )

    assert exc.value.code == "BUDGET_EXCEEDED"


def test_invalid_input_does_not_create_audit_record() -> None:
    policy = Policy(
        [
            Rule(
                capability="read",
                effect="ALLOW",
                quota=QuotaRule(
                    limit=10,
                    unit="requests",
                ),
            )
        ]
    )

    with pytest.raises(NervaError) as exc:
        policy.enforce(
            "read",
            {
                "usage": True,
            },
        )

    assert exc.value.code == "INVALID_INPUT"
    assert policy.get_audit_log() == []
