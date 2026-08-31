# Project Brief

| Field | Value |
|---|---|
| Purpose | Define the product problem, users, MVP boundary, and measurable outcomes. |
| Owner | Agent Governance product owner |
| Update cadence | At milestone planning or when product scope changes |
| Last updated | 2026-08-04 |

## Problem

Agentic systems can propose and execute actions across tools, people, and systems. Model quality alone does not determine whether those actions are safe or authorized. Teams need an inspectable runtime boundary that can validate a proposed action, apply controls proportional to its risk, pause for a human when required, and preserve evidence of what happened.

Many demos put planning and execution in the same opaque loop. That makes it difficult for an enterprise or public-sector reviewer to answer:

- Which agent acted, and under whose authority?
- Which tool and version was selected?
- Why was the action allowed, paused, or denied?
- Did a human approve the exact action that later executed?
- Can an operator reconstruct the decision from an audit trail?

## Target Users

### Primary

- AI platform and product teams prototyping governed tool-calling agents.
- Enterprise or public-sector reviewers evaluating agent control patterns.
- AI Product Managers who need a concrete, demoable reference architecture for autonomy, approvals, and auditability.

### Secondary

- Security, risk, compliance, and audit stakeholders reviewing how agent actions are controlled.
- Engineers who need a small test bed for policy and evaluation patterns.

## Product Goal

Build a small, understandable reference implementation that proves a model can remain an action proposer while a backend control plane owns validation, authorization, approval, execution, and audit evidence.

## User Value

The MVP gives technical and governance stakeholders a shared artifact they can run, inspect, test, and discuss. It turns abstract responsible-agent principles into explicit API behavior and evidence.

## MVP Scope

- Async request orchestration.
- Mock retrieval and planning.
- Versioned tool registry and Pydantic input validation.
- Registered agent identities with proportional autonomy and tool scope.
- Explainable `allow`, `require_approval`, and `deny` policy outcomes.
- Backend-managed ordered execution paths and a path-aware write-escalation rule.
- Authenticated, scope-checked human approval and rejection paths for external writes.
- Separation-of-duties checks between approver, declared requester, and governed agent.
- Approval binding to agent, policy decision, path action, tool, and version.
- Approval expiry, idempotency-key replay, and immutable per-attempt execution receipts.
- Explicit retryable and terminal execution failure semantics.
- Structured local audit events.
- Read-only governance inspection endpoints.
- Versioned product-level policy scenarios with trace-completeness assertions.
- Focused automated tests and a scripted demo flow.

## Non-Goals

- A general-purpose chatbot or autonomous agent platform.
- Production identity federation, requester authentication, durable authorization policy, persistence, or deployment.
- A real LLM, vector database, or enterprise data connector.
- Legal or regulatory compliance certification.
- Dynamic policy administration or a full policy-as-code engine.
- Cryptographic tool verification, tamper-proof logs, or a security operations console.
- Fully autonomous high-impact actions.

## Product Principles

1. **The planner proposes; the runtime enforces.**
2. **Control intensity follows action risk and agent autonomy.**
3. **No tool executes before schema validation and policy evaluation.**
4. **Approval applies to an exact proposed action and tool version.**
5. **Human approval requires authenticated identity, explicit authority, and separation of duties.**
6. **Every terminal outcome must be explainable and traceable.**
7. **The demo remains small enough for a reviewer to understand end to end.**

## Success Metrics

| Metric | MVP target | Evidence |
|---|---:|---|
| Core policy scenarios produce the expected outcome and reason code | 100% | Versioned evaluation fixtures |
| Denied or invalid actions that execute a tool | 0 | Runtime tests and audit assertions |
| Approval-required actions executed before approval | 0 | Approval state-transition tests |
| Duplicate approval replays that invoke a tool again | 0 | Versioned idempotency scenario and handler-call assertions |
| Unauthorized approval attempts that invoke a tool | 0 | Authorization scenarios and API/runtime assertions |
| Terminal runs with correlated decision and audit identifiers | 100% | Trace-completeness evaluation |
| Registered tools with owner, source, version, risk class, and provenance status | 100% | `/governance/tools` |
| Local automated test suite | 100% passing | `make verify` |
| Portfolio demo duration | Under 3 minutes | `demo_flow.sh` and demo script |

These targets demonstrate control behavior; they do not claim production reliability or regulatory compliance.

## Current MVP Evidence

As of 2026-08-04, the repo contains the Milestone 2.7 authorized-approval contract, three governed tools, two registered agent identities, four local approver identities, path-aware decisions, expiring and idempotent approval execution, identity-bound receipts, backend-managed ordered paths, JSONL audit logging, governance inspection endpoints, a scripted demo, 16 passing policy scenarios, and 51 passing tests.

## Definition of Done for the Next Increment

- Approval, authorization-decision, receipt, and path state survives restart.
- Receipt-key uniqueness is transactional across workers.
- Recovery tests prove an uncertain or completed execution is not repeated.
- Migrations and failure handling fail closed.
- `make verify` passes from the documented clean bootstrap.
