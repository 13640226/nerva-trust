## 18. Layer 3 — Workflow Orchestration

**Status:** SPEC FROZEN / IMPLEMENTATION PENDING
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

End of Nerva Specification v0.1

Status: RECONSTRUCTED WITH EXPLICIT REVISIONS
