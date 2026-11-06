

# M2.10 — Failure Handling & Recovery Boundary



**Project:** INVARIUS

**Phase:** Phase 1 — Software Understanding Foundation

**Milestone:** M2.10

**Status:** Approved — Scope Locked



\---



## 1. Mission



Establish a reliable, observable, bounded and verifiable failure-handling and recovery boundary across the INVARIUS platform.



The boundary must preserve failure evidence, maintain lifecycle and identity integrity, coordinate explicitly authorized recovery attempts, and distinguish attempted recovery from verified recovery.



It must integrate with the existing M2.1–M2.9 foundations without duplicating their responsibilities.



## 2. Objectives



1\. Represent platform failures consistently.

2\. Preserve original failure context and provenance.

3\. Distinguish operational failure from diagnostic failure.

4\. Track recovery attempts independently of original failures.

5\. Coordinate bounded and explicitly authorized recovery.

6\. Verify recovery outcomes using observable evidence.

7\. Preserve runtime, component, operation and correlation identities.

8\. Handle secondary failures without concealing original failures.

9\. Maintain deterministic and testable failure-handling behaviour.



## 3. Scope



M2.10 covers:



\- Failure representation.

\- Failure classification boundaries.

\- Failure context and provenance.

\- Failure correlation.

\- Recovery attempt representation.

\- Recovery authorization boundaries.

\- Recovery coordination.

\- Recovery outcome representation.

\- Recovery verification.

\- Secondary failure handling.

\- Integration with existing platform foundations.



## 4. Failure Categories



The design must distinguish:



\- Runtime failure.

\- Component instance failure.

\- Operation execution failure.

\- Communication failure.

\- Storage failure.

\- Configuration failure.

\- Dependency availability failure.

\- Recovery failure.

\- Diagnostic and reporting failure.



Classification must not imply root-cause certainty.



## 5. Failure Record Requirements



A failure record must support:



\- Stable failure identity.

\- Failure category.

\- Detection timestamp.

\- Source and originating boundary.

\- Runtime identity where applicable.

\- Component and instance identity where applicable.

\- Operation and correlation identity where applicable.

\- Error code.

\- Safe descriptive information.

\- Evidence references and provenance.

\- Explicit classification confidence or unresolved status.

\- Related failure references where established.



Records must be immutable after creation unless a formally justified versioning mechanism is designed.



## 6. Recovery Requirements



A recovery attempt must:



\- Have its own stable identity.

\- Reference the original failure.

\- Record its authorization context.

\- Record its start and completion times.

\- Identify the recovery action.

\- Track attempt status.

\- Preserve its own failure information.

\- Have explicit attempt and resource bounds.

\- Avoid unbounded retry loops.



Recovery must never be represented as successful merely because an action was initiated or completed.



## 7. Identity and Lifecycle Invariants



1\. FAILED runtime lifetimes remain terminal.

2\. FAILED component instances remain terminal.

3\. Recovery of a failed runtime creates a new runtime lifetime.

4\. Recovery of a failed component instance creates a new instance identity.

5\. Historical failure records remain associated with the original identities.

6\. A new instance must not inherit the identity of a failed instance.

7\. Operation completion must not be interpreted as operation success.

8\. Component failure must not automatically imply runtime failure.

9\. Operation failure must not automatically imply component failure.



## 8. Diagnostic Failure Handling



Diagnostic serialization, logging and reporting may fail independently.



The system must:



\- Preserve the original operational failure.

\- Preserve secondary reporting failures separately when possible.

\- Avoid silently replacing the original exception.

\- Avoid claiming that an event was persisted when only logging was attempted.

\- Avoid exposing secrets or sensitive payloads in failure records.



## 9. Recovery Verification



Recovery verification must establish whether the intended operating condition was restored.



Possible outcomes:



\- VERIFIED.

\- FAILED.

\- UNRESOLVED.



Verification must identify the evidence and conditions supporting its outcome.



No unsupported recovery-success claims are permitted.



## 10. Integration Boundaries



M2.10 must integrate with:



\- M2.1 Runtime and Lifecycle.

\- M2.2 Component Model.

\- M2.3 Component Registry.

\- M2.4 Capability and Health.

\- M2.5 Execution and Operation Context.

\- M2.6 Internal Communication.

\- M2.7 Persistence and Storage.

\- M2.8 Configuration Integration.

\- M2.9 Observability.



Existing ownership of lifecycle, identity, execution and diagnostic responsibilities must be preserved.



## 11. Security and Privacy



\- Failure records must not expose secrets.

\- Recovery actions must be explicitly authorized.

\- Recovery execution must respect resource and permission boundaries.

\- Failure and recovery histories must remain auditable.

\- Untrusted error messages must not become executable instructions.

\- Recovery must not bypass existing security controls.



## 12. Explicit Exclusions



M2.10 does not implement:



\- AI root-cause analysis.

\- Autonomous debugging.

\- Automatic source-code repair.

\- Predictive failure intelligence.

\- Agentic self-healing.

\- Unbounded automatic restarts.

\- Automatic resurrection of terminal lifecycle objects.



## 13. Required Verification Scenarios



The test design must cover:



1\. Operation failure while runtime remains operational.

2\. Component instance failure.

3\. Runtime failure.

4\. Dependency unavailability.

5\. Storage failure.

