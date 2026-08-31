# Milestone 2.6: Receipt-Backed Approval Execution

## Objective

Make approval execution safe and inspectable under duplicate requests, stale approvals, and tool failures before connecting the runtime to a consequential external system.

## Delivered

- Approval states for pending, executing, retryable/terminal failure, executed, rejected, and expired outcomes.
- Configurable approval expiry with fail-closed HTTP `410` behavior.
- Approval-scoped idempotency keys with deterministic receipt replay.
- Immutable execution receipts bound to the approved agent, policy decision, path action, tool, version, and arguments.
- Explicit retryable and terminal tool failure types.
- New-key retries after retryable failure; terminal failures and post-success duplicates remain closed.
- Receipt-aware audit events and approval inspection API.
- Versioned scenarios for duplicate replay, expiry, retryable failure/recovery, and terminal failure.
- Demo proof that a repeated approval request returns the original receipt without repeating the side effect.

## Acceptance Evidence

Completed on 2026-07-30 in release `0.4.0`:

- Policy evaluation suite: **13/13 scenarios passed**.
- Automated tests: **36 passed**.
- API integration tests: duplicate approval replay returned the same successful receipt and one tool execution.
- Approval detail endpoint exposed ordered receipt status and attempt history.

## Boundaries

- Approval and receipt state is process-local and is lost on restart.
- Cross-worker concurrency and transactional recovery are not implemented.
- The approval actor is an API-supplied label, not an authenticated, authorized identity.
- The JSONL audit log is mutable local evidence rather than an integrity-protected record.

## Next Step

AG-004 should authenticate approvers, enforce role/scope and separation-of-duties rules, and preserve verified actor identity in each approval transition and receipt. AG-005 should then make the state machine transactional and restart-safe.
