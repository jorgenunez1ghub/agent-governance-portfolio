# Approver Authentication and Authorization Contract

Release `0.5.0` adds an explicit identity boundary to approval and rejection. A bearer credential resolves to a registered approver; the runtime then evaluates that identity against the exact pending action before changing approval state or invoking a tool.

## Request Contract

`POST /approvals/{approval_id}/approve` and `POST /approvals/{approval_id}/reject` require:

```http
Authorization: Bearer <approver credential>
```

Missing or invalid credentials return HTTP `401` with `WWW-Authenticate: Bearer`. A recognized identity that lacks authority returns HTTP `403` with stable reason codes and an authorization-decision ID. Credentials are never returned by inspection APIs or written to audit records.

## Local Identity Registry

The MVP uses four static identities:

| Identity | Role | Tools | Risk | Actions |
|---|---|---|---|---|
| `demo-approver` | Risk reviewer | Internal action items and external messages | Medium, high | Approve, reject |
| `limited-approver` | Risk reviewer | Internal action items | Medium | Approve, reject |
| `governance-admin` | Governance administrator | All | All | Approve, reject |
| `audit-observer` | Audit observer | All | All | None |

Credentials come from `DEMO_APPROVER_TOKEN`, `LIMITED_APPROVER_TOKEN`, `GOVERNANCE_ADMIN_TOKEN`, and `AUDIT_OBSERVER_TOKEN`. Source-known defaults exist only so the local demo starts without external infrastructure. Replace every default with a secret of at least 16 characters before shared use.

The registry stores SHA-256 token fingerprints rather than raw tokens. This reduces accidental disclosure inside the process, but it is not a password-storage scheme or an identity-provider replacement.

## Authorization Rules

An approval or rejection is allowed only when all conditions hold:

1. The registered approver is active.
2. The approver is not the declared requester.
3. The approver is not the governed agent.
4. The requested approval action is permitted for the role.
5. The pending tool is inside the approver's tool scope.
6. The request risk level is inside the approver's risk scope.

The governance administrator has wildcard tool and risk scope but does not bypass separation of duties.

Stable denial reason codes are:

- `approver_inactive`
- `requester_cannot_approve_own_request`
- `agent_cannot_approve_own_action`
- `approval_action_not_permitted`
- `tool_outside_approver_scope`
- `risk_outside_approver_scope`

## Evidence Binding

Every granted or denied authorization receives a unique decision ID. Successful transitions bind the approver and decision ID to:

- the approval record;
- the immutable execution receipt;
- the normalized path action;
- the API response; and
- correlated audit events.

The trace distinguishes authentication failures, authorization grants, and authorization denials. It never logs bearer credentials or idempotency keys.

## Important Trust Boundary

The approver is authenticated. The request's `user_id` is still a caller-supplied, unverified claim. The separation-of-duties comparison therefore blocks matching identifiers and records `requester_identity_verified: false`, but it cannot prove the requester's real-world identity. Production use requires a trusted identity provider for both requesters and approvers, credential rotation/revocation, transport security, rate limiting, and durable authorization policy.

The registry and governance state are process-local. Restart, multi-worker uniqueness, and transactional recovery remain AG-005.
