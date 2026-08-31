# Milestone 2.7: Authorized Human Approval

## Objective

Close the AG-004 identity gap by requiring an authenticated approver, checking role and action scope, enforcing separation of duties, and preserving authorization evidence through the approval execution trace.

## Delivered

- Bearer authentication for approval and rejection endpoints.
- Static local approver identities with active state, role, tool scope, risk scope, and permitted actions.
- Separation-of-duties checks between approver, declared requester, and governed agent.
- HTTP `401` for authentication failures and HTTP `403` for authorization failures.
- Stable authorization reason codes and unique authorization-decision IDs.
- Approver and decision binding across approval records, receipts, path actions, API responses, and audit events.
- Read-only approver metadata inspection without credential exposure.
- Versioned evaluation scenarios for self-approval denial, scope denial, and authorized rejection.
- A pinned Python runtime/dependency snapshot and repository-level `make verify` gate.

## Evidence

Completed on 2026-08-04 in release `0.5.0`:

- Policy evaluation suite: **16/16 scenarios passed**.
- Automated tests: **51 passed**.
- Canonical verification: `make verify` passes tests, evaluations, compilation, and demo-shell validation.
- API tests prove missing and invalid credentials fail with `401`, recognized but unauthorized identities fail with `403`, and credentials never appear in approver metadata.

## Acceptance Criteria

1. Approval and rejection require a registered bearer credential. **Met.**
2. Role/action, tool, risk, active-state, and separation-of-duties rules run before approval state changes. **Met.**
3. Unauthorized attempts never invoke a tool and are audited with stable reason codes. **Met.**
4. Authorized identity and decision evidence persist across the record, receipt, path action, response, and audit trace. **Met.**
5. Evaluation scenarios cover self-approval, scope denial, and authorized rejection. **Met.**
6. Documentation states the local credential and unverified-requester limitations. **Met.**

## Deliberate Limitations

- Requester identity is a declared, unverified `user_id`; equality-based separation of duties is not proof of real-world identity.
- Demo bearer defaults are source-known and must not be used for a shared or consequential deployment.
- There is no external identity provider, signed token validation, rotation, revocation, delegated approval chain, or emergency-access workflow.
- Approval, receipt, path, identity, and authorization state remains process-local and non-transactional.
- Audit logs remain mutable local JSONL.

## Next Recommended Task

AG-005 should persist approvals, authorization decisions, receipts, and execution paths transactionally; enforce uniqueness across workers; and prove restart recovery without repeating a side effect.
