# Prioritized Backlog

| Field | Value |
|---|---|
| Purpose | Maintain an ordered set of outcome-focused work with testable acceptance criteria. |
| Owner | Agent Governance product owner |
| Update cadence | Weekly planning and after task completion |
| Last updated | 2026-08-04 |

## Prioritization Method

- **P0:** Required to make the next governance claim credible.
- **P1:** Required before adding real integrations or a hosted demo.
- **P2:** Improves portfolio communication or future scale.
- Effort is a relative estimate: **S** (focused task), **M** (multi-file increment), **L** (architectural milestone).

## Backlog

| ID | Priority | Status | Feature | User value | Effort | Delivery risk | Acceptance criteria |
|---|---|---|---|---|---|---|---|
| AG-001 | P0 | Done | Policy evaluation harness | Gives product, risk, and engineering reviewers repeatable evidence that controls behave as specified | M | Medium | Versioned fixtures cover allow, approval, deny, invalid input, unknown agent, untrusted tool, and version mismatch; each asserts outcome, reason codes, execution invariant, and audit events; command is documented |
| AG-002 | P0 | Done | Minimal path-aware policy context | Prevents governance from treating a proposed action independently of risky prior steps | M | High | Runtime passes an ordered, typed partial path to policy; a prior adverse action escalates a later write; read-only investigation remains available; decision/audit records identify the path; tests remain green |
| AG-003 | P0 | Done | Approval idempotency, expiry, and failure semantics | Makes human approval reliable under retries, delays, and tool failures | M | High | Duplicate approve requests execute once and replay a recorded receipt; expired approvals fail closed; failures have explicit retryable/terminal states; transition, API, runtime, and versioned scenario tests pass |
| AG-004 | P1 | Done | Approver identity and authorization | Shows who approved an action and whether they had authority | L | High | Approval endpoints require an authenticated actor; actor role/action/tool/risk scope is checked; unauthorized approval is denied and audited; tests cover separation of duties |
| AG-005 | P1 | Next | Durable governance state | Preserves approvals, paths, and policy references across process restarts | L | High | Identity, policy version, path, approval state, and execution receipt are transactional and restart-safe; migration and recovery tests pass |
| AG-006 | P1 | Planned | Audit integrity and data controls | Produces evidence suitable for controlled enterprise review | L | High | Events have schema versions and integrity checks; sensitive fields are redacted; retention/access/export rules are documented and tested |
| AG-007 | P1 | Planned | Grounded policy retrieval | Makes planner proposals traceable to versioned policy evidence | M | Medium | Local corpus has document IDs/versions; plans cite retrieved evidence; evals cover stale, missing, and conflicting context; unsupported actions fail safely |
| AG-008 | P2 | Planned | Governance scorecard and runtime view | Lets a PM or operator see outcome mix, approval latency, denials, failures, and trace gaps | M | Medium | View uses structured events; filters by agent/tool/outcome; metrics have definitions; empty/error states are clear; no raw sensitive payloads are exposed |
| AG-009 | P2 | Planned | Reversible action and rollback contract | Gives operators a defined recovery path for supported writes | L | High | Tool metadata declares reversibility; reversible mock action can roll back idempotently; rollback decision and outcome are audited; irreversible actions are explicit |
| AG-010 | P2 | Planned | Portfolio case study and one-command demo | Makes the product problem, decisions, evidence, and limitations easy to evaluate | S | Low | Setup/test/demo commands work from a clean checkout; case study covers problem, users, tradeoffs, results, risks, and next step; screenshots match current behavior |

## Recommended Next Issue

Start with **AG-005: Durable governance state**. AG-004 now authenticates and authorizes the local approver, but approval, authorization, receipt, and path evidence is still process-local and cannot support restart or multi-worker guarantees.

## Definition of Ready

A backlog item is ready when it has:

- A named user or reviewer and a concrete problem.
- An observable outcome rather than only an implementation instruction.
- Explicit security and governance assumptions.
- Acceptance criteria covering behavior, evidence, and failure paths.
- Dependencies and non-goals.

## Definition of Done

An item is done when:

- Acceptance criteria pass with automated tests or documented validation.
- Relevant policy, audit, privacy, and rollback impacts are addressed.
- Documentation and demo behavior match the implementation.
- The [Decision Log](DECISION_LOG.md), [Risk Register](RISK_REGISTER.md), and [Project Status](../../PROJECT_STATUS.md) are updated when materially affected.
