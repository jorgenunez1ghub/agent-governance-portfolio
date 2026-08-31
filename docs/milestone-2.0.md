# Milestone 2.0: Explainable Policy Decisions

## Goal

Turn the Milestone 1.5 approval flag into an explicit governance decision:

```text
validated action + agent identity + tool provenance + request risk
    -> policy evaluation
    -> allow | require_approval | deny
    -> structured response and audit event
```

The runtime must be able to explain which policy rules matched, why the outcome was selected, and exactly which agent and tool version the decision covered.

## In Scope

- Static agent identity registry with owner, purpose, autonomy level, and allowed tools.
- Versioned tool metadata with owner, source, risk class, and provenance status.
- Structured `PolicyDecision` records with a decision ID and policy version.
- `allow`, `require_approval`, and `deny` outcomes.
- Matched rules, reason codes, and a human-readable explanation.
- Policy decision data in agent responses and audit events.
- Approval records bound to agent ID, policy decision ID, and tool version.
- Read-only API endpoints for inspecting registered agents and tool metadata.
- Focused tests for each decision path.

## Out of Scope

- Dynamic policy configuration or policy-as-code.
- Path-aware evaluation of multi-step execution history.
- Authentication and authorization for users or approvers.
- Persistent agent, approval, or policy databases.
- Tool package scanning or signature verification.
- Real model or external tool integrations.
- Rollback, runtime monitoring UI, and production deployment.

## Decision Inputs

- Registered agent identity.
- Agent autonomy level and allowed-tool scope.
- Tool name and version.
- Tool risk class.
- Tool provenance status.
- Request risk level.

## Policy Rules

Rules are evaluated in this order:

1. The agent must be registered.
2. Tool provenance must be trusted.
3. The tool must be in the agent's allowed scope.
4. The agent's autonomy level must permit the tool risk.
5. External writes require human approval.
6. High-risk non-read-only requests require human approval.
7. Remaining trusted, in-scope actions may execute automatically.

## Definition of Done

- A trusted internal action from `demo-agent` returns `allow` and executes.
- An external write from `demo-agent` returns `require_approval` and pauses.
- A write requested by `read-only-agent` returns `deny` and never executes.
- An unknown agent is denied.
- An untrusted tool is denied by unit policy evaluation.
- Responses include the complete policy decision.
- Audit events include agent ID, policy decision ID, tool name, and tool version.
- Approvals cannot silently apply to a different tool version.
- Registered agents and tool provenance are inspectable through the API.
- The complete test suite passes.

## API Additions

- Optional `agent_id` on `POST /agent/run`, defaulting to `demo-agent`.
- `GET /governance/agents`.
- `GET /governance/tools`.
- `policy_decision` and `agent_id` on agent-run responses.
- `agent_id` and `policy_decision_id` on approval-action responses.

## Successor Milestone

[Milestone 2.5](milestone-2.5.md) adds versioned product-level policy evaluations and a backend-managed partial execution path while retaining this decision contract.
