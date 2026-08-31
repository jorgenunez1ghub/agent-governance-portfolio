# Project Status

| Field | Value |
|---|---|
| Purpose | Provide a concise, evidence-based view of delivery status and the next decisions. |
| Owner | Agent Governance product owner |
| Update cadence | Weekly and after every milestone |
| Last updated | 2026-08-31 |
| Current release | `0.5.0` / Milestone 2.7 |
| Overall status | Public portfolio artifact published with local controls and benchmark infrastructure implemented; measured outcomes remain unestablished |

## Current State

Agent Governance MVP is a local FastAPI control-plane prototype for governed agent execution. It demonstrates that a model or planner can propose an action while a backend remains responsible for tool lookup, input validation, policy evaluation, human approval, execution, and audit evidence.

The current implementation is suitable for a local portfolio demo and design discussion. It is not a production authorization service.

This clean-history repository is the sanitized public portfolio artifact. It excludes private development history and begins with new commits authored by `jorgenunez1ghub` through the GitHub-provided no-reply address.

The included outcome-evidence scenario contract, pre-registered protocol, benchmark harness, and configuration gate provide a measurement system only; they have not produced measured reviewer-performance outcomes.

## What Works

- Context retrieval and mock planning run concurrently with `asyncio.gather()`.
- A registry resolves three versioned tools and validates their Pydantic inputs.
- Registered agent identities define purpose, autonomy level, and allowed tools.
- Policy evaluation produces explainable `allow`, `require_approval`, or `deny` decisions.
- Backend-managed execution paths preserve ordered, normalized action outcomes.
- A prior failed, denied, or rejected action escalates the next write on the same path.
- Read-only investigation remains available after an adverse path outcome.
- External writes pause for human approval.
- Approval and rejection endpoints authenticate bearer credentials against registered approver identities.
- Active state, permitted action, tool scope, risk scope, and separation of duties are enforced before transition.
- Approval records are bound to the requester claim, agent, policy decision, path action, tool, and tool version.
- Approver and authorization-decision IDs persist across approval records, receipts, path actions, responses, and audit evidence.
- Pending approvals expire and fail closed before tool execution.
- Idempotency-key replay returns the original execution receipt without repeating a side effect.
- Every execution attempt records an immutable success or failure receipt.
- Retryable failures require a new key; terminal failures and post-success duplicates remain closed.
- Structured JSONL audit events correlate runs, decisions, approvals, paths, and executions.
- Read-only endpoints expose registered agents, approver scopes, tool metadata, execution paths, approvals, and receipts.
- A versioned scenario harness verifies decisions, execution invariants, and trace completeness.
- A fixed eight-scenario outcome benchmark, pre-registered protocol, and fail-closed bundle workflow are implemented.
- The canonical gate validates the outcome-benchmark configuration before any participant observations are collected.
- `demo_flow.sh` exercises allowed, approval-required, denied, invalid, and path-escalated actions.
- Policy evaluations pass: **16/16 scenarios on 2026-08-30**.
- The automated suite passes: **62 tests on 2026-08-31**.
- `make verify` is the canonical test, evaluation, compilation, and shell-validation gate.

**Benchmark infrastructure shipped; measured outcome not yet established.** The protocol remains **PRE-REGISTERED / NOT RUN**, and no measured-results bundle exists.

## What Is Incomplete

- Retrieval and planning are mocked; there is no model provider, RAG pipeline, or citation validation.
- Path-aware policy has one deliberately narrow escalation rule; it does not yet express general multi-step constraints.
- Agent and approver identities are static; approvals, authorization decisions, receipts, paths, and policies are in memory.
- Concurrent updates to one path are not locked or coordinated across workers.
- Requester `user_id` remains an unverified claim; approvers use a local bearer registry rather than an external identity provider.
- Source-known demo credentials have no rotation, revocation, federation, or protected administration.
- Tool provenance is declared metadata, not verified through signatures or package scanning.
- Audit data is a mutable local file without retention, redaction, integrity, or export controls.
- There is no rollback manager, runtime monitoring UI, production persistence, or deployment configuration.
- Evaluation is deterministic and reference-scenario based; it does not yet measure statistical false-positive/false-negative rates, concurrency, restart recovery, or latency.
- No baseline or assisted participant observations have been collected, so reviewer time, correction burden, usefulness, and comparative outcome claims remain unmeasured.

## Known Risks

The highest current risks are unverified requester identity, source-known local demo credentials, volatile approval/receipt/path state, cross-worker races, mutable audit records, and overstating benchmark infrastructure as measured evidence. The idempotency guarantee is single-process only. These constraints are acceptable only inside the documented local-demo boundary.

See [Risk Register](docs/pm/RISK_REGISTER.md) for owners, triggers, mitigations, and contingencies.

## Next Three Recommended Tasks

1. **Collect the independent paired observations.** Complete the frozen baseline-first and assisted-second run before making or closing any measured-outcome claim.
2. **Make governance state durable (AG-005).** Persist approvals, authorization decisions, receipts, and execution paths transactionally with restart and recovery tests.
3. **Protect audit integrity (AG-006).** Add redaction, integrity checks, retention, and export controls around receipt-linked evidence.

## Current Decision Needed

Choose the AG-005 persistence boundary and concurrency strategy: a transactional relational store with unique receipt keys is recommended before any multi-worker or restart-safe claim.

## Related PM Artifacts

- [Project Brief](docs/pm/PROJECT_BRIEF.md)
- [Roadmap](docs/pm/ROADMAP.md)
- [Backlog](docs/pm/BACKLOG.md)
- [Decision Log](docs/pm/DECISION_LOG.md)
- [Release Notes](docs/pm/RELEASE_NOTES.md)
