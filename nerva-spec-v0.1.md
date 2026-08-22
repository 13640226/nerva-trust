# Nerva Specification v0.1

**Status:** RECONSTRUCTED WITH EXPLICIT REVISIONS
**Conformance Scope:** Layer 0, Layer 1, Layer 2 (Spec), and Layer 3
**Reference Implementation:** Python
**Transport Binding:** None

---

## 1. Status of This Specification

The original source document for Nerva Specification v0.1 is no longer available.

This document is a controlled reconstruction of the normative contracts that are demonstrably implemented and tested in the current Nerva reference repository for Layers 0 and 1.

**Layer 2** (Capability Invocation & Execution) is an **Explicit Semantic Revision** added to this version. It is not derived from historical implementation or tests.

Normative material in this document is derived from:

1. the current Python reference implementation (Layers 0 & 1);
2. surviving conformance tests (Layers 0 & 1);
3. surviving unit tests where needed to clarify implemented behavior;
4. repository history and requirement identifiers;
5. previously adopted explicit semantic revisions that are reflected by the current conformant implementation;
6. explicit semantic revision for Layer 2 (`R-EXEC-001..012`).

This reconstruction MUST NOT be interpreted as defining requirements beyond the surviving implementation and tests, plus the explicitly defined Layer 2 revision.

---

## 2. Conformance Language

The key words MUST, MUST NOT, REQUIRED, SHALL, SHALL NOT, SHOULD, SHOULD NOT, and MAY are to be interpreted as normative requirements.

An implementation is CONFORMANT only when:

1. all requirements applicable to the component are implemented;
2. all relevant conformance tests pass;
3. static type checking passes under the project configuration;
4. formatting and lint gates pass;
5. CI passes on the supported Python versions.

A component MUST NOT be declared CONFORMANT solely because its source code has been written.

---

## 3. Layer 0 — Core Context and Canonical Errors

Layer 0 consists of:

- ExecContext
- NervaError

---

## 4. ExecContext

### 4.1 Data Model

The canonical execution context contains:

- version
- request_id
- user_id
- session_id
- trace_id
- timeout_ms
- deadline_unix_ms
- capabilities
- metadata

The supported context version is:

```text
1.0
```

The logical Python model is equivalent to:

```python
ExecContext(
    request_id: str,
    user_id: str,
    *,
    session_id: str | None = None,
    trace_id: str | None = None,
    timeout_ms: int | None = None,
    deadline_unix_ms: int | None = None,
    version: str = "1.0",
    capabilities: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
)
```

#### R-CTX-001 — Required Identifiers

`request_id` and `user_id` MUST each be non-empty strings.

Invalid values MUST raise:

```text
SCHEMA_VALIDATION_FAILED
```

#### R-CTX-002 — Optional Identifiers

`session_id` and `trace_id` MUST each be either:

- a string; or
- `None`.

Any other value MUST raise:

```text
SCHEMA_VALIDATION_FAILED
```

#### R-CTX-003 — Timing Values

`timeout_ms`, when present, MUST be a positive integer.

`deadline_unix_ms`, when present, MUST be a positive integer.

Boolean values MUST NOT be accepted as integers.

Therefore:

```python
True
False
```

are invalid timing values.

Invalid timing values MUST raise:

```text
SCHEMA_VALIDATION_FAILED
```

#### R-CTX-004 — Version

`version` MUST be a string.

The only supported version in Specification v0.1 is:

```text
1.0
```

A non-string version MUST raise:

```text
SCHEMA_VALIDATION_FAILED
```

A syntactically valid but unsupported version MUST raise:

```text
UNSUPPORTED_VERSION
```

#### R-CTX-005 — Capabilities

`capabilities` MUST be either:

- `None`; or
- a list consisting only of strings.

`None` is normalized to an empty capability collection.

The stored representation MUST be immutable.

Invalid capability structures MUST raise:

```text
SCHEMA_VALIDATION_FAILED
```

Capability strings are opaque strings at the ExecContext layer.

#### R-CTX-006 — Metadata

`metadata` MUST be either:

- `None`; or
- a dictionary.

`None` is normalized to an empty mapping.

Invalid metadata structures MUST raise:

```text
SCHEMA_VALIDATION_FAILED
```

#### R-CTX-007 — Canonical Plain Representation

`to_dict()` MUST return a plain mutable wire representation containing:

- version
- request_id
- user_id
- session_id
- trace_id
- timeout_ms
- deadline_unix_ms
- capabilities
- metadata

Immutable internal tuples MUST be thawed into lists.

Immutable internal mappings MUST be thawed recursively into dictionaries.

The following round trip MUST hold for valid contexts:

```python
ExecContext.from_dict(ctx.to_dict()) == ctx
```

#### R-CTX-008 — Unknown Fields

`ExecContext.from_dict()` MUST reject fields outside the canonical field set.

Unknown fields MUST raise:

```text
SCHEMA_VALIDATION_FAILED
```

No silent preservation or ignoring of unknown fields is permitted.

#### R-CTX-009 — Deep Immutability

ExecContext MUST be immutable after construction.

Nested metadata MUST also be immutable.

The canonical recursive freeze behavior is:

```text
dict / Mapping -> immutable Mapping
list / tuple    -> tuple
scalar          -> unchanged
```

Mutating source objects after construction MUST NOT mutate the stored context.

The internal metadata representation MUST therefore be isolated from the caller's mutable objects.

#### R-CTX-010 — Credential-Bearing Metadata

Credential-bearing fields MUST NOT appear anywhere inside metadata.

The check MUST be:

- recursive;
- case-insensitive.

The canonical forbidden metadata keys are:

- password
- token
- secret
- credential
- authorization

A forbidden key at any nested depth MUST raise:

```text
SCHEMA_VALIDATION_FAILED
```

Credential-bearing values MUST NOT be admitted merely because they are nested inside lists, tuples, or mappings.

---

## 5. Canonical Error Model

### 5.1 NervaError

The canonical exception type is:

```text
NervaError
```

Its logical fields are:

