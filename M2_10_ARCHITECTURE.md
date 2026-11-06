# M2.10 — Failure Handling & Recovery Boundary

**Status:** Architecture baseline
**Contract:** `M2_10_ENGINEERING_CONTRACT.md`
**Scope:** M2.10 only

## 1. Mission

Establish an explicit, auditable boundary for capturing failures, recording failure context, authorizing recovery, executing recovery attempts, and verifying recovery outcomes.

This milestone does not implement autonomous debugging or automatic source-code repair.

## 2. Architectural Principles

- A failure record is not an exception and not an operation result.
- Original failures must remain preserved.
- Failure capture, diagnostics, and persistence are separate concerns.
- Recovery is explicit, authorized, bounded, and auditable.
- Recovery never reactivates a terminal component instance or runtime.
- Recovery success requires verification, not merely action completion.
- Uncertainty must remain visible.
- Storage or diagnostic failures must not overwrite the original operational failure.
- No implicit authorization, retry, or recovery scope inference.

## 3. Proposed Module Boundaries

### `backend/app/platform/failures.py`

Owns:
- Failure categories and classification.
- Immutable failure records.
- Failure identity and timestamps.
- Context capture and validation.
- Failure relationships and serialization.

Does not own:
- Recovery execution.
- Storage backend implementation.
- Diagnostic logging implementation.
- Root-cause analysis.

### `backend/app/platform/recovery.py`

Owns:
- Recovery scope and target identity.
- Recovery attempt records.
- Recovery lifecycle and transition validation.
- Authorization state representation.
- Attempt coordination and conflict detection.
- Recovery outcome and verification status.

Does not own:
- Autonomous recovery policy.
- Component/runtime lifecycle mutation.
- Source-code repair.
- Scheduling arbitrary component code.

### Existing boundaries

- `core/errors.py`: common INVARIUS errors.
- `core/operation.py`: authoritative operation identity.
- `core/result.py`: authoritative operation outcome.
- `platform/runtime.py`: runtime lifecycle.
- `platform/component.py`: component lifecycle.
- `platform/storage.py`: `StoragePort` persistence boundary.
- `observability/diagnostics.py`: diagnostic event and emission boundary.

These modules remain authoritative for their respective responsibilities.

## 4. Failure Model

A failure record should capture, where available:

- Unique failure ID.
- Failure contract version.
- Failure category.
- Occurrence timestamp in UTC.
- Bounded error type and safe message.
- Operation ID and operation type.
- Runtime ID.
- Component ID and component instance ID.
- Correlation and parent-operation IDs.
- Source/context information.
- Related failure IDs.
- Capture status and limitations.

Failure records must not store unrestricted exception tracebacks, secrets, or arbitrary payloads by default.

Unexpected Python exceptions must be representable even when they are not `InvariusError` instances.

Failure category describes the failure; it does not determine recovery scope.

## 5. Recovery Model

Recovery scope is explicit:

- `COMPONENT_INSTANCE`
- `RUNTIME`
- `OPERATION`
- `DEPENDENCY`
- `OTHER`

Recovery target identity must be explicit and validated.

Each recovery attempt has:
- Unique attempt ID.
- Associated failure ID or recovery objective.
- Recovery scope and target.
- Request timestamp.
- Authorization information.
- Current state and transition history.
- Action/completion information.
- Verification result.
- Bounded attempt metadata.

## 6. Recovery Lifecycle

States:

`REQUESTED`, `AUTHORIZED`, `RUNNING`, `SUCCEEDED`, `FAILED`, `REJECTED`, `CANCELLED`, `UNRESOLVED`

Allowed transitions:

- `REQUESTED` → `AUTHORIZED`, `REJECTED`, `CANCELLED`
- `AUTHORIZED` → `RUNNING`, `CANCELLED`
- `RUNNING` → `SUCCEEDED`, `FAILED`, `CANCELLED`, `UNRESOLVED`

Terminal states:

`SUCCEEDED`, `FAILED`, `REJECTED`, `CANCELLED`, `UNRESOLVED`

Terminal attempts cannot be reopened. Every retry creates a new attempt ID.

`SUCCEEDED` requires:
1. The recovery action completed.
2. Verification confirms the intended target condition.

Action completion alone is insufficient.

## 7. Authorization and Execution Boundary

Recovery authorization is represented explicitly.

No recovery attempt may transition to `RUNNING` without authorization.

M2.10 establishes the authorization boundary; it does not implement an autonomous policy engine or grant implicit permissions.

Recovery actions must be bounded and represented through a controlled interface. Arbitrary code execution is outside scope.

## 8. Recovery Scope and Lifecycle Safety

- Failed component instances remain terminal.
- Component recovery, when supported, creates a new instance with a new instance ID.
- Failed runtimes remain terminal.
- Runtime recovery creates a new runtime lifetime with a new runtime ID.
- Old instances are not reused as active instances under the new runtime.
- Historical identities and failure records remain preserved.

Recovery must not directly bypass existing runtime or component lifecycle invariants.

## 9. Concurrency and Conflict Handling

Recovery attempts targeting the same recovery scope and target identity must be coordinated.

- Conflicting attempts cannot run concurrently unless explicitly permitted.
- Coordination must use deterministic synchronization.
- Conflict detection must not depend solely on timing.
- Rejected or blocked attempts remain observable.
- Coordination failure cannot be interpreted as successful recovery.
- Waiting must be bounded to avoid deadlocks or indefinite blocking.

## 10. Diagnostics and Persistence

Failure capture, diagnostic emission, and durable persistence are distinct operations.

- Diagnostic events use the existing observability contract.
- Diagnostic emission failure must not replace the original failure.
- Failure persistence uses `StoragePort`.
- Persistence success is confirmed only after the storage operation returns successfully.
- In-memory records and emitted logs are not proof of durable persistence.
- Storage failure is recorded as a related secondary failure when possible.
- Original failure identity and information must remain intact.
- Persistence retries are bounded.
- Durable history cannot be guaranteed while the storage backend is unavailable.

Failure and recovery domain logic must not be added to the SQLite adapter.

## 11. Testing Strategy

Dedicated tests should cover:

- Failure record validation and immutability.
- Failure identity and timestamp normalization.
- Safe exception capture.
- Recovery lifecycle transitions.
- Invalid transitions and terminal-state enforcement.
- Authorization requirements.
- Recovery verification requirements.
- Explicit recovery scope.
- New identity requirements for component/runtime recovery.
- Retry identity and attempt limits.
- Recovery conflict coordination.
- Diagnostic emission failure.
- Storage persistence failure.
- Preservation of original failures.
- Serialization and compatibility behavior.

## 12. Implementation Order

1. Implement failure types and records.
2. Add dedicated failure tests.
3. Implement recovery types and state machine.
4. Add recovery lifecycle tests.
5. Implement authorization and verification boundaries.
6. Implement conflict coordination.
7. Integrate diagnostics and `StoragePort`.
8. Add adversarial and failure-path tests.
9. Run targeted tests and static checks.
10. Run full regression and review the diff.

## 13. Explicit Exclusions

M2.10 does not implement:

- Autonomous root-cause analysis.
- Automatic source-code repair.
- Predictive failure prevention.
- Agentic self-healing.
- eBPF or runtime instrumentation expansion.
- Digital twins.
- New storage backend implementations.
- New general-purpose scheduling systems.

These remain outside the approved M2.10 contract.