6\. Communication failure.

7\. Diagnostic serialization failure.

8\. Logging-handler failure.

9\. Recovery action failure.

10\. Recovery verification failure.

11\. Concurrent recovery attempts.

12\. Preservation of original and secondary failures.

13\. New identity creation during recovery.

14\. Recovery authorization rejection.

15\. Bounded retry behaviour.



## 14. Acceptance Criteria



M2.10 is complete only when:



\- Failure records preserve required context and identity.

\- Recovery attempts are independently represented.

\- Recovery actions respect authorization and bounds.

\- Original failures survive secondary failures.

\- Terminal lifecycle invariants remain intact.

\- Recovery outcomes require verification.

\- Integration tests demonstrate correct cross-module behaviour.

\- Dedicated tests, static checks and full regression pass.

\- Security and adversarial review is complete.

\- Documentation accurately reflects implemented behaviour.



## 15. Definition of Done



The milestone must have:



\- Approved engineering contract.

\- Approved architecture and module boundaries.

\- Implemented models and interfaces.

\- Dedicated unit and integration tests.

\- Security and adversarial review.

\- Passing quality gates.

\- Reviewed Git diff.

\- Committed and pushed implementation.

\- Clean working tree.




## 16. Recovery Identity and Runtime Scope

### 16.1 Component Instance Recovery

When a component instance fails while its owning runtime remains operational:

- The failed component instance remains terminal.
- Recovery may create a new component instance under the existing runtime.
- The new instance must have a distinct instance ID.
- The new instance must reference the same logical component ID unless an explicitly approved replacement changes the component definition.
- Recovery must validate runtime state, dependency availability, registry consistency, and applicable authorization before creating or activating the new instance.
- The failed instance history must remain preserved.

### 16.2 Runtime Recovery

When a runtime fails:

- The failed runtime remains terminal.
- Recovery must create a new runtime lifetime with a new runtime ID.
- Component instances owned by the failed runtime must not be reused as active instances.
- New component instances must reference the new runtime ID.
- Historical records must preserve the identities of the failed runtime and its component instances.

### 16.3 Recovery Scope

Recovery scope must be explicitly recorded as one of:

- COMPONENT_INSTANCE
- RUNTIME
- OPERATION
- DEPENDENCY
- OTHER

The recovery scope must not be inferred solely from the failure category.


## 17. Recovery Attempt Lifecycle

### 17.1 Recovery States

Each recovery attempt must use the following lifecycle states:

- REQUESTED
- AUTHORIZED
- RUNNING
- SUCCEEDED
- FAILED
- REJECTED
- CANCELLED
- UNRESOLVED

### 17.2 Allowed Transitions

The recovery lifecycle must follow these transitions:

- REQUESTED -> AUTHORIZED
- REQUESTED -> REJECTED
- REQUESTED -> CANCELLED
- AUTHORIZED -> RUNNING
- AUTHORIZED -> CANCELLED
- RUNNING -> SUCCEEDED
- RUNNING -> FAILED
- RUNNING -> CANCELLED
- RUNNING -> UNRESOLVED

SUCCEEDED, FAILED, REJECTED, CANCELLED and UNRESOLVED are terminal recovery-attempt states.

A terminal recovery attempt must never be reopened or modified into a different state. A new attempt must receive a new recovery-attempt ID.

### 17.3 State Semantics

- REQUESTED means recovery has been requested but not authorized.
- AUTHORIZED means the request passed authorization but has not started execution.
- RUNNING means the recovery action is actively executing.
- SUCCEEDED means the action completed and recovery verification confirmed the target condition.
- FAILED means the action or required verification definitively failed.
- REJECTED means authorization or policy denied the request.
- CANCELLED means the attempt was explicitly cancelled.
- UNRESOLVED means available evidence cannot establish a definitive outcome.

Action completion alone must not transition an attempt to SUCCEEDED.

### 17.4 Retry Semantics

A retry is a new recovery attempt linked to the same original failure or recovery objective.

- Each attempt has a unique recovery-attempt ID.
- Retry limits must be explicit.
- Retries must not bypass authorization.
- Unsafe or non-idempotent actions must not be retried automatically without explicit policy approval.
- Retry exhaustion must produce a visible outcome rather than an infinite loop.


## 18. Concurrency and Failure Persistence

### 18.1 Concurrent Recovery Coordination

- Recovery coordination must detect conflicting attempts targeting the same recovery scope and target identity.
- Conflicting concurrent attempts must not execute independently unless explicitly permitted by policy.
- Recovery coordination must use deterministic synchronization and must not depend solely on timing.
- A rejected or blocked concurrent request must remain observable.
- Coordination failure must not be interpreted as successful recovery.
- Recovery coordination must not introduce unbounded waiting or deadlock.

### 18.2 Failure Persistence Boundary

Failure capture, diagnostic emission, and durable persistence are distinct outcomes.

- A failure record created in memory must not be described as durably persisted.
- Successful logging must not be treated as proof of storage persistence.
- Persistence success must be reported only when the storage boundary confirms success.
- Storage failure must not silently erase or replace the original operational failure.
- A persistence failure must be represented as a related secondary failure when possible.
- M2.10 must not claim guaranteed durable failure history when the storage backend is unavailable.
- Persistence retry behaviour must be bounded and must not introduce an unbounded retry loop.
