# Retrospective Log

| Field | Value |
|---|---|
| Purpose | Capture delivery lessons and turn them into owned improvements. |
| Owner | Agent Governance product owner |
| Update cadence | At the end of each milestone or material PR |
| Last updated | 2026-08-04 |

## Milestone 2.7 Retrospective — 2026-08-04

### Outcome

AG-004 is complete. Approval and rejection now require an authenticated local approver whose active state, action, tool, risk, and separation-of-duties constraints authorize the exact transition.

### What Went Well

- Authentication, authorization, transition, and execution remain distinct and independently testable boundaries.
- Stable reason codes make self-approval and scope denials usable as product-level evaluation contracts.
- The same approver and decision IDs connect records, receipts, paths, API responses, and audit evidence.
- Credential values are absent from metadata, state models, responses, and audit records.

### What Was Confusing

- Authenticated approver identity does not make the caller-supplied requester ID trustworthy; the audit model now labels that claim unverified.
- A governance administrator needs broad scope but should not bypass separation of duties.
- Source-known demo credentials make local setup easy but must be framed as a deployment blocker, not production secrets.

### What Broke or Nearly Broke

- Tests initially embedded default bearer values; deriving headers from settings preserves environment overrides.
- Authorization had to run before expiry, replay, rejection, or execution so no state transition can use an unverified actor.
- Broad documentation claims could have implied verified requester identity; the limitation is explicit throughout the release artifacts.

### What Should Improve Next

1. Implement AG-005 transactional, restart-safe governance state.
2. Replace local identity configuration with a trusted identity provider before shared use.
3. Add audit integrity, retention, redaction, and access controls in AG-006.

### Actions

| Action | Owner | Due | Status |
|---|---|---|---|
| Define approver role/scope and separation-of-duties rules | Product, security, and governance owners | Before `0.5.0` | Done |
| Design transactional receipt and authorization-decision persistence | Backend owner | With AG-005 | Open |
| Select trusted requester/approver identity integration | Security owner | Before shared deployment | Open |
| Validate clean bootstrap on M1 | Repository owner | Before release publication | Open |

## Milestone 2.6 Retrospective — 2026-07-30

### Outcome

AG-003 is complete. Duplicate approval requests now replay one recorded result, stale approvals fail closed, and each real attempt produces an explicit success or failure receipt.

### What Went Well

- The state-machine boundary separated authorization state from tool-attempt evidence.
- Handler-call assertions proved replay semantics, not only response equality.
- The versioned fixture expanded from 9 to 13 scenarios without breaking the earlier policy/path contract.
- The same receipt identifiers now connect API responses, approval state, path outcomes, and audit evidence.

### What Was Confusing

- “Durable receipt” was too strong for an in-memory store; documentation now says immutable per-attempt receipt and reserves durability for AG-005.
- A successful replay must bypass current tool-registry version checks because it returns historical evidence rather than authorizing a new execution.
- Timeout retryability cannot be generic when an external system may have completed an operation after the local caller lost the response.

### What Broke or Nearly Broke

- Rechecking current tool metadata before replay would have blocked a valid completed receipt after registry drift.
- A raw idempotency key would have created unnecessary sensitive log/state exposure; only a fingerprint is retained.
- Treating unknown exceptions as retryable could have duplicated an uncertain external side effect, so they fail terminally.

### What Should Improve Next

1. Implement AG-004 verified approver identity and separation of duties.
2. Implement AG-005 transactional state and cross-worker uniqueness.
3. Define tool-specific timeout reconciliation before adding real side effects.
4. Establish repository baseline history.

### Actions

| Action | Owner | Due | Status |
|---|---|---|---|
| Define approver role/scope and separation-of-duties rules | Product, security, and governance owners | Before `0.5.0` | Open |
| Design transactional receipt uniqueness and restart recovery | Backend owner | With AG-005 | Open |
| Define external timeout reconciliation contract | Tool integration owner | Before first real write tool | Open |
| Establish repository baseline history | Repository owner | Before collaborative implementation | Open |

## Milestone 2.5 Retrospective — 2026-07-29

### Outcome

AG-001 and AG-002 are complete. The repo now has a nine-scenario policy evidence contract and a backend-managed ordered execution path that changes a later write decision after an adverse outcome.

### What Went Well

