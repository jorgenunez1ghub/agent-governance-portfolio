# Research Context

These notes explain why Milestone 1.5 is intentionally focused on governed execution rather than model intelligence.

## Source Notes

- Gartner, May 26, 2026: [Applying Uniform Governance Across AI Agents Will Lead to Enterprise AI Agent Failure](https://www.gartner.com/en/newsroom/press-releases/2026-05-26-gartner-says-applying-uniform-governance-across-ai-agents-will-lead-to-enterprise-ai-agent-failure)
- arXiv, March 17, 2026: [Runtime Governance for AI Agents: Policies on Paths](https://arxiv.org/abs/2603.16586)
- arXiv, May 27, 2026: [Technical Report: Exploring the Emerging Threats of the Agent Skill Ecosystem](https://arxiv.org/abs/2605.28588)

The pasted arXiv link `2605.28588` is not the "Policies on Paths" paper. It is a separate security report about malicious and vulnerable agent skills. Both are useful, but they support different roadmap items.

## Core Thesis

The future bottleneck for agent systems is governed execution.

Better models can improve reasoning quality, but they do not solve the operational control problem. Once agents can use tools, touch systems, or communicate externally, the runtime has to decide what can execute, under what conditions, with what human oversight, and with what audit trail.

Milestone 1.5 proves the smallest useful slice of that pattern:

```text
request -> context + plan -> tool registry -> schema validation -> policy check -> approval gate -> execution -> audit log
```

## Gartner Alignment

Gartner's May 2026 argument is that AI agent governance fails when organizations apply the same controls to every agent regardless of autonomy level and scope. The article distinguishes agent autonomy levels from read-only observation through autonomous action.

This MVP maps to that idea in a deliberately small way:

- `lookup_policy` demonstrates read-only behavior.
- `create_action_item` demonstrates low-risk internal execution.
- `send_external_message` demonstrates an action that pauses for explicit approval.

The important design point is proportional governance. A policy lookup should not carry the same burden as an external message or infrastructure change.

## Policies On Paths Alignment

The "Policies on Paths" paper argues that access control is necessary but not sufficient. The core governance object is the execution path: the sequence of actions already taken plus the next proposed action.

Milestone 1.5 created the seam for path-aware policy:

- The runtime records each step as an audit event.
- Tool execution is centralized in the runtime.
- Policy is a separate module.
- Approval is a separate state transition.
- The model proposes actions, but the backend enforces validation and authorization.

Milestone 2.5 now evolves the decision input from:

```text
evaluate_policy(agent_identity, proposed_action)
```

to:

```text
evaluate_policy(agent_identity, partial_path, proposed_action)
```

The partial path is backend-managed and contains normalized prior action outcomes. The first path-aware rule escalates a write after a prior validation failure, denial, rejection, or execution failure. It is intentionally narrower than a production path-policy system.

## Agent Skill Ecosystem Alignment

The `2605.28588` report is useful for a different reason: it highlights that agent skills and tools can become a supply-chain risk. If a runtime can load external skills, the governance layer must eventually validate more than tool input.

Future roadmap implications:

- Tool registry metadata should include source, version, owner, and risk class.
- New tools should pass security review before registration.
- External tool packages should be scanned before use.
- Audit events should record which tool version executed.
- Approval policy should consider both action risk and tool provenance.

Milestone 1.5 keeps tools local and mocked, so this risk is intentionally out of scope for now.

## Industrial And Mission-Critical AI

This repo can be framed as a control-plane prototype for domains where agent actions can have real-world consequences:

```text
Physical system
Telemetry
Digital twin
AI analytics
Agents
Runtime governance
Human oversight
```

Examples:

- Read telemetry: read-only access and usage logging.
- Recommend maintenance: recommendation plus human review.
- Send external notifications: approval gate and audit trail.
- Reconfigure infrastructure: approval, rollback, monitoring, and incident response.
- Modify mission systems: highest scrutiny, continuous monitoring, emergency shutdown, and post-incident review.

The same model can appear in each case. The governance requirements change with autonomy, access, impact, context, and execution history.

## Roadmap Additions

Milestone 2.0 implemented static identity and provenance inputs to an explainable policy engine. Milestone 2.5 added the first path-aware rule and a versioned evaluation harness. Milestone 2.6 added expiry, idempotent receipt replay, and explicit failure semantics. Milestone 2.7 authenticates local approvers, enforces scoped authority and separation of duties, and binds that evidence to execution. The remaining roadmap is:

1. Durable, transactional, concurrency-safe approval, authorization-decision, receipt, and path state.
2. Trusted requester and approver identity federation with lifecycle controls.
3. Broader path-aware rules.
4. Rollback manager for reversible actions.
5. Runtime monitor with policy and evaluation summaries.
6. Statistical/adversarial evaluations beyond deterministic reference fixtures.
7. Persistent and protected policy administration.

The audit model now includes agent and approver identity, policy and authorization decisions, tool version, execution path/action, approval, and execution-receipt IDs. The remaining additions would move the repo from an evaluated local path-aware proof into an Agent Governance Reference Architecture.