- code
- category
- message
- retryable
- details
- cause_code
- request_id

Its plain representation MUST NOT be wrapped in an outer `"error"` object.

The canonical serialization shape is:

```python
{
    "code": ...,
    "category": ...,
    "message": ...,
    "retryable": ...,
    "details": ...,
    "cause_code": ...,
    "request_id": ...,
}
```

#### R-ERROR-001 — Catalog-Driven Errors

Known error codes MUST resolve their default:

- category;
- message;
- retryability

from the canonical error catalog.

Explicit constructor overrides MAY replace applicable defaults.

#### R-ERROR-002 — Unknown Error Codes

An unknown error code MUST remain representable.

For an unknown code:

```text
category  = "internal"
retryable = false
message   = explicit message, otherwise the code itself
```

unless explicitly overridden where the API permits.

#### R-ERROR-003 — Error Serialization

`NervaError.to_dict()` MUST return the canonical error object directly.

It MUST NOT produce:

```python
{"error": {...}}
```

or another transport-specific envelope.

The error model is transport-neutral.

#### R-ERROR-004 — Cause and Request Correlation

`cause_code`, when supplied, MUST be preserved.

`request_id`, when supplied, MUST be preserved.

The error object MUST NOT require a transport protocol in order to carry either value.

---

## 6. Canonical Error Catalog

Specification v0.1 defines exactly 18 canonical error codes.

| Code | Category | Retryable |
|---|---|---:|
| EXECUTION_TIMEOUT | deadline_exceeded | true |
| CANCELLED | cancelled | false |
| WORKER_FAILED | internal | false |
| INTERNAL_ERROR | internal | false |
| PERMISSION_DENIED | authorization | false |
| RATE_LIMIT_EXCEEDED | resource_exhausted | true |
| QUOTA_EXCEEDED | resource_exhausted | false |
| BUDGET_EXCEEDED | resource_exhausted | false |
| RESOURCE_EXHAUSTED | resource_exhausted | true |
| INVALID_INPUT | invalid_argument | false |
| SCHEMA_VALIDATION_FAILED | invalid_argument | false |
| NOT_FOUND | not_found | false |
| ALREADY_EXISTS | conflict | false |
| CONFLICT | conflict | false |
| UNAVAILABLE | unavailable | true |
| UNSUPPORTED_VERSION | invalid_argument | false |
| CAPABILITY_UNSUPPORTED | invalid_argument | false |
| SERIALIZATION_FAILED | invalid_argument | false |

The catalog MUST contain exactly these 18 codes for conformance with this reconstructed v0.1 contract.

---

## 7. Layer 1 — Registry and Policy

Layer 1 consists of:

- Registry
- Policy

Both components are transport-neutral.

---

## 8. Registry

The Registry stores arbitrary values under unique string identifiers.

Its public API is:

```python
register(id, value)
get(id)
unregister(id)
list()
```

#### R-REG-001 — Identifier Validation

A Registry identifier MUST be a string.

It MUST NOT be empty.

An invalid identifier MUST raise:

```text
INVALID_INPUT
```

#### R-REG-002 — Register

`register(id, value)` MUST associate `value` with `id`.

The Registry MAY store arbitrary Python values.

#### R-REG-003 — Duplicate Registration

Registering an identifier that is already present MUST fail with:

```text
ALREADY_EXISTS
```

Existing state MUST NOT be silently overwritten.

#### R-REG-004 — Get

`get(id)` MUST return the value associated with a registered identifier.

#### R-REG-005 — Missing Get

Calling `get(id)` for an identifier that is not registered MUST raise:

```text
NOT_FOUND
```

#### R-REG-006 — Unregister

`unregister(id)` MUST remove the registered identifier.

Calling `unregister(id)` for a missing identifier MUST raise:

```text
NOT_FOUND
```

#### R-REG-007 — List

`list()` MUST expose the set of currently registered identifiers.

Output ordering is undefined.

Conformance MUST therefore compare identifier membership as a set rather than relying on sequence order.

#### R-REG-008 — Transport Neutrality

Registry operations MUST NOT depend on HTTP, RPC, sockets, message queues, or another transport mechanism.

Transport-specific status codes or envelopes MUST NOT form part of the Registry contract.

#### R-REG-009 — Observable State

Successful mutations MUST be observable through subsequent Registry operations.

After:

```python
register(id, value)
```

then:

```python
get(id)
```

MUST observe the registered value.

After:

```python
unregister(id)
```

the identifier MUST no longer appear in `list()` and `get(id)` MUST behave as missing.

---

## 9. Policy

### 9.1 Policy Data Types

#### RateLimitRule

```python
@dataclass(frozen=True)
class RateLimitRule:
    max_requests: int
    window_ms: int
```

Both numeric values MUST be true integers and MUST be greater than zero.

Boolean values MUST be rejected.

#### QuotaRule

```python
@dataclass(frozen=True)
class QuotaRule:
    limit: int
    unit: str
```

`limit` MUST be a true positive integer.

Boolean values MUST be rejected.

`unit` MUST be a non-empty string.

#### Rule

```python
@dataclass(frozen=True)
class Rule:
    capability: str
    effect: str
    rate_limit: RateLimitRule | None = None
    quota: QuotaRule | None = None
    budget: int | None = None
```

- `capability` MUST be a non-empty string.
- `effect` MUST be exactly one of `ALLOW` or `DENY`.
- At least one of `rate_limit`, `quota`, or `budget` MUST be present.
- `budget`, when present, MUST be a true positive integer.
- Boolean values MUST be rejected as budget values.

#### PolicyDecision

```python
@dataclass(frozen=True)
class PolicyDecision:
    effect: str
    reason: str
    matched_rule: int | None = None
    audit_id: str | None = None
```

PolicyDecision MUST be immutable.

#### PolicyAuditRecord

```python
@dataclass(frozen=True)
class PolicyAuditRecord:
    timestamp: int
    capability: str
    context: dict[str, Any]
    decision: PolicyDecision
    state_delta: dict[str, int]
```

#### R-POLICY-001 — Deny by Default

