# Risk Register

| Field | Value |
|---|---|
| Purpose | Track material product, technical, security/privacy, and delivery risks with explicit treatment. |
| Owner | Agent Governance product owner |
| Update cadence | Weekly; immediately before adding a real tool, data source, or deployment |
| Last updated | 2026-08-04 |

## Scoring

- Likelihood and impact use **Low / Medium / High**.
- **Open** means treatment is still required.
- **Accepted for local demo** does not authorize production use.

## Active Risks

| ID | Category | Risk | Likelihood | Impact | Status | Owner | Trigger / evidence | Mitigation | Contingency |
|---|---|---|---|---|---|---|---|---|---|
| R-001 | Security | Approver credentials are source-known local defaults and requester identity is unverified | High outside local use | High | Partially mitigated by local bearer auth and scope checks; blocks shared deployment | Security owner | Any network-accessible, shared, or consequential deployment | Replace demo credentials; authenticate requester and approver through a trusted provider; add rotation, revocation, TLS, rate limits, and protected administration | Disable approval execution and external-write tools |
| R-002 | Technical | Approval, receipt, and execution-path state is in memory and is lost on restart | High | High | Open | Backend owner | Restart, multiple workers, or process failure | Add durable transactional state and explicit recovery semantics | Fail unresolved approvals closed and require a new path/run |
| R-003 | Governance | The first path-aware rule covers adverse outcomes but not general multi-step constraints | Medium | High | Mitigated for the reference scenario; open for broader autonomy | Governance owner | New chained tools, branches, aggregate risk, or sequence-specific constraints | Add reviewed path rules and versioned scenarios incrementally | Limit the runtime to documented path semantics and local mock tools |
| R-004 | Security | Tool provenance is self-declared metadata rather than verified evidence | Medium | High | Open | Supply-chain owner | Loading packages or remotely managed tools | Add allowlisting, artifact identity, signature/attestation checks, and review gates | Block any tool without verified provenance |
| R-005 | Privacy | Audit payloads may capture task text, tool arguments, or personal data in a mutable local file | Medium | High | Open | Privacy owner | Real user data or external integrations | Data classification, field minimization, redaction, access controls, retention, and deletion policy | Stop ingestion, isolate the log, and remove affected demo data through an approved process |
| R-006 | Technical | Approval retry or execution failure can create ambiguous state or duplicate side effects | Medium | High | Mitigated in one process; open across restarts/workers and uncertain external outcomes | Backend owner | Client retries, timeout, process loss, or tool failure after approval | Implemented key replay, receipts, expiry, and explicit failed/retryable states; add transactional uniqueness and external reconciliation in AG-005 | Reconcile by run/approval/tool receipt; disable retries for non-idempotent tools |
| R-007 | Product | Mock planner and retrieval can overstate how close the MVP is to a production agent | High | Medium | Mitigated in docs | Product owner | Portfolio or stakeholder review | Label mock boundaries consistently; demonstrate control-plane value, not model intelligence | Narrow claims and show the roadmap gap explicitly |
| R-008 | Evaluation | The deterministic scenario suite may miss unknown false allows, policy conflicts, concurrency, and recovery failures | Medium | High | Mitigated for the current contract; open for production claims | Evaluation owner | New policy rule, agent, tool, persistence layer, or deployment model | Version fixtures with every control change; add adversarial, concurrency, restart, latency, and statistical tests | Freeze affected capability until its scenario coverage is reviewed |
| R-009 | Security | Audit JSONL is mutable and has no integrity or non-repudiation control | Medium | High | Open | Platform owner | Compliance evidence or incident investigation requirement | Append-only controlled storage, schema versions, hashes/signatures, protected clocks, and export controls | Treat local logs as debugging evidence only |
| R-010 | Delivery | Roadmap can expand into a broad platform before the core governance hypothesis is evaluated | Medium | Medium | Open | Product owner | Adding UI, cloud, connectors, or multiple models before AG-005/AG-006 | Require milestone exit criteria and keep one thin vertical slice | Defer integrations and return to the top authorization/durability gap |
| R-011 | Product | Approval fatigue can cause rubber-stamping if controls are not proportional | Medium | High | Future | Product and governance owners | High approval volume or low rejection rate | Risk-tier controls, clear rationale, batching rules, and approval quality metrics | Reduce agent scope or disable affected write actions |
| R-012 | Delivery | Runtime and transitive dependency drift can make verification machine-specific | Medium | Medium | Mitigated with `.python-version`, `requirements.lock`, and `make verify`; portability check remains | Repository owner | Clean bootstrap or second-machine verification differs | Refresh the pinned lock intentionally and run the canonical gate from a clean clone on the M1 | Preserve the last verified lock and record bootstrap failure evidence |
| R-013 | Technical | Concurrent requests can evaluate the same stale path snapshot and append conflicting actions | Medium in shared use | High | Open | Backend owner | Parallel requests reuse one `path_id` or multiple workers serve the runtime | Add path revision numbers, optimistic concurrency/locking, and transactional persistence | Reject concurrent writes to one path and require resubmission from the latest revision |

## Risks That Block Real External Tools

R-001, R-002, R-003, R-004, R-005, R-006, R-009, and R-013 must have approved treatments before this runtime is connected to a consequential external system.

## Review Questions

1. Did the change expand who or what can act?
2. Did it introduce a new tool, data class, external recipient, or side effect?
3. Can retries, stale approvals, or partial failures create a second execution?
4. Does the audit record contain enough evidence without exposing unnecessary data?
5. Which scenario proves the control, and what happens when the control is unavailable?
