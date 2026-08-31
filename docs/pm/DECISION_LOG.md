# Decision Log

| Field | Value |
|---|---|
| Purpose | Preserve material product and architecture decisions, alternatives, and tradeoffs. |
| Owner | Agent Governance product owner |
| Update cadence | Whenever a material decision is proposed, accepted, superseded, or reversed |
| Last updated | 2026-08-04 |

## Status Definitions

- **Accepted:** Current direction.
- **Proposed:** Decision is needed before implementation.
- **Superseded:** Retained for history but no longer current.

## Decisions

### D-001 — Keep the planner as proposer and the backend as enforcer

- **Date recorded:** 2026-07-24
- **Status:** Accepted; implemented in `0.2.0`
- **Decision:** The planner may propose a tool and arguments but cannot execute directly. The backend owns registry lookup, validation, policy, approval, execution, and audit.
- **Options considered:** Planner executes tools directly; framework middleware enforces controls; application backend enforces controls.
- **Rationale:** An explicit backend boundary is easy to inspect, test, and explain to enterprise and public-sector reviewers.
- **Tradeoffs:** More orchestration code and a narrower demo, in exchange for deterministic control points.

### D-002 — Use three explicit policy outcomes

- **Date recorded:** 2026-07-24
- **Status:** Accepted; implemented in `0.2.0`
- **Decision:** Policy returns `allow`, `require_approval`, or `deny`, with matched rules, reason codes, explanation, and a decision ID.
- **Options considered:** Boolean approval flag; allow/deny only; structured three-outcome decision.
- **Rationale:** A separate pause state models proportional human oversight without treating every controlled action as prohibited.
- **Tradeoffs:** Requires approval lifecycle management and more terminal-state tests.

### D-003 — Bind approvals to the evaluated action and tool version

- **Date recorded:** 2026-07-24
- **Status:** Accepted; implemented in `0.2.0`
- **Decision:** Approval records preserve agent ID, policy decision ID, tool name, version, and validated arguments.
- **Options considered:** Approve a run ID only; approve a tool name; approve the full evaluated action.
- **Rationale:** A human decision must not silently authorize changed code or a different proposed action.
- **Tradeoffs:** Tool upgrades invalidate pending approvals and require resubmission.

### D-004 — Start with static registries and local JSONL evidence

- **Date recorded:** 2026-07-24
- **Status:** Accepted for local MVP
- **Decision:** Keep agent/tool metadata static, approvals in memory, and audit events in a local JSONL file.
- **Options considered:** Database-backed control plane; external policy service; local in-process implementation.
- **Rationale:** The smallest implementation exposes the governance seams without infrastructure obscuring the product hypothesis.
- **Tradeoffs:** No restart safety, multi-worker consistency, protected administration, or audit integrity. This decision blocks production use.

### D-005 — Run mock retrieval and planning concurrently

- **Date recorded:** 2026-07-24
- **Status:** Accepted; implemented in `0.2.0`
- **Decision:** Use `asyncio.gather()` for independent retrieval and planning operations.
- **Options considered:** Sequential calls; concurrent calls; workflow engine.
- **Rationale:** It demonstrates an I/O-appropriate runtime pattern while keeping orchestration readable.
- **Tradeoffs:** Future real planning may depend on retrieved context, in which case the dependency graph must change rather than preserving concurrency artificially.

### D-006 — Prioritize evaluation before adding model or tool complexity

- **Date:** 2026-07-24
- **Status:** Accepted; implemented in `0.3.0`
- **Decision:** Build a versioned policy scenario matrix before introducing path-aware rules, a real model, or external tools.
- **Options considered:** Add RAG first; add monitoring UI first; establish the control evaluation contract first.
- **Rationale:** The next change should make governance claims measurable and protect the existing behavior from regression.
- **Tradeoffs:** Less visible feature growth in the immediate next increment, but stronger evidence and safer iteration.

### D-007 — Represent partial execution history as ordered normalized action records