Policy evaluation MUST be deny-by-default.

If no Rule exactly matches the requested capability:

```text
effect = DENY
```

`evaluate()` MUST return a DENY PolicyDecision.

`enforce()` MUST record the DENY and raise:

```text
PERMISSION_DENIED
```

#### R-POLICY-002 — Exact Capability Matching

Capability matching MUST use exact string equality.

Matching is case-sensitive.

Wildcard matching MUST NOT be implied.

Regular-expression matching MUST NOT be implied.

For example:

```text
read != Read
```

#### R-POLICY-003 — Deterministic Rule Selection

Rules MUST be examined in insertion order.

The first exact capability match MUST determine the applicable Rule.

Later Rules with the same capability MUST NOT override the first match.

An applicable Rule whose effect is `DENY` MUST produce a denied policy decision regardless of later matching Rules.

#### R-POLICY-004 — Pure and State-Aware Evaluation

The public evaluation operation is:

```python
evaluate(
    capability: str,
    context: dict[str, Any],
) -> PolicyDecision
```

`evaluate()` MUST NOT mutate policy counters.

`evaluate()` MUST NOT append audit records.

However, purity MUST NOT mean ignoring current state.

Evaluation MUST inspect the existing counter state and compute the decision that would result from the request without committing the calculated next state.

Repeated evaluation alone therefore MUST NOT consume rate, quota, or budget.

#### R-POLICY-005 — Enforcement

The public enforcement operation is:

```python
enforce(
    capability: str,
    context: dict[str, Any],
) -> PolicyDecision
```

`enforce()` is the only public operation permitted to commit policy consumption state.

On ALLOW:

- calculated state changes MUST be committed;
- an audit record MUST be appended;
- a PolicyDecision MUST be returned.

On policy DENY:

- consumption state MUST NOT be committed;
- an audit record MUST be appended;
- the applicable NervaError MUST be raised.

Every policy-valid `enforce()` decision, including DENY, MUST receive an audit identifier.

#### R-POLICY-006 — Constraint Priority

Constraints MUST be considered in the following logical order:

1. Capability / applicable Rule
2. Rate Limit
3. Quota
4. Budget

If a stage denies the request, subsequent constraint stages MUST NOT produce committed consumption.

#### R-POLICY-007 — Rate Limit

Rate limiting is scoped to:

```text
capability + subject
```

The subject is read from:

```python
context["subject"]
```

If absent:

```text
subject = "anonymous"
```

A rate-limit state contains:

- count
- window_start

A fresh state begins with count zero and the current timestamp as the window start.

The rate window resets when:

```text
now >= window_start + window_ms
```

A request MUST be denied when the existing count is already greater than or equal to `max_requests`.

The denial code is:

```text
RATE_LIMIT_EXCEEDED
```

A successful request increments the rate counter by exactly:

```text
1
```

Its audit `state_delta` MUST record that request-local increment rather than the resulting total.

#### R-POLICY-008 — Quota and Budget

##### Quota

Quota is scoped to:

```text
capability + subject + unit
```

Request consumption is obtained from:

```python
context["usage"]
```

If absent:

```text
usage = 1
```

When a quota Rule is active, `usage` MUST be a true positive integer.

Boolean, zero, negative, and non-integer usage values MUST raise:

```text
INVALID_INPUT
```

Quota denial occurs when:

```text
current_usage + usage > limit
```

The denial code is:

```text
QUOTA_EXCEEDED
```

The request-local audit delta MUST equal `usage`.

##### Budget

Budget is scoped to:

```text
capability + subject
```

Request cost is obtained from:

```python
context["cost"]
```

If absent:

```text
cost = 1
```

When a budget Rule is active, `cost` MUST be a true positive integer.

Boolean, zero, negative, and non-integer cost values MUST raise:

```text
INVALID_INPUT
```

Budget denial occurs when:

```text
current_spent + cost > budget
```

The denial code is:

```text
BUDGET_EXCEEDED
```

The request-local audit delta MUST equal `cost`.

`usage` MUST only be validated when a quota constraint is applicable.

`cost` MUST only be validated when a budget constraint is applicable.

#### R-POLICY-009 — Atomic State Commit and Audit

Policy constraint evaluation MUST use a calculated next-state separate from the currently committed counter state.

If the complete request is allowed, the calculated state becomes the new committed state.

If the request is denied by any policy constraint:

```text
no calculated consumption is committed
```

For denied requests:

```python
state_delta == {}
```

For allowed requests, `state_delta` MUST describe only the consumption caused by the current request.

The Audit Record MUST contain:

- timestamp
- capability
- context
- decision
- state_delta

The audit context MUST be an allow-listed summary.

It MUST always contain:

```text
subject
```

with:

```text
anonymous
```

as the default.

It MAY additionally contain only these request fields when supplied:

- resource
- usage
- cost

Other context keys MUST NOT be copied into the audit context.

#### R-POLICY-010 — API Validation and Policy Errors

At the Policy API boundary:

- `capability` MUST be a non-empty string.
- `context` MUST be a dictionary.

Invalid API input MUST raise:

```text
INVALID_INPUT
```

Invalid input MUST NOT produce an Audit Record.

Constraint-specific denials MUST use:

```text
PERMISSION_DENIED
RATE_LIMIT_EXCEEDED
QUOTA_EXCEEDED
BUDGET_EXCEEDED
```

as applicable.

A DENY raised by `enforce()` MUST occur only after the corresponding valid policy decision has been recorded in the Audit Log.

---

## 10. Transport Neutrality

Layer 0 and Layer 1 contracts are transport-neutral.

Nothing in this specification requires:

- HTTP;
- REST;
- WebSocket;
- gRPC;
- JSON-RPC;
- message queues;
- a specific agent protocol.

Transport adapters MAY be defined by a future specification, but no such adapter semantics are defined by Nerva Specification v0.1 as reconstructed here.

---

## 11. Serialization Boundaries

ExecContext and NervaError expose plain object representations suitable for transport-independent serialization.

These plain representations MUST NOT be interpreted as requiring a particular wire codec.

