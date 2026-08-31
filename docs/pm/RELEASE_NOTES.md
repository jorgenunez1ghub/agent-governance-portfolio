# Release Notes

| Field | Value |
|---|---|
| Purpose | Summarize shipped product behavior, validation evidence, and known limitations by release. |
| Owner | Agent Governance product owner |
| Update cadence | Every release |
| Last updated | 2026-08-04 |

## 0.5.0 — Authorized Human Approval

### Product Outcome

Approval and rejection now require a registered human-review identity with authority over the exact action. The runtime fails closed on missing, invalid, self-approving, inactive, or out-of-scope actors and preserves decision evidence across the execution trace.

### Added or Changed

- Bearer authentication with fingerprint-only in-process credential lookup.
- Approver roles, active state, tool/risk scopes, and permitted actions.
- Requester/agent/approver separation-of-duties checks with stable reason codes.
- HTTP `401` authentication and HTTP `403` authorization failure contracts.
- Approver and authorization-decision IDs on records, receipts, paths, responses, and audit events.
- `GET /governance/approvers` metadata inspection without credentials.
- Fixture schema `1.2.0` with self-approval, scope-denial, and authorized-rejection scenarios.
- Python `3.12.13`, pinned `requirements.lock`, and canonical `make verify`.

### Validation

- `make verify`: **passed**
- Policy evaluations: **16/16 scenarios passed**
- Automated tests: **51 passed**
- Results recorded on 2026-08-04.

### Risks and Limitations

- Requester `user_id` is still an unverified claim; equality-based separation is not real-world identity proof.
- Source-known demo bearer defaults must be replaced and do not provide rotation, revocation, federation, or protected administration.
- Governance state is in memory and not restart-safe or multi-worker safe.
- Audit evidence remains mutable local JSONL.

### Upgrade or Rollback Notes

- Approval clients must now send `Authorization: Bearer <token>`.
- Set all token variables in `.env.example` before shared use; shared use remains unsupported.
- Rollback to `0.4.0` removes approver enforcement and identity-bound evidence; do not expose approval endpoints after rollback.

### Next Recommended Increment

Implement AG-005 transactional governance state, cross-worker uniqueness, and restart recovery.

## 0.4.0 — Receipt-Backed Approval Execution

### Product Outcome

An approved action now has deterministic behavior under duplicate requests, expiry, and tool failure. Each real attempt produces an inspectable receipt; a repeated key replays that receipt without repeating the side effect.

### Added or Changed

- Explicit approval states: `pending`, `executing`, `execution_failed`, `executed`, `rejected`, and `expired`.
- Configurable approval TTL with fail-closed HTTP `410` behavior.
- `Idempotency-Key` support with a stable approval-scoped default for existing callers.
- Immutable execution receipts with exact governance/action binding, attempt number, key fingerprint, status, retryability, result/error, and timestamps.
- Retryable and terminal tool failure types with new-key retry rules.
- Receipt-aware approval/path responses and audit events.
- `GET /governance/approvals/{approval_id}` for receipt-history inspection.
- Fixture schema `1.1.0` with duplicate, expiry, retryable-failure, and terminal-failure scenarios.
- Demo step that repeats the same approval key and proves receipt replay.

### Validation

- `.venv/bin/python -m evals.run_policy_evals`: **13/13 scenarios passed**
- `.venv/bin/pytest -q`: **36 passed**
- API integration tests verified one tool execution and same-receipt replay.
- Results recorded on 2026-07-30.

### Risks and Limitations

- Approval, receipt, and path state remains in memory and is not restart-safe.
- Idempotency is enforced in one process only; multiple workers need transactional uniqueness.
- Approver identity remains unauthenticated and unauthorized.
- Unknown external timeout outcomes do not yet have a reconciliation protocol.
- Audit evidence remains a mutable local JSONL file.

### Upgrade or Rollback Notes

- Existing clients may omit `Idempotency-Key`; they receive a stable approval-scoped key.
- Clients that intentionally retry a declared retryable failure must send a new key.
- Rollback to `0.3.0` removes receipt history and reintroduces duplicate-execution risk; do not roll back while approval requests are active.

### Next Recommended Increment

Implement AG-004 approver identity, role/scope authorization, and separation-of-duties scenarios.

## 0.3.0 — Evaluated, Path-Aware Policy

### Product Outcome

The runtime can now consider backend-managed prior action outcomes before authorizing a proposed action. A normally allowed write is escalated to human review after a failed, denied, or rejected action on the same path, and a versioned evaluation suite verifies both decisions and execution/trace invariants.

### Added

- Versioned `1.0.0` policy scenario fixture with nine reference scenarios.
- Dependency-free evaluation runner with human-readable and JSON output.
- Trace-completeness checks for run, agent, policy, tool, path, and action identifiers.
- Backend-managed ordered execution paths and normalized action records.
- `path_id` continuation with agent ownership checks.
- Policy `2.1` adverse-path write escalation.
- Read-only investigation after an adverse path outcome.
- Approval binding to path and path-action identifiers.
- `GET /governance/paths/{path_id}`.
- `path_action_recorded` and `path_action_updated` audit events.

### Validation

- `.venv/bin/python -m evals.run_policy_evals`: **9/9 scenarios passed**
- `.venv/bin/pytest -q`: **25 passed**
- Results recorded on 2026-07-29.

### Known Limitations

- Approval and execution-path stores are in memory.
- Concurrent requests can evaluate the same stale path revision.
- The path policy contains one narrow escalation rule, not a general path-policy language.
- Adverse status remains on the path; there is no reviewed recovery/clearance transition.
- Approval expiry, idempotency, receipts, and authenticated approvers are not implemented.
- All `0.2.0` local-demo limitations still apply.

### Recommended Next Release

Completed in [0.4.0](#040--receipt-backed-approval-execution).

## 0.2.0 — Explainable Policy Decisions

### Product Outcome

The runtime now explains why an agent-proposed action is allowed, paused for human approval, or denied. Decisions are tied to a registered agent and a versioned tool, and the resulting evidence can be inspected through API responses and audit events.

### Added

- Static agent identity registry with owner, purpose, autonomy level, and allowed tools.
- Versioned tool metadata with owner, source, risk class, and provenance status.
- Structured policy decisions with decision IDs, policy version, matched rules, reason codes, and explanations.
- `allow`, `require_approval`, and `deny` outcomes.
- Approval records bound to agent, policy decision, tool, version, and validated arguments.
- `GET /governance/agents` and `GET /governance/tools`.
- Correlated agent, decision, tool, and version fields in audit events.
- Demo coverage for allowed, approval-required, and denied actions.

### Validation

- `.venv/bin/pytest -q`
- Result on 2026-07-24: **19 passed**

### Known Limitations

- Planner and retrieval are mocked.
- Agent, policy, and approval state is local/static or in memory.
- API users and approvers are unauthenticated.
- Tool provenance is declared, not cryptographically verified.
- Policy is single-action rather than path-aware.
- JSONL audit data is mutable and intended for development only.

### Recommended Next Release

Create a policy evaluation harness with versioned scenarios, expected decisions, execution invariants, and trace-completeness checks. Then add the minimal path state required for path-aware policy.

## Release Entry Template

## X.Y.Z — Release title

### Product Outcome

### Added or Changed

- <!-- Add shipped behavior. -->

### Validation

- <!-- Add commands, evaluations, and results. -->

### Risks and Limitations

- <!-- Add residual risk and scope boundaries. -->

### Upgrade or Rollback Notes

- <!-- Add migration or recovery guidance. -->

### Next Recommended Increment

- <!-- Add one outcome-focused next step. -->
