# Five-Minute Reviewer Evidence Path

This walkthrough tests one narrow governance claim using only artifacts committed
to this public repository. It is an evidence-inspection path, not a production
readiness demonstration.

## Claim under review

**An authenticated reviewer cannot approve a pending action outside the
reviewer's registered tool and risk scope. Reviewer judgment does not silently
override that authorization floor.**

Representative scenario: `deny_approver_outside_scope`. A high-risk external
write is pending, but `limited-approver` is authorized only for medium-risk
internal action items.

## Review in five steps

1. Open the scenario contract at
   [`evals/scenarios/policy_scenarios.v1.json`](evals/scenarios/policy_scenarios.v1.json)
   and find `deny_approver_outside_scope`.
2. Confirm the expected control: the initial policy decision requires approval,
   the out-of-scope approval attempt raises `ApprovalAuthorizationError`, the
   approval remains pending, the tool handler is never called, and grant,
   approval, execution-start, tool-execution, and run-completion events are
   forbidden.
3. Open
   [`docs/approver-authorization.md`](docs/approver-authorization.md#authorization-rules)
   and confirm that both tool scope and risk scope are mandatory authorization
   checks.
4. Open the recorded public result at
   [`docs/outcome-evidence/internal-paired-20260827/policy_eval_results.json`](docs/outcome-evidence/internal-paired-20260827/policy_eval_results.json)
   and find the same scenario ID.
5. Verify that the recorded entry has `"passed": true` and
   `"failures": []`, then apply the evidence boundary below.

## Expected result

The committed result records `deny_approver_outside_scope` as passing with no
failures and nine audit events. The enclosing suite records 16 of 16 scenarios
passing for policy version `agent-governance-policy-2.1`, captured from source
commit `98573688e1459c4976c53e7a2a54deea01dcb405`.

To reproduce the current suite after completing the README setup:

```bash
.venv/bin/python -m evals.run_policy_evals
```

Expected summary:

```text
agent-governance-policy-core agent-governance-policy-2.1: 16/16 scenarios passed
PASS deny_approver_outside_scope (9 audit events)
```

The scenario line appears among the other scenario results. The command exits
with status 0 only when the entire suite passes.

## Failure interpretation

- Missing or renamed scenario/artifact: the documented evidence chain is broken.
- `"passed": false`, a non-empty `failures` list, a `FAIL` line, or a nonzero
  command exit: the current run does not verify the claim; inspect the reported
  assertion failures before relying on it.
- A fixture that permits the out-of-scope attempt to grant approval or invoke
  the tool: the scenario contract no longer asserts the claimed authority floor.
- A passing committed result verifies only the recorded source commit. Run the
  suite to evaluate a different revision.

## Verified

Within the deterministic local harness and recorded public run:

- the out-of-scope reviewer attempt is rejected;
- the approval remains pending;
- no tool side effect occurs;
- the scenario asserts required and forbidden audit events; and
- the scenario passed against the recorded policy version.

## Not Demonstrated

This evidence does **not** demonstrate:

- production identity, credential lifecycle, or authorization infrastructure;
- that the caller-supplied requester identity represents a verified person;
- durable, multi-process, or restart-safe governance state;
- tamper-resistant audit storage or real external-tool reconciliation;
- statistical safety, adversarial robustness, latency, adoption, or productivity
  outcomes; or
- production readiness or real-world safety.

For the broader limitations, see [Project Status](PROJECT_STATUS.md) and the
[Approver Authentication and Authorization Contract](docs/approver-authorization.md#important-trust-boundary).