JSON MAY serialize compatible values, but JSON itself is not made normative by this specification.

---

## 12. Security Boundaries

ExecContext metadata MUST NOT serve as a credential transport.

The canonical forbidden credential-bearing metadata names are:

- password
- token
- secret
- credential
- authorization

Policy Audit Records MUST NOT indiscriminately copy request context.

Only the allow-listed policy context fields defined in R-POLICY-009 may be recorded by the reconstructed v0.1 Policy Audit contract.

---

## 13. Conformance Inventory

The surviving conformance surface covers:

### ExecContext

```text
R-CTX-001 .. R-CTX-010
```

including:

- required IDs;
- optional strings;
- timing;
- version;
- capabilities;
- metadata;
- serialization round trip;
- unknown fields;
- deep immutability;
- credential rejection.

### Canonical Errors

The conformance suite verifies:

- exact 18-code catalog;
- unknown-code fallback;
- transport-neutral serialization;
- cause/request correlation;
- canonical semantics for selected error codes.

### Registry

```text
R-REG-001 .. R-REG-009
```

including:

- register/get;
- duplicate behavior;
- missing behavior;
- list semantics;
- unregister behavior;
- transport neutrality;
- state observability;
- invalid IDs.

### Policy

The surviving implementation and tests establish the reconstructed Policy contract described by:

```text
R-POLICY-001 .. R-POLICY-010
```

This identifier mapping is retained for continuity with the Layer 1 implementation history.

The original source text for the one-to-one R-POLICY requirement mapping is not available; therefore this section is a reconstructed normative mapping of the currently conformant implementation.

---

## 14. Known Reconstruction Notes

### RN-001 — Original Source Unavailable

The original `nerva-spec-v0.1.md` was not found in:

- the current repository;
- available Git history;
- available branches;
- available tags;
- the local project search performed during reconstruction.

This file is therefore explicitly marked RECONSTRUCTED.

### RN-002 — Error Catalog Correction

The surviving implementation and conformance tests define exactly 18 canonical error codes.

`INTERNAL_ERROR` is one of those 18 codes.

Any earlier project summary omitting `INTERNAL_ERROR` is superseded by the current conformant implementation and conformance suite for the purposes of this reconstructed document.

### RN-003 — Policy Requirement Mapping

The repository history identifies Policy implementation as covering:

```text
R-POLICY-001 .. R-POLICY-010
```

The original normative prose assigning exact text to those ten identifiers is unavailable.

The requirement mapping in this reconstructed document represents the observable contract of the current conformant implementation.

### RN-004 — No Layer 2 (historical)

At the time of initial reconstruction, no surviving source defined Layer 2.

### RN-005 — Layer 2 as Explicit Semantic Revision

Layer 2 (Capability Invocation & Execution) is an Explicit Semantic Revision added to this specification.

It is not derived from historical implementation, tests, or reconstructed material.

Its requirements are:

```text
R-EXEC-001 .. R-EXEC-012
```

as defined in the Layer 2 section below.

Implementation and conformance tests for Layer 2 are pending and will follow the adoption of this specification.

---

## 15. Layer 2 — Capability Invocation & Execution

**Status:** CONFORMANT
**Revision Type:** EXPLICIT SEMANTIC REVISION
**Depends On:** Layer 0 (ExecContext, NervaError), Layer 1 (Registry, Policy)

#### R-EXEC-001 — Scope and Responsibilities

Layer 2 is responsible for:

- receiving a capability request with structured arguments and an `ExecContext`;
- resolving the capability via `Registry`;
- enforcing policy via `Policy` before execution;
- invoking the resolved executable;
- normalizing execution outcomes into a canonical `ExecutionResult` or `NervaError`;
- preserving transport neutrality.

Layer 2 MUST NOT define:

- HTTP, gRPC, WebSocket, or other transport bindings;
- agent orchestration or workflow logic;
- persistent state or database access;
- agent discovery or authentication protocols;
- distributed retry semantics.

#### R-EXEC-002 — ExecutionResult

`ExecutionResult` represents the successful outcome of a capability invocation.

Logical shape:

```python
@dataclass(frozen=True)
class ExecutionResult:
    execution_id: str
    capability: str
    output: Any
    duration_ms: int
    metadata: Mapping[str, Any]
```

`execution_id` MUST be a UUID string in canonical form.

`capability` MUST match the requested capability.

`output` is opaque to Layer 2; no deep-freeze is required.

`duration_ms` MUST be measured using a monotonic clock.

`metadata` MUST be immutable.

In v0.1, `metadata` SHALL be an empty immutable mapping.

Layer 2 MUST NOT invent or infer metadata from ExecContext, Policy, Registry, or handler output.

#### R-EXEC-003 — CapabilityHandler

The executable contract for a registered capability is:

```python
CapabilityCallable = Callable[
    [dict[str, Any], ExecContext],
    Awaitable[Any],
]


@dataclass(frozen=True)
class CapabilityHandler:
    version: str
    handler: CapabilityCallable
    description: str | None = None
```

Only async handlers are supported.

`version` MUST be a non-empty string.

`description` MAY be `None`; if provided, it MUST be a string.

At construction time:

- `handler` MUST be callable.
- Violations of the above MUST raise `INVALID_INPUT`.

At invocation time:

- `handler(args, exec_context)` MUST produce an Awaitable.
- If the returned value is not an Awaitable, Layer 2 MUST raise `CAPABILITY_UNSUPPORTED`.

#### R-EXEC-004 — Invocation Validation

On entry to Layer 2:

- `capability` MUST be a non-empty string.
- `args` MUST be either:
  - a `dict[str, Any]`; or
  - `None`, which is normalized to `{}`.
- `context` MUST be a valid ExecContext.

Any violation MUST raise:

```text
INVALID_INPUT
```

#### R-EXEC-005 — Policy Bridge

The `Policy.enforce()` call SHALL receive a context built as:

```python
policy_context = {
    "subject": exec_context.user_id,
}
```

Layer 2 MUST NOT invent `usage`, `cost`, or `resource` fields.

These MAY be added in future revisions.