- **Date:** 2026-07-29
- **Status:** Accepted; implemented in `0.3.0`
- **Decision:** Use a backend-managed typed ordered list of action records, referenced by `path_id`.
- **Options considered:** Ordered action records; aggregate counters/flags only; event-sourced state machine; external workflow engine.
- **Implementation:** Each record contains action/run IDs, tool/version/risk, request risk, policy decision/outcome, approval ID/status, execution outcome, and timestamps. Callers may continue but cannot submit or rewrite path history.
- **Rationale:** This is the smallest auditable model that preserves sequence and can later be derived from structured events.
- **Tradeoffs:** The policy interface and audit model are more complex. The in-memory store has no concurrency, retention, restart, or integrity guarantees.

### D-008 — Escalate writes after adverse path outcomes while preserving reads

- **Date:** 2026-07-29
- **Status:** Accepted; implemented in policy `2.1`
- **Decision:** A validation failure, denial, rejection, or execution failure on a path causes the next non-read-only action to require human approval. Trusted in-scope reads remain eligible for automatic execution.
- **Options considered:** Deny all later actions; require approval for every later action; escalate writes only; use an aggregate numeric risk score.
- **Rationale:** Write-only escalation limits additional side effects while preserving the operator's ability to inspect policy after a problem.
- **Tradeoffs:** One adverse event taints the path indefinitely in the current MVP. There is no reviewed recovery/clearance transition yet.
- **Evidence:** `escalate_write_after_failed_action` and `allow_read_after_failed_action` in the versioned policy suite.

### D-009 — Begin approval execution with an immutable idempotency-bound receipt

- **Date:** 2026-07-30
- **Status:** Accepted; implemented in `0.4.0`
- **Decision:** Before invoking an approved tool, atomically move the approval into `executing` and create a receipt bound to a fingerprint of the client idempotency key. A completed key replays its receipt; it never invokes the tool again.
- **Options considered:** Trust clients not to retry; mark an approval executed before the tool call; cache only the response; create a per-attempt receipt and explicit approval state machine.
- **Rationale:** A receipt makes the execution claim inspectable and gives retries a deterministic answer while preserving the exact approved agent, policy, path action, tool version, and arguments.
- **Tradeoffs:** The in-memory atomicity applies to one process only. Cross-worker guarantees require a transactional store and uniqueness constraint.
- **Evidence:** Duplicate-replay API/runtime/store tests and `duplicate_approval_replays_receipt` in fixture schema `1.1.0`.

### D-010 — Fail stale approvals and unclassified tool errors closed

- **Date:** 2026-07-30
- **Status:** Accepted; implemented in `0.4.0`
- **Decision:** Expire approvals after a configurable TTL. Permit a new-key retry only when a handler explicitly raises `RetryableToolExecutionError`; treat declared terminal errors and all unclassified exceptions as terminal.
- **Options considered:** Never expire approvals; retry every failure; infer retryability from exception text; require an explicit typed failure contract.
- **Rationale:** Authorization should not remain valid indefinitely, and uncertain failures should not authorize repeated side effects automatically.
- **Tradeoffs:** Some recoverable unclassified errors require a new approval instead of an automatic retry. Reliable timeout reconciliation remains dependent on future tool-specific contracts and durable state.
- **Evidence:** Expiry, retryable recovery, and terminal failure scenarios in the versioned suite, plus approval transition tests.

### D-011 — Authenticate approvers locally and authorize every transition

- **Date:** 2026-08-04
- **Status:** Accepted; implemented in `0.5.0`
- **Decision:** Resolve approval bearer credentials through a static local identity registry, then require active state, permitted action, tool scope, risk scope, and separation of duties for approval and rejection. Bind the resulting approver and authorization-decision IDs to records, receipts, path actions, responses, and audit events.
- **Options considered:** Continue caller-supplied actor labels; integrate an external identity provider now; use signed local tokens; use an in-process fingerprinted bearer registry.
- **Rationale:** The in-process registry closes the demonstrable authorization gap without adding infrastructure that would obscure the control flow. Stable decision reason codes make grants and denials testable.
- **Tradeoffs:** Source-known demo credentials, static lifecycle, and unverified requester identity mean this is not production authentication. The governance administrator retains broad scope but cannot bypass separation of duties.
- **Evidence:** Fixture schema `1.2.0`, API/runtime/registry tests, and [Milestone 2.7](../milestone-2.7.md).

## Decision Template

### D-XXX — Decision title

- **Date:**
- **Status:** Proposed / Accepted / Superseded
- **Decision:**
- **Options considered:**
- **Rationale:**
- **Tradeoffs:**
- **Evidence or follow-up:**
