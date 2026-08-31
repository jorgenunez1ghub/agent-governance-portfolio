# Audit Model

Audit events are JSON objects written one per line to:

```text
app/storage/audit_log.jsonl
```

Each event has this shape:

```json
{
  "timestamp": "2026-07-04T10:15:00Z",
  "event_type": "policy_evaluated",
  "actor": "policy-engine",
  "agent_id": "demo-agent",
  "policy_decision_id": "uuid",
  "tool_name": "create_action_item",
  "tool_version": "1.0.0",
  "path_id": "uuid",
  "path_action_id": "uuid",
  "details": {
    "outcome": "allow",
    "matched_rules": ["agent_must_be_registered", "tool_provenance_must_be_trusted"],
    "reason_codes": ["trusted_tool_within_agent_scope"]
  },
  "run_id": "uuid",
  "approval_id": null,
  "execution_receipt_id": null,
  "approver_id": null,
  "approval_authorization_decision_id": null
}
```

## Event Types

- `run_started`
- `context_retrieved`
- `plan_created`
- `tool_selected`
- `tool_validation_passed`
- `tool_validation_failed`
- `policy_evaluated`
- `approval_required`
- `approval_authentication_failed`
- `approval_authorization_granted`
- `approval_authorization_denied`
- `approval_approved`
- `approval_rejected`
- `approval_expired`
- `approval_execution_started`
- `approval_execution_replayed`
- `approval_execution_failed`
- `execution_receipt_recorded`
- `tool_executed`
- `run_completed`
- `run_denied`
- `run_failed`
- `path_action_recorded`
- `path_action_updated`

## Notes

`policy_evaluated` contains the complete policy decision: outcome, policy version, matched rules, reason codes, explanation, agent ID, request risk, and tool version.

The top-level agent, approver, authorization-decision, policy, tool, path, path-action, approval, and execution-receipt fields make policy and execution events easy to correlate without parsing event-specific details. `path_action_recorded` captures the normalized decision/execution outcome, while `path_action_updated` records an approval transition to executed, rejected, expired, or execution-failed.

Approval traces distinguish failed authentication, granted authorization, and denied authorization. Granted transitions identify the approver and authorization decision at receipt start, success, failure, replay, rejection, expiry, and path update. The `requester_identity_verified` detail remains `false` until requester authentication exists.

Approval execution traces identify the exact receipt at start, success, failure, and replay. A receipt includes only a fingerprint of the idempotency key; the raw client key is not logged or exposed.

The versioned evaluation harness checks that each run has a start event, a terminal or pause event, a recorded path action, consistent path identifiers, complete policy identity fields, receipt identifiers plus approver and authorization-decision identifiers on approval execution evidence.

The audit log remains local and append-only by convention; it is designed to make the runtime inspectable during development, not to replace production-grade immutable logging.