#### R-EXEC-006 — Execution Ordering and Policy Finality

The canonical invocation flow SHALL be:

1. Validate inputs (`capability`, `args`, `context`).
2. Perform timing preflight as defined by R-EXEC-007.
   - If `deadline_unix_ms` is already expired, raise `EXECUTION_TIMEOUT` without Policy enforcement.
3. Call `Policy.enforce(capability, policy_context)`.
   - If DENY, raise the corresponding NervaError.
   - Policy consumption and audit are final for this invocation.
4. Call `Registry.get(capability)`.
   - If missing, propagate `NOT_FOUND`.
5. Validate that the obtained value is a `CapabilityHandler`.
   - If not, raise `CAPABILITY_UNSUPPORTED`.
6. Execute `handler(args, exec_context)` within the effective time bound.
7. Return `ExecutionResult`.

This ordering prevents capability probing by unauthorized callers.

A successful `Policy.enforce()` is final.

If subsequent Registry resolution, handler validation, timeout, cancellation, or execution failure occurs, Layer 2 MUST NOT roll back Policy state or Policy audit records.

Therefore:

```text
Expired before Policy
    -> EXECUTION_TIMEOUT
    -> no Policy consumption

Expires after successful Policy enforcement
    -> EXECUTION_TIMEOUT
    -> Policy consumption/audit remain final
```

#### R-EXEC-007 — Timeout and Deadline Semantics

`deadline_unix_ms` is compared against wall-clock Unix time.

`duration_ms` is measured using a monotonic clock.

The effective execution deadline SHALL be determined as follows.

If `deadline_unix_ms` is present and:

```text
now >= deadline_unix_ms
```

Layer 2 MUST raise `EXECUTION_TIMEOUT` immediately before Policy enforcement.

If both `timeout_ms` and `deadline_unix_ms` are present, the earliest bound applies:

```text
effective_deadline = min(now + timeout_ms, deadline_unix_ms)
```

If only `timeout_ms` is present:

```text
effective_deadline = now + timeout_ms
```

If only `deadline_unix_ms` is present:

```text
effective_deadline = deadline_unix_ms
```

If neither is present, no execution timeout is imposed by Layer 2.

No default timeout is introduced in this version.

#### R-EXEC-008 — Cancellation Semantics

`asyncio.CancelledError` raised during handler execution MUST be caught and normalized to:

```text
CANCELLED
```

The handler SHOULD be cancellation-aware, but this is not required.

#### R-EXEC-009 — Exception Normalization

Exceptions from handler execution MUST be normalized as follows:

| Exception | Resulting Code |
|---|---|
| Timeout enforced by Layer 2 | EXECUTION_TIMEOUT |
| `TimeoutError` | EXECUTION_TIMEOUT |
| `asyncio.TimeoutError` | EXECUTION_TIMEOUT |
| `asyncio.CancelledError` | CANCELLED |
| Any other `Exception` subclass | WORKER_FAILED |
| `KeyboardInterrupt`, `SystemExit` | Propagate |

For `WORKER_FAILED`, `details` SHALL contain at least:

```python
{"exception_type": "<class name>"}
```

Layer 2 MUST NOT automatically include the exception message in `details`, in order to avoid leaking sensitive data.

#### R-EXEC-010 — Registry Executable Contract

`Registry.get(capability)` MUST return a `CapabilityHandler` for the capability to be executable.

If the registered value is not a `CapabilityHandler`, Layer 2 MUST raise:

```text
CAPABILITY_UNSUPPORTED
```

#### R-EXEC-011 — Transport Neutrality

Layer 2 MUST NOT depend on any transport protocol.

It MUST NOT define:

- HTTP status codes;
- RPC envelopes;
- protocol-specific headers.

Input and output are Python objects, not serialized bytes.

#### R-EXEC-012 — State and Side-Effect Boundaries

Layer 2 SHALL remain stateless.

It MAY read state from Registry and Policy.

It MUST NOT introduce new persistent state.

It MUST NOT mutate ExecContext.

Any side effects beyond the invoked handler are out of scope.

---

## 16. Change Control

After adoption of this reconstructed specification with explicit revisions, changes MUST be classified as one of:

### Implementation Bug

The implementation violates an already-defined requirement.

### Spec Erratum

The normative text contains an accidental inconsistency with the agreed contract and requires correction without intentional semantic change.

### Explicit Semantic Revision

The intended behavior itself is deliberately changed or extended.

New Layer definitions MUST be Explicit Semantic Revisions unless an authoritative historical source is recovered.

---

## 17. Current Conformance State

At the time this reconstruction was finalized:

| Component | Status |
|---|---|
| Layer 0 / ExecContext | CONFORMANT ✅ |
| Layer 0 / NervaError | CONFORMANT ✅ |
| Layer 0 | CONFORMANT ✅ |
| Layer 1 / Registry | CONFORMANT ✅ |
| Layer 1 / Policy | CONFORMANT ✅ |
| Layer 1 | CONFORMANT ✅ |
| Layer 2 / Capability Invocation & Execution | CONFORMANT ⏳ |

The repository's current Layer 0 and Layer 1 implementations have passed their applicable local quality gates and project CI.

Layer 2 Specification has been adopted via Explicit Semantic Revision.

Layer 2 conformance tests and implementation are complete. The Capability Invocation & Execution implementation satisfies requirements R-EXEC-001 through R-EXEC-012 under the local conformance suite. Project CI has passed successfully on all supported Python versions (3.10, 3.11, 3.12). Layer 2 is now formally CONFORMANT.

---

## 18. Layer 3 — Workflow Orchestration

**Status:** CONFORMANT
**Revision Type:** EXPLICIT SEMANTIC REVISION
**Depends On:** Layer 0 (ExecContext, NervaError), Layer 2 (Capability Invocation & Execution)

Layer 3 defines transport-neutral orchestration of multiple capability invocations as an acyclic dependency graph.

Layer 3 MUST remain stateless.

Layer 3 MUST NOT define:

- transport bindings;
- persistence or checkpointing;
- distributed scheduling;
- capability discovery;
- observability;
- loops;
- conditional branching;
- automatic retry;
- fallback;
- compensation;
- inter-step data binding;
- new canonical error codes.

### 18.1 Canonical Data Model

#### R-WORKFLOW-001 — Workflow Definition

A workflow SHALL be represented as an immutable container of workflow steps.

The canonical stored logical model is:

```python
@dataclass(frozen=True)
class Workflow:
    steps: tuple[WorkflowStep, ...]

The following requirements apply:

steps MUST be a tuple in the canonical stored representation.
steps MUST contain only WorkflowStep instances.
steps MUST NOT be empty.
Tuple position MUST NOT by itself imply execution order.
Execution readiness and ordering MUST be determined only by the dependency graph defined by depends_on.
Forward references are permitted; a dependency MAY refer to a step appearing later in the steps tuple.
The Workflow object MUST be immutable after successful construction.
Workflow-wide structural validation, including identifier uniqueness, dependency resolution, and acyclicity, MUST complete before the Workflow is considered successfully constructed.
Violation of this requirement MUST raise INVALID_INPUT.
R-WORKFLOW-002 — Workflow Step Validation

Each workflow step SHALL have the canonical stored logical representation:

@dataclass(frozen=True)
class WorkflowStep:
    id: str
    capability: str
    args: Mapping[str, Any]
    depends_on: tuple[str, ...] = ()

At WorkflowStep construction:

id MUST be a non-empty string.
capability MUST be a non-empty string.
args MAY be supplied as None, in which case it MUST be normalized to an empty immutable mapping.
Otherwise, args MUST be a Mapping whose keys are strings.
The top-level stored args mapping MUST be immutable.
Construction MUST isolate the stored top-level mapping from subsequent mutation of the caller-supplied mapping.
Nested values contained within args are opaque to Layer 3 and are NOT required to be deep-frozen in this revision.
depends_on MAY be supplied as None, in which case it MUST be normalized to an empty tuple.
Otherwise, depends_on MUST be a tuple containing only strings.
Each dependency identifier within a single depends_on tuple MUST be unique.
The stored depends_on representation MUST be immutable.
Validation that depends on other steps in the Workflow, including identifier uniqueness, dependency existence, self-dependency, and cycle detection, MUST NOT be performed as a standalone WorkflowStep validation concern. Those requirements are enforced during Workflow construction.
Violation of local WorkflowStep validation MUST raise INVALID_INPUT.
R-WORKFLOW-003 — Step Identifier Uniqueness

Within a single Workflow, every WorkflowStep.id MUST be unique.

Identifier comparison MUST use exact, case-sensitive string equality.
For example, step-a and Step-A are different identifiers.
Two steps within the same Workflow MUST NOT have identical identifiers.
Identifier uniqueness MUST be validated during Workflow construction and before any capability invocation begins.
Violation of identifier uniqueness MUST raise INVALID_INPUT.
No capability MUST be invoked when Workflow construction fails this validation.
R-WORKFLOW-004 — Dependency Reference Validation

Every identifier appearing in WorkflowStep.depends_on MUST reference exactly one existing step within the same Workflow.

Dependency matching MUST use exact, case-sensitive string equality.

A step:

MAY have zero dependencies and therefore be a root step;
MAY depend on a step appearing before or after it in the steps tuple;
MUST NOT depend on itself;
MUST NOT reference an identifier that does not exist in the Workflow.

Dependency reference validation MUST occur during Workflow construction and before any capability invocation begins.

Acyclicity is a separate graph-level requirement defined by R-WORKFLOW-005.

Execution readiness after successful validation is defined by R-WORKFLOW-006.

Violation of dependency reference validity MUST raise INVALID_INPUT.

No capability MUST be invoked when Workflow construction fails this validation.

R-WORKFLOW-005 — Acyclic Graph Requirement

The dependency graph formed by all depends_on relationships within a single Workflow MUST be acyclic.

A cycle exists if there is a non-empty sequence of steps S1, S2, ..., Sn such that S1 depends on S2, S2 depends on S3, ..., and Sn depends on S1.

A step MUST NOT depend on itself, directly or indirectly.

Cycle detection MUST occur during Workflow construction and MUST complete before any capability invocation begins.

If a direct self-dependency, indirect cycle, or other cyclic structure is detected, Workflow construction MUST fail with INVALID_INPUT.

When Workflow construction fails this validation, no workflow step MAY be invoked.

The acyclicity requirement applies to the complete dependency graph regardless of step position in the steps tuple.

R-WORKFLOW-006 — Step Readiness

A workflow step is ready for execution only when all of the following are true:

execution of that step has not previously started;
workflow cancellation has not made the step ineligible to start;
every step identified by its depends_on tuple has completed successfully.

A step with an empty depends_on tuple is a root step and becomes ready when workflow execution begins, unless cancellation or workflow failure prevents it from starting.

Readiness MUST be re-evaluated as dependency executions complete.

A step that is not ready MAY become ready later when all of its dependencies succeed.

The Orchestrator MUST NOT invoke a step before it is ready.

A step whose execution has already started MUST NOT be invoked a second time.

If any dependency fails, the dependent step MUST NOT become ready.

When multiple independent steps are ready simultaneously, Layer 3 does not define an observable ordering between their starts.

R-WORKFLOW-007 — Step Execution

Each started WorkflowStep SHALL be executed through exactly one call to Layer 2:

Executor.invoke(
    step.capability,
    args,
    workflow_context,
)

For each invocation:

capability MUST equal the step's stored capability.
args MUST be a new plain dict[str, Any] shallowly projected from the step's stored args mapping.
The shallow projection MUST preserve the stored top-level key/value associations without semantic transformation.
The Orchestrator MUST NOT mutate the stored args mapping.
Deep copying of nested values is NOT required.
context MUST be the same ExecContext supplied to the workflow invocation.
The Executor.invoke() operation MUST be awaited.
A successful return marks the step successful.
A raised NervaError marks the step failed.
Layer 3 MUST NOT retry a failed invocation implicitly.
Layer 3 MUST NOT alter Policy, Registry, timeout, cancellation, or exception-normalization semantics defined by Layer 2.
R-WORKFLOW-008 — No Inter-Step Data Binding

In this revision, Layer 3 MUST NOT perform implicit or explicit transfer of one step's output into another step's arguments.

The Orchestrator MUST NOT use a step output to:

insert or replace another step's argument;
mutate another step's stored or invocation-time arguments;
create an undeclared dependency;
resolve a step_id.output reference;
resolve $ref, templates, interpolation expressions, paths, or equivalent binding syntax.

The dependency graph defined by depends_on controls execution readiness only.

A dependency MUST NOT imply output transfer.

If step B depends on step A, successful completion of A MAY make B ready, but B MUST still be invoked from its own pre-defined args.

This requirement does not prohibit two steps from independently receiving shared objects that were already present in their caller-supplied arguments before workflow execution began.

Step outputs MAY be collected only for the successful WorkflowResult defined by R-WORKFLOW-011.

Inter-step data binding requires a future Explicit Semantic Revision.

R-WORKFLOW-009 — Fail-Fast Semantics

Layer 3 SHALL use a fail-fast workflow failure model.

If a started step fails because its Executor.invoke() call raises a NervaError:

the workflow MUST be considered failed;
no step whose execution has not already started MAY subsequently be started;
every other currently running workflow step MUST receive a cancellation request as defined by R-WORKFLOW-010;
the NervaError from the first step failure observed by the Orchestrator MUST be propagated as the workflow failure;
Layer 3 MUST NOT wrap, replace, or semantically transform that propagated NervaError;
no WorkflowResult MAY be returned.

When multiple concurrently running steps fail before fail-fast processing settles, the failure first observed by the Orchestrator determines the error propagated to the workflow caller.

Layer 3 does not define a deterministic winner when multiple failures become observable concurrently.

Errors from other concurrently running steps that settle after the selected workflow failure MUST NOT replace the selected propagated error.

R-WORKFLOW-010 — Cancellation

Layer 3 SHALL support cancellation of an active workflow invocation.

Workflow cancellation MAY originate from:

cancellation of the coroutine executing Orchestrator.invoke(); or
fail-fast processing defined by R-WORKFLOW-009.

Once workflow cancellation begins:

no additional workflow step MAY be started;
every currently running step task MUST receive a cancellation request;
cancellation MUST propagate through the active Executor.invoke() operation;
the Orchestrator MUST retain ownership of every task it created until that task reaches a terminal state;
exceptions produced while cancelled sibling tasks settle MUST be retrieved and MUST NOT replace the workflow's already-selected fail-fast error;
Layer 3 MUST NOT treat normal successful completion of a sibling after cancellation was requested as recovery of an already-failed workflow.

When cancellation originates from cancellation of the workflow invocation itself, the workflow invocation MUST fail with:

CANCELLED

represented by a NervaError from the existing canonical error catalog.

When cancellation of sibling steps is initiated because another step failed, the original first-observed step failure defined by R-WORKFLOW-009 MUST remain the workflow error.

Layer 3 MUST NOT introduce an independent workflow retry or recovery mechanism as part of cancellation.

R-WORKFLOW-011 — Workflow Result

If and only if every WorkflowStep completes successfully, Orchestrator.invoke() SHALL return a WorkflowResult.

The canonical stored logical model is:

@dataclass(frozen=True)
class WorkflowResult:
    workflow_id: str
    outputs: Mapping[str, Any]
    duration_ms: int

The following requirements apply:

workflow_id MUST be a canonical UUID string generated once for the workflow invocation.
outputs MUST contain exactly one entry for every step in the Workflow.
Each output key MUST equal the corresponding WorkflowStep.id.
Each output value MUST equal the opaque ExecutionResult.output returned by that step's Layer 2 invocation.
Output entry ordering is undefined.
The top-level outputs mapping MUST be immutable.
Layer 3 is NOT required to deep-freeze step output values.
WorkflowResult MUST NOT contain per-step execution_id, duration_ms, or Layer 2 metadata.
duration_ms MUST be a non-negative integer measured using a monotonic clock.
Measurement MUST begin when execution of the validated workflow invocation begins and end immediately before the successful WorkflowResult is returned.
The WorkflowResult object MUST be immutable after construction.
A failed or cancelled workflow MUST NOT return a partial WorkflowResult.
R-WORKFLOW-012 — Orchestrator, State, and Transport Boundaries

The canonical Layer 3 execution surface is logically equivalent to:

class Orchestrator:
    def __init__(self, *, executor: Executor) -> None:
        ...

    async def invoke(
        self,
        workflow: Workflow,
        context: ExecContext,
    ) -> WorkflowResult:
        ...

The following requirements apply:

workflow MUST be a successfully constructed Workflow.
context MUST be an ExecContext.
Invalid invocation input MUST raise INVALID_INPUT.
The Orchestrator MUST delegate capability execution exclusively through its supplied Layer 2 Executor.
Layer 3 MUST NOT directly perform Registry lookup or Policy enforcement.
Layer 3 SHALL remain stateless across workflow invocations.
The Orchestrator MUST NOT persist workflow definitions, execution state, or results beyond a workflow invocation.
The Orchestrator MUST NOT maintain workflow execution state across separate invoke() calls.
The Orchestrator MUST NOT introduce persistence or checkpointing.
The Orchestrator MUST NOT depend on HTTP, gRPC, WebSocket, RPC, message queues, or another transport protocol.
The Orchestrator MUST NOT define a wire format for Workflow, WorkflowStep, or WorkflowResult.
The Orchestrator MUST NOT mutate the supplied ExecContext.
The Orchestrator MUST NOT create a replacement ExecContext for individual workflow steps.
Layer 3 MUST NOT introduce new canonical error codes.

Transport neutrality and state-boundary requirements are part of Layer 3 conformance.

Violation of these requirements constitutes a Layer 3 conformance failure.

## 19. Layer 4 - Observability

**Status:** SPEC FROZEN / IMPLEMENTATION PENDING
**Revision Type:** EXPLICIT SEMANTIC REVISION
**Depends On:** Layer 0 (ExecContext, NervaError), Layer 2 (Capability Invocation & Execution), Layer 3 (Workflow Orchestration)

Layer 4 defines transport-neutral observability for capability and workflow execution.

Layer 4 MUST NOT alter the canonical execution semantics of Layers 0 through 3.

Observability data MUST be derived from already-observable execution state and MUST NOT become an input to execution, policy evaluation, registry lookup, scheduling, cancellation, retry, or error selection.

Layer 4 MUST remain optional with respect to execution correctness: failure of an observability sink MUST NOT change a successful or failed execution result.

##### R-OBS-001 - Observation Model

Layer 4 SHALL define an immutable observation record representing one observable execution event.

An observation record MUST contain:

- `event_id`: a canonical UUID string generated once for the observation;
- `event_type`: a stable Layer 4 event identifier;
- `timestamp_unix_ms`: a non-negative Unix timestamp in milliseconds representing when the observation was created;
- `request_id`: the originating `ExecContext.request_id`;
- `workflow_id`: when the observation belongs to a Layer 3 workflow invocation;
- `step_id`: when the observation belongs to a workflow step;
- `capability_id`: when the observation belongs to a Layer 2 capability invocation;
- `attributes`: an immutable mapping of additional observation metadata.

Fields not applicable to an event MUST be absent or `None` according to the canonical Layer 4 data model.

##### R-OBS-002 - Event Identifier Semantics

`event_id` MUST uniquely identify one observation record.

An implementation MUST NOT reuse an `event_id` for another observation.

Event identifiers MUST NOT encode transport-specific routing information, process identifiers, filesystem paths, hostnames, or network addresses.

##### R-OBS-003 - Event Type Catalog

Layer 4 SHALL define a closed canonical event-type catalog for this specification revision.

The canonical catalog MUST include events for:

- capability invocation started;
- capability invocation completed;
- capability invocation failed;
- workflow invocation started;
- workflow step started;
- workflow step completed;
- workflow step failed;
- workflow cancellation requested;
- workflow invocation completed;
- workflow invocation failed.

An implementation MUST NOT introduce additional canonical Layer 4 event types without an Explicit Semantic Revision.

Implementation-specific non-canonical diagnostic events MAY exist outside the canonical Layer 4 conformance surface.

##### R-OBS-004 - Correlation

Observations MUST preserve available canonical correlation identifiers from the execution being observed.

Layer 4 MUST NOT generate replacement `request_id`, `workflow_id`, `step_id`, `session_id`, or `trace_id` values when those identifiers already exist.

Layer 4 MUST NOT mutate the supplied `ExecContext` for correlation purposes.

##### R-OBS-005 - Causal Ordering

For observations emitted by one logical execution path, an implementation MUST preserve program-order causality.

A completion or failure observation MUST NOT be emitted before the corresponding start observation.

Layer 4 does not define a total ordering across independently executing workflow steps.

Concurrent observations MAY be delivered in any order consistent with the causal constraints above.

##### R-OBS-006 - Result and Error Representation

Successful observations MAY include non-sensitive summary metadata about the corresponding execution result.

Layer 4 MUST NOT require deep serialization of opaque Layer 2 output values.

Failure observations MUST reference the canonical `NervaError` produced by the underlying layer or a transport-neutral representation of that error.

Layer 4 MUST NOT wrap, replace, reclassify, or semantically transform a canonical `NervaError`.

##### R-OBS-007 - Sensitive Data Boundaries

Observation records MUST NOT contain credentials, secrets, authentication tokens, or raw secret-bearing capability inputs.

Implementations MUST provide a deterministic redaction boundary before observations are delivered to an external sink.

Redaction MUST NOT mutate the underlying `ExecContext`, capability input, execution result, `WorkflowResult`, or `NervaError`.

##### R-OBS-008 - Observer Interface

The canonical Layer 4 observer surface is logically equivalent to:

```python
class Observer:
    async def emit(
        self,
        observation: Observation,
    ) -> None:
        ...
