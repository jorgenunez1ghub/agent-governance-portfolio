# Milestone 2.5: Evaluated, Path-Aware Policy

## Goal

Protect the Milestone 2.0 decision contract with versioned product-level evaluations, then make policy consider a backend-managed partial execution path:

```text
validated action + agent identity + tool provenance + prior path
    -> path-aware policy evaluation
    -> allow | require_approval | deny
    -> normalized path outcome + structured audit evidence
```

## In Scope

- Versioned JSON scenario fixtures and a dependency-free evaluation runner.
- Scenarios for allow, approval, deny, invalid input, unknown agent, untrusted provenance, and approval-version mismatch.
- Trace-completeness assertions for run, agent, policy, tool, path, and action identifiers.
- Backend-managed execution paths keyed by `path_id`.
- Ordered, typed action records with decision, approval, and execution outcomes.
- Agent ownership checks when a caller continues a path.
- A path-aware rule that requires human review for a write after a validation failure, denial, rejection, or execution failure.
- Read-only policy lookup after an adverse outcome.
- Inspection through `GET /governance/paths/{path_id}`.

## Out of Scope

- Durable, transactional path or approval persistence.
- Concurrent path-update locking or multi-worker coordination.
- Caller-supplied path history.
- General policy expression language or workflow engine.
- Approval expiry, idempotency keys, execution receipts, or authenticated approvers.
- Path compaction, retention, branching, merging, or cryptographic integrity.
- Real model, RAG, external tool, or production deployment.

## Policy 2.1 Rule Order

1. Agent must be registered.
2. Tool provenance must be trusted.
3. Tool must be in the agent's registered scope.
4. Agent autonomy must permit the tool risk.
5. A write after an adverse path outcome requires human review.
6. External writes require human approval.
7. High-risk writes require human approval.
8. Remaining trusted, in-scope actions may execute.

The path rule does not override identity, provenance, scope, or autonomy denials. It also does not block read-only investigation.

## Definition of Done

- The versioned suite runs with `.venv/bin/python -m evals.run_policy_evals`.
- All nine reference scenarios pass.
- Each scenario asserts expected status, policy outcome, reason codes, execution invariant, audit events, path outcomes, and trace identifiers.
- A failed action followed by a normally allowed write on the same path returns `require_approval`.
- The same failed path can still execute a trusted, in-scope read-only lookup.
- Decisions include the path ID and number of prior actions evaluated.
- Audit events include path and path-action identifiers.
- The complete automated suite passes.

## Result

Completed on 2026-07-29 in release `0.3.0`:

- Policy evaluation suite: **9/9 scenarios passed**.
- Automated tests: **25 passed**.

## Deferred Next Step

[Milestone 2.6](milestone-2.6.md) completes this next step with idempotency, expiry, explicit execution receipts, and failure/retry semantics.