- The scenario fixture expresses product behavior separately from implementation tests.
- Every scenario checks decision, reason, execution, audit events, path outcomes, and trace identifiers.
- The path model preserves sequence without adding a workflow engine or accepting caller-supplied history.
- The escalation rule is proportional: writes pause after an adverse outcome while reads remain available.
- Existing Milestone 2.0 behavior stayed covered; the suite grew from 19 to 25 tests.

### What Was Confusing

- “Initial status” in sequence scenarios refers to the evaluated final step; a future fixture schema should use a clearer field name.
- An execution path is inspectable but not durable or concurrency-safe, so “backend-managed” must not be read as production-grade.
- Deterministic scenario coverage proves the reference contract, not a statistical false-positive or false-negative rate.

### What Broke or Nearly Broke

- The first path endpoint implementation attempted to validate a base Pydantic model directly as a response subclass; converting through `model_dump()` fixed it.
- The local Ruby version lacked `Array#filter_map` during an earlier documentation validator; the compatibility issue did not affect product code.
- Approval execution still lacks idempotency and durable receipts, which becomes more visible now that path state records execution outcomes.

### What Should Improve Next

1. Implement AG-003 before adding real side effects.
2. Add path revision/concurrency checks with durable state.
3. Keep policy fixtures versioned when expected behavior changes.
4. Establish repository baseline history.

### Actions

| Action | Owner | Due | Status |
|---|---|---|---|
| Define approval idempotency/receipt state machine | Backend and governance owners | Before release `0.4.0` | Done |
| Add expiry, retry, and duplicate-approval scenarios | Evaluation owner | With AG-003 | Done |
| Design path revision and concurrency control | Backend owner | With durable state work | Open |
| Establish repository baseline history | Repository owner | Before collaborative implementation | Open |

## Milestone 2.0 Retrospective — 2026-07-24

### Outcome

The project moved from a boolean approval concept to an explainable decision contract with registered agent identity, tool provenance, proportional outcomes, approval binding, and correlated audit evidence.

### What Went Well

- The control boundary is legible: proposal, validation, policy, approval, execution, and audit have distinct roles.
- `allow`, `require_approval`, and `deny` paths are demonstrated with small, understandable fixtures.
- Decision IDs, tool versions, and agent IDs make policy and audit events correlatable.
- Tests cover unregistered agents, out-of-scope tools, untrusted provenance, invalid inputs, approval execution, and version mismatch.
- The two-minute demo maps code behavior to a clear governance narrative.

### What Was Confusing

- Product milestone names and package version `0.2.0` can be mistaken for the broader portfolio roadmap stages.
- “Trusted provenance” can sound verified even though it is currently registry metadata.
- The research and future-state language can make the small local MVP appear more production-ready than it is.

### What Broke or Nearly Broke

- Running `pytest` directly failed because the command is only available in the repo virtual environment; `.venv/bin/pytest -q` is the reliable current command.
- Approval state is changed before tool execution completes, so failure and retry semantics need an explicit design before real side effects.
- The repository content is currently untracked, which makes it difficult to distinguish baseline work from later increments.

### What Should Improve Next

1. Add a versioned evaluation scenario matrix with product-level control assertions.
2. Separate “declared” from “verified” provenance in future naming and evidence.
3. Define path state, approval idempotency, expiry, and execution-failure transitions.
4. Establish an intentional baseline commit before multiple contributors or agents modify the repo.

### Actions

| Action | Owner | Due | Status |
|---|---|---|---|
| Create AG-001 evaluation harness issue from the backlog | Product owner | Next planning session | Done |
| Decide D-007 path representation | Product and backend owners | Before path-aware implementation | Done |
| Define approval failure/idempotency state diagram | Backend and governance owners | Before any real external tool | Done |
| Establish repository baseline history | Repository owner | Before collaborative implementation | Open |

## Retrospective Template

### Milestone or PR — YYYY-MM-DD

**Intended outcome**

**Actual outcome and evidence**

**What went well**

- <!-- Add an evidence-backed observation. -->

**What was confusing**

- <!-- Add a specific source of ambiguity. -->

**What broke or nearly broke**

- <!-- Add the failure, impact, and detection method. -->

**What should improve next**

- <!-- Add the improvement and expected outcome. -->

**Actions**

| Action | Owner | Due | Status |
|---|---|---|---|
|  |  |  | Open |
