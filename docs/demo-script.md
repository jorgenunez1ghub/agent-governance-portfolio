# Demo Script

This demo proves the Milestone 2.7 evaluated, path-aware, identity-bound approval loop.

## Start the API

```bash
source .venv/bin/activate
uvicorn app.main:app --reload
```

## Run the Demo Flow

In another terminal:

```bash
./demo_flow.sh
```

If the API is running on a different URL:

```bash
BASE_URL=http://127.0.0.1:8001 ./demo_flow.sh
```

## Talk Track

1. `demo-agent` receives `allow` for a trusted, in-scope internal action.
2. Its external write receives `require_approval`, with matched rules and reason codes.
3. A bearer credential resolves to `demo-approver`; role, tool, risk, and separation-of-duties checks authorize the exact action before a receipt begins.
4. Repeating the same idempotency key returns the same successful receipt without a second tool execution.
5. `read-only-agent` receives `deny` when it proposes an internal write.
6. An invalid external message records a `validation_failed` path action.
7. A normally allowed internal write on that same path is escalated to `require_approval`.
8. `/governance/agents`, `/governance/approvers`, `/governance/tools`, paths, and approvals expose policy inputs, approver scopes, outcomes, and receipt history.
9. `/audit/recent` correlates each outcome with agent, approver, policy/authorization decisions, tool, path, action, approval, and receipt IDs.
10. The versioned policy evaluation harness reports 16 passing scenarios, including self-approval denial, scope denial, authorized rejection, expiry, and retry/terminal failure semantics.
11. `app/agent/runtime.py` still uses `asyncio.gather()` for concurrent retrieval and planning.

## What This Proves

The model is only a proposer. The backend owns tool lookup, schema validation, agent identity, tool provenance, execution-path state, explainable policy decisions, approver authentication/authorization, approval expiry, idempotent execution, receipt completion, and audit logging. The deterministic evaluation suite verifies decision results, side-effect counts, receipt states, and trace invariants.
