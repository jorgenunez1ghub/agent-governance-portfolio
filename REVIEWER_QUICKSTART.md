# Five-Minute Reviewer Quickstart

This guide follows one concrete claim through the public policy evaluation: a reviewer whose registered scope excludes an external, high-risk action cannot authorize it, and the attempted approval does not execute the tool.

The walkthrough uses only files in this repository. No private repository, credentials, running API, or external service is needed.

## Walkthrough

1. **Read the claim and limits.** See [Approver Authentication and Authorization Contract](docs/approver-authorization.md), especially “Authorization Rules” and “Important Trust Boundary.” A high-risk external write is outside the `limited-approver` identity’s registered scope; the requester identity is still an unverified caller claim.
2. **Find the scenario.** Open [policy_scenarios.v1.json](evals/scenarios/policy_scenarios.v1.json) and locate `deny_approver_outside_scope`. It requests a high-risk external message, then attempts approval as `limited-approver`.
3. **Inspect the expected evidence.** The scenario expects the request to pause at `approval_required`, one `approval_authorization_denied` audit event, no authorization grant, approval execution, successful completion, or `tool_executed` event, a still-pending approval, and zero handler calls.
4. **Run the deterministic check** from the repository root with Python 3.12 and the locked dependencies installed:
   ```bash
   .venv/bin/python -m evals.run_policy_evals
   ```
   The harness selects the named scenario from the versioned suite, runs it against the local runtime, checks its expected events and outcomes, and exits nonzero if an assertion fails. The expected suite summary is `16/16 scenarios passed`; the named scenario should be `PASS deny_approver_outside_scope`.
5. **Trace how the result is recorded.** [Approver authorization](docs/approver-authorization.md) describes binding the authorization decision to approval and audit evidence. [Approval execution](docs/approval-execution.md) defines the receipt and failure behavior; [Audit Model](docs/audit-model.md) lists authorization audit events and the trace checks. The evaluation harness uses an isolated temporary audit JSONL file for the run, then checks the event stream; it does not leave a committed result bundle.

## Expected result and failure interpretation

A passing `deny_approver_outside_scope` result means the harness observed the scenario’s declared denial, no tool execution, and no handler invocation. If the scenario fails, read its printed assertion details: a missing denial event means the authorization decision was not recorded as expected; a grant, execution-start, completed-run, or tool-executed event means the forbidden path occurred; a handler count other than zero means the tool handler was invoked. Treat any such mismatch as a failed governance check requiring investigation, not as evidence that the control held.

## Verified

- In this versioned local evaluation, an out-of-scope approver is expected to be denied before approval execution.
- The harness checks for an authorization-denial event, forbids grant/execution/success events, checks that approval remains pending, and asserts zero handler calls.
- The full current policy suite is documented as 16 scenarios; run it to verify the checkout you are reviewing.

## Not Demonstrated

- Real-world requester identity: `user_id` is caller supplied and unverified.
- Production identity, credential lifecycle, durable or multi-worker state, or immutable production audit storage.
- That this single-process evaluation predicts behavior in a deployment or proves real-world safety.
- Reviewer speed, adoption, productivity improvement, or any measured human-performance outcome. The separate outcome protocol remains **PRE-REGISTERED / NOT RUN**.

This is a bounded, reproducible code-and-evaluation claim. It is not a production-readiness or generalized safety claim.