```

An observer MUST receive an immutable observation record.

The execution layers MUST NOT depend on observer return values.

An observer MUST NOT be given authority to mutate execution state.

##### R-OBS-009 - Failure Isolation

Failure of an observer or observability sink MUST NOT change the canonical result of the execution being observed.

Observer exceptions MUST NOT replace a successful `ExecutionResult`, `WorkflowResult`, or canonical `NervaError`.

An implementation MAY record observer failures through a non-canonical local diagnostic mechanism.

Layer 4 MUST NOT introduce a new canonical execution error code solely for observability delivery failure.

##### R-OBS-010 - Non-Blocking Execution Boundary

Layer 4 MUST NOT require durable delivery, distributed consensus, or remote acknowledgement before canonical execution may complete.

An implementation MAY buffer, batch, or asynchronously deliver observations.

Any buffering mechanism MUST remain outside the canonical execution state of Layer 3.

Loss of buffered observations after canonical execution completion MUST NOT retroactively alter that execution result.

##### R-OBS-011 - Transport Neutrality

Layer 4 MUST NOT define a required wire format or transport binding for observations.

The canonical Layer 4 model MUST NOT depend on HTTP, gRPC, WebSocket, RPC, message queues, OpenTelemetry exporters, files, databases, or another transport mechanism.

Adapters MAY map canonical observations to external observability systems provided that the mapping does not alter Layer 4 semantics.

##### R-OBS-012 - State and Execution Boundaries

Layer 4 MUST remain observational.

Layer 4 MUST NOT:

- perform Registry lookup or Policy enforcement;
- invoke capabilities;
- start, cancel, retry, or reschedule workflow steps;
- mutate `ExecContext`;
- mutate `ExecutionResult`, `WorkflowResult`, or `NervaError`;
- persist canonical workflow execution state;
- introduce checkpointing or recovery semantics;
- introduce new canonical execution error codes.

Violation of these requirements constitutes a Layer 4 conformance failure.

# End of Nerva Specification v0.1
