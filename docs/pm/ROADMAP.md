# Product Roadmap

| Field | Value |
|---|---|
| Purpose | Sequence product outcomes from local proof to enterprise-ready reference architecture. |
| Owner | Agent Governance product owner |
| Update cadence | Monthly and at milestone exit reviews |
| Last updated | 2026-08-04 |

The roadmap uses product milestones rather than release version numbers. Release `0.5.0` satisfies Milestone 1 and delivers the evaluated, path-aware, identity-bound approval slice of Milestone 3.

## Roadmap Summary

| Milestone | Outcome | Status | Exit signal |
|---|---|---|---|
| 1. Local MVP | Demonstrate a complete governed execution loop locally | Complete | Allow, approve, deny, validate, execute, and audit paths pass |
| 2. Better Retrieval, Ranking, and Reasoning | Ground proposals in inspectable evidence | Planned | Planner outputs cite ranked evidence and pass groundedness checks |
| 3. Governance and Evaluation | Evaluate action paths and measure policy behavior | In progress | Versioned eval suite, path-aware decisions, local idempotent execution, and approver authorization pass; durability remains |
| 4. Demo-Ready Portfolio Version | Make value and tradeoffs obvious to a reviewer | Planned | One-command demo, visuals, scorecard, and case study are current |
| 5. Enterprise-Ready Version | Replace demo boundaries with durable controls | Future | Authenticated, persistent, observable, integrity-protected deployment |

## Milestone 1: Local MVP

**Outcome:** A reviewer can run and inspect the smallest complete governed-agent control loop.

**Delivered**

- Async FastAPI runtime with concurrent mock retrieval and planning.
- Tool registry, Pydantic validation, and three local mock tools.
- Registered agent identity and autonomy metadata.
- Explainable `allow`, `require_approval`, and `deny` policy decisions.
- Expiring human approval/rejection flow bound to an exact tool version.
- Receipt-backed idempotent approval execution with retryable/terminal failure states.
- Structured JSONL audit events and inspection endpoints.
- Demo script, 16 passing evaluation scenarios, and 51 passing tests.
- Authenticated local approver identities, scope authorization, and separation of duties.

**Exit criteria:** Met for the local-demo boundary.

## Milestone 2: Better Retrieval, Ranking, and Reasoning

**Outcome:** The planner proposes actions from traceable, relevant context rather than task-string heuristics.

**Candidate scope**

- A small local policy corpus with document IDs, versions, and effective dates.
- Retrieval and ranking with evidence included in the plan.
- Planner output that distinguishes facts, assumptions, and proposed actions.
- Citation validity, retrieval relevance, and unsupported-action evaluations.
- Safe behavior when evidence is missing, conflicting, or stale.

**Non-goal:** Optimizing model sophistication before governance evidence can be measured.

**Exit criteria**

- Every evidence-dependent proposal includes source identifiers.
- Evaluation fixtures include no-context, stale-context, and conflicting-context cases.
- Unsupported high-impact proposals fail closed or require review.

## Milestone 3: Governance and Evaluation

**Outcome:** Policy decisions account for execution history, and the team can quantify whether controls behave as intended.

**Delivered through `0.5.0`**

- Versioned policy scenario matrix and evaluation runner.
- Backend-managed path model containing ordered actions, decisions, approvals, and execution outcomes.
- A rule that escalates a write after an adverse partial-path outcome.
- Read-only investigation after an adverse outcome.
- Trace-completeness assertions across run, policy, tool, path, and action identifiers.
- Expiring approvals, idempotency-key replay, and immutable per-attempt execution receipts.
- Explicit retryable and terminal failure states with receipt-linked audit evidence.
- Local bearer-authenticated approver registry, scope checks, separation of duties, and identity-bound evidence.

**Remaining scope**

- Trusted requester/approver identity federation, lifecycle management, and delegated/emergency approval policy.
- Durable and concurrency-safe path/approval state.
- Evaluation measures for statistical false allows/denials, approval correctness, concurrency, restart recovery, and latency.
- Regression gates for the governance contract.

**Exit criteria**

- High-risk prohibited scenarios have zero false allows in the 16-scenario reference suite. **Met for current fixtures.**
- Every policy scenario has an expected outcome and reason code. **Met.**
- At least one multi-step scenario produces a different result from its single-action equivalent. **Met.**
- Approval retries cannot duplicate execution inside one running process. **Met.**
- All Milestone 2.0 behaviors remain covered. **Met.**

## Milestone 4: Demo-Ready Portfolio Version

**Outcome:** A hiring manager, product leader, or technical reviewer can understand the problem, product decisions, architecture, and evidence in less than ten minutes.

**Candidate scope**

- One-command setup and deterministic seeded scenarios.
- Lightweight runtime/evaluation scorecard.
- Architecture, data-flow, and governance visuals aligned with the implementation.
- Demo narrative for product, technical, governance, and portfolio lenses.
- Release notes, decision history, and a concise case study.
- Optional hosted demo with synthetic data and no consequential tools.

**Exit criteria**

- A clean checkout can complete setup, tests, and demo from documented commands.
- Demo outputs show decisions, reasons, approvals, and correlated audit evidence.
- Portfolio case study clearly separates delivered behavior from future architecture.

## Milestone 5: Enterprise-Ready Version

**Outcome:** Replace local-demo assumptions with a deployable reference control plane.

**Candidate scope**

- Authenticated users, agents, services, and approvers with least-privilege authorization.
- Durable, transactional approval and policy state.
- Policy administration, versioning, change approval, and rollback.
- Verified tool provenance, allowlisting, and supply-chain controls.
- Redaction, retention, access control, integrity protection, and export for audit data.
- Observability, alerts, SLOs, incident response, and kill-switch controls.
- Multi-tenant isolation, secrets management, deployment automation, and threat modeling.

**Exit criteria**

- Security and privacy reviews close all launch-blocking findings.
- Control behavior is verified in staging with failure and recovery tests.
- Operational ownership, SLOs, incident response, rollback, and evidence retention are documented.

## Sequencing Guardrail

Do not connect the runtime to consequential external systems until authentication, durable approval semantics, idempotent execution, and audit protections are implemented and evaluated.
