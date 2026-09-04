# INVARIUS Phase 1 Requirements Register

**Version:** 1.0.0
**Status:** ACTIVE
**Phase:** Phase 1

---

## Requirement Status

Each requirement has one of these statuses:

- `PLANNED`
- `IN_PROGRESS`
- `IMPLEMENTED`
- `VERIFIED`
- `BLOCKED`
- `DEFERRED`

---

## Requirement Classification

Each requirement is classified as:

- `BUILD_NOW` — implemented during Phase 1
- `FOUNDATION_NOW` — foundation/contract implemented during Phase 1
- `FUTURE` — explicitly handed off to a later phase

---

## Requirement Record

Each requirement must contain:

- ID
- Requirement
- Classification
- Status
- Rationale
- Dependencies
- Inputs
- Outputs
- Interfaces
- Security considerations
- Validation criteria
- Evidence
- ADR reference
- Future-phase handoff

---

# Phase 1 Requirements

## INV-P1-0001 — Engineering Contract

**Requirement:**
INVARIUS Phase 1 shall operate according to the Engineering Contract.

**Classification:** `BUILD_NOW`

**Status:** `IMPLEMENTED`

**Validation:**
- Engineering Contract exists.
- Contract is versioned.
- Architecture decisions can reference it.
- Changes are subject to change control.

---

## INV-P1-0002 — Canonical Software Representation

**Requirement:**
INVARIUS shall establish a Canonical Software Representation (CSR) capable
of representing the structure, dependencies, configuration, tests,
relationships, provenance, confidence, and temporal information of a
software project.

**Classification:** `BUILD_NOW`

**Status:** `PLANNED`

**Validation:**
- CSR schema exists.
- CSR has stable identifiers.
- CSR is versioned.
- CSR can be serialized.
- CSR provenance is represented.
- CSR integrity can be verified.

---

## INV-P1-0003 — Evidence-Based Knowledge

**Requirement:**
INVARIUS shall distinguish observed facts from inference, hypothesis,
unknown, conflict, and stale information.

**Classification:** `BUILD_NOW`

**Status:** `PLANNED`

**Validation:**
- Knowledge types are represented.
- Evidence can be attached to knowledge.
- Unknown information cannot silently become fact.

---

## INV-P1-0004 — Project Discovery

**Requirement:**
INVARIUS shall discover the structure and relevant artifacts of a target
software project before analysis.

**Classification:** `BUILD_NOW`

**Status:** `PLANNED`

**Validation:**
- Project root can be identified.
- Files can be enumerated.
- Relevant project metadata can be identified.
- Unsupported/unreadable artifacts are explicitly reported.

---

## INV-P1-0005 — Universal Source Ingestion

**Requirement:**
INVARIUS shall provide a controlled ingestion layer for source and project
artifacts.

**Classification:** `BUILD_NOW`

**Status:** `PLANNED`

**Validation:**
- Inputs are validated.
- Files are identified.
- Content integrity can be checked.
- Unsupported content produces explicit results.
- Malicious/untrusted input is handled safely.

---

## INV-P1-0006 — Language Understanding

**Requirement:**
INVARIUS shall provide an extensible language-adapter architecture.

Initial language targets:

- Python
- JavaScript
- TypeScript
- Java
- Go
- Rust
- C
- C++

**Classification:** `BUILD_NOW`

**Status:** `PLANNED`

---

## INV-P1-0007 — Security by Construction

**Requirement:**
Security controls shall be integrated into Phase 1 architecture rather than
added after implementation.

**Classification:** `BUILD_NOW`

**Status:** `PLANNED`

**Validation:**
- Trust boundaries are defined.
- Authorization boundaries exist.
- Untrusted input is identified.
- Sensitive data handling is defined.
- Security events are auditable.

---

## INV-P1-0008 — No Silent Failure

**Requirement:**
Important INVARIUS failures shall be observable and diagnosable.

**Classification:** `BUILD_NOW`

**Status:** `PLANNED`

**Validation:**
- Structured error model exists.
- Failures are logged appropriately.
- Correlation information exists where applicable.
- Failure state is represented explicitly.

---

## INV-P1-0009 — Observability

**Requirement:**
INVARIUS shall provide internal observability capabilities.

**Classification:** `FOUNDATION_NOW`

**Status:** `PLANNED`

**Validation:**
- Structured logging exists.
- Health checks exist.
- Metrics/tracing architecture exists.
- Internal diagnostics are available.

---

## INV-P1-0010 — Explicit Versioning

**Requirement:**
Important schemas, contracts, representations, and persisted structures shall
be versioned.

**Classification:** `BUILD_NOW`

**Status:** `PLANNED`

---

## INV-P1-0011 — Provenance

**Requirement:**
Important knowledge and representations shall retain information describing
their origin and supporting evidence.

**Classification:** `BUILD_NOW`

**Status:** `PLANNED`

---

## INV-P1-0012 — Requirement Traceability

**Requirement:**
Significant Phase 1 requirements shall be traceable to implementation,
testing, documentation, architecture decisions, and verification evidence.

**Classification:** `BUILD_NOW`

**Status:** `PLANNED`

---

# Requirement Change Control

New requirements must not automatically expand Phase 1.

A proposed requirement must first be classified:

1. Already covered.
2. Required for Phase 1 correctness/security.
3. Future Phase.

Architecture-affecting changes require an ADR where appropriate.

---

# Phase 1 Verification

Phase 1 cannot be declared complete until every applicable requirement has
reached the required verification state.

---

**Status: ACTIVE**
