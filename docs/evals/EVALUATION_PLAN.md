# Policy Evaluation Plan

| Field | Value |
|---|---|
| Purpose | Define how the repo verifies policy behavior, execution invariants, path outcomes, and audit evidence. |
| Owner | Agent Governance evaluation owner |
| Update cadence | With every policy version or material runtime control change |
| Last updated | 2026-08-04 |

## Evaluation Question

Does the governed runtime produce the expected decision, prevent prohibited or duplicate execution, preserve approval binding, and emit a complete receipt-correlated trace for each reference scenario?

## Run

```bash
.venv/bin/python -m evals.run_policy_evals
```

For machine-readable output:

```bash
.venv/bin/python -m evals.run_policy_evals --json
```

The command returns exit code `0` only when every scenario passes.

## Versioned Assets

- Fixture schema: `1.2.0`
- Policy contract: `agent-governance-policy-2.1`
- Scenario source: `evals/scenarios/policy_scenarios.v1.json`
- Runner: `evals/run_policy_evals.py`
- Harness: `evals/harness.py`

The fixture is validated with Pydantic using `extra="forbid"` so misspelled or unsupported fields fail before evaluation.

## Reference Scenario Matrix

| Scenario | Expected control | Execution invariant |
|---|---|---|
| Trusted internal write | `allow` | Tool executes |
| External write | `require_approval` | Tool executes only after approval |
| Out-of-scope tool | `deny` | Tool never executes |
| Unknown agent | `deny` | Tool never executes |
| Unverified provenance | `deny` | Tool never executes |
| Invalid input | Validation failure before policy | Policy and tool execution never occur |
| Approval version mismatch | Transition error | Approved tool version cannot drift |
| Write after failed path action | `require_approval` | Normally allowed write pauses |
| Read after failed path action | `allow` | Read-only investigation remains available |
| Duplicate approval key | Receipt replay | Tool executes once and the same receipt is returned |
| Expired approval | `expired` / HTTP `410` | Tool never executes and no receipt is created |
| Retryable tool failure | Failed receipt, then success | Same key replays failure; a new key retries once |
| Terminal tool failure | Terminal failed receipt | Same key replays failure; a new key is blocked |
| Requester self-approval | Authorization denial | Tool never executes and approval remains pending |
| Approver outside tool/risk scope | Authorization denial | Tool never executes and approval remains pending |
| Authorized rejection | Rejected | Tool never executes and actor evidence is retained |

## Assertions Per Scenario

- API/runtime status.
- Policy outcome and exact reason codes when policy runs.
- Presence or absence of tool execution.
- Required and forbidden audit event types.
- Ordered path action outcomes.
- Number of prior path actions evaluated.
- Expected exception for version mismatch.
- Approval state and ordered execution-receipt statuses.
- Approval-attempt response statuses and idempotent-replay count.
- Exact tool-handler call count across retries and replays.
- Trace completeness:
  - `run_started` exists.
  - A terminal or pause event exists after the normalized path action is recorded.
  - `path_action_recorded` exists.
  - Every run event carries the expected `path_id` and `path_action_id`.
  - Every policy event identifies agent, decision, tool, and version.
  - Receipt events carry the expected `execution_receipt_id`, `approver_id`, and `approval_authorization_decision_id`.
- Authorization-denial scenarios emit the exact denied-event count and no side effect.

## Isolation

Each scenario receives:

- A temporary audit file.
- Empty in-memory approval and execution-path stores.
- Temporary tool metadata and behavior overrides that are restored after the scenario.
- Temporary approval-TTL overrides that are restored after the scenario.

This prevents scenario order from influencing results.

## Change Control

When policy behavior intentionally changes:

1. Create a new policy version.
2. Add or revise scenarios that express the intended product behavior.
3. Preserve the prior fixture when historical reproducibility matters.
4. Run the scenario suite and automated tests.
5. Update the decision log, risk register, milestone contract, and release notes.

Do not change an expected result only to make a failing implementation pass. The fixture represents the reviewed control contract.

## Current Evidence

On 2026-08-04:

- Policy scenarios: **16/16 passed**.
- Automated tests: **51 passed**.
- Canonical gate: **`make verify` passed**.

## Remaining Evaluation Gaps

- No statistical false-positive/false-negative estimate beyond the deterministic reference matrix.
- No concurrency, restart, load, latency, or chaos scenarios.
- No real identity provider, authenticated requester, model, retrieval corpus, external tool, or privacy data.
- No adversarial mutation of audit records or supply-chain artifacts.
- No cross-process idempotency, transactional recovery, or real external-side-effect reconciliation scenario.
