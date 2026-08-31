#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
APPROVER_TOKEN="${APPROVER_TOKEN:-${DEMO_APPROVER_TOKEN:-local-demo-approver-token-change-me}}"

safe_response="$(mktemp)"
risky_response="$(mktemp)"
approval_response="$(mktemp)"
replay_response="$(mktemp)"
denied_response="$(mktemp)"
invalid_response="$(mktemp)"
escalated_response="$(mktemp)"
audit_response="$(mktemp)"

cleanup() {
  rm -f \
    "$safe_response" \
    "$risky_response" \
    "$approval_response" \
    "$replay_response" \
    "$denied_response" \
    "$invalid_response" \
    "$escalated_response" \
    "$audit_response"
}
trap cleanup EXIT

print_step() {
  printf "\n==> %s\n" "$1"
}

summarize_response() {
  python3 - "$1" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as file:
    response = json.load(file)

summary = {
    "status": response.get("status"),
    "run_id": response.get("run_id"),
    "path_id": response.get("path_id"),
    "path_action_id": response.get("path_action_id"),
    "approval_required": response.get("approval_required"),
    "approval_id": response.get("approval_id"),
    "approval_expires_at": response.get("approval_expires_at"),
    "approver_id": response.get("approver_id"),
    "approval_authorization_decision_id": response.get(
        "approval_authorization_decision_id"
    ),
    "agent_id": response.get("agent_id"),
    "tool": (response.get("plan") or {}).get("tool_name")
        or (response.get("proposed_action") or {}).get("tool_name"),
    "policy_outcome": (response.get("policy_decision") or {}).get("outcome"),
    "reason_codes": (response.get("policy_decision") or {}).get("reason_codes"),
    "policy_decision_id": (response.get("policy_decision") or {}).get("decision_id")
        or response.get("policy_decision_id"),
    "evaluated_path_action_count": (response.get("policy_decision") or {}).get(
        "evaluated_path_action_count"
    ),
    "tool_result_status": (response.get("tool_result") or {}).get("status"),
    "execution_receipt_id": (response.get("execution_receipt") or {}).get("receipt_id"),
    "execution_receipt_status": (response.get("execution_receipt") or {}).get("status"),
    "attempt_number": (response.get("execution_receipt") or {}).get("attempt_number"),
    "idempotent_replay": response.get("idempotent_replay"),
    "retryable": response.get("retryable"),
}

print(json.dumps({key: value for key, value in summary.items() if value is not None}, indent=2))
PY
}

print_step "Checking FastAPI server at $BASE_URL"
curl -fsS "$BASE_URL/health" >/dev/null

print_step "1. Safe task runs immediately"
curl -fsS -X POST "$BASE_URL/agent/run" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "demo-user",
    "agent_id": "demo-agent",
    "task": "Create an internal action item to review project risk",
    "risk_level": "medium"
  }' > "$safe_response"
summarize_response "$safe_response"

print_step "2. Risky task pauses for approval"
curl -fsS -X POST "$BASE_URL/agent/run" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "demo-user",
    "agent_id": "demo-agent",
    "task": "Send an external message about the project risk",
    "risk_level": "high"
  }' > "$risky_response"
summarize_response "$risky_response"

approval_id="$(
  python3 - "$risky_response" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as file:
    response = json.load(file)

approval_id = response.get("approval_id")
if not approval_id:
    raise SystemExit("Risky task did not return an approval_id.")

print(approval_id)
PY
)"

print_step "3. Approval executes the pending tool"
curl -fsS -X POST "$BASE_URL/approvals/$approval_id/approve" \
  -H "Authorization: Bearer $APPROVER_TOKEN" \
  -H "Idempotency-Key: demo-approval-attempt" > "$approval_response"
summarize_response "$approval_response"

print_step "4. Repeating the same key replays the receipt without re-execution"
curl -fsS -X POST "$BASE_URL/approvals/$approval_id/approve" \
  -H "Authorization: Bearer $APPROVER_TOKEN" \
  -H "Idempotency-Key: demo-approval-attempt" > "$replay_response"
summarize_response "$replay_response"

print_step "5. Out-of-scope action is denied"
curl -fsS -X POST "$BASE_URL/agent/run" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "demo-user",
    "agent_id": "read-only-agent",
    "task": "Create an internal action item to review project risk",
    "risk_level": "medium"
  }' > "$denied_response"
summarize_response "$denied_response"

print_step "6. Invalid input records an adverse path outcome"
curl -fsS -X POST "$BASE_URL/agent/run" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "demo-user",
    "agent_id": "demo-agent",
    "task": "Send invalid external message about project risk",
    "risk_level": "high"
  }' > "$invalid_response"
summarize_response "$invalid_response"

path_id="$(
  python3 - "$invalid_response" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as file:
    response = json.load(file)

path_id = response.get("path_id")
if not path_id:
    raise SystemExit("Invalid task did not return a path_id.")

print(path_id)
PY
)"

print_step "7. The same path escalates a normally safe write"
curl -fsS -X POST "$BASE_URL/agent/run" \
  -H "Content-Type: application/json" \
  -d "{
    \"user_id\": \"demo-user\",
    \"agent_id\": \"demo-agent\",
    \"path_id\": \"$path_id\",
    \"task\": \"Create an internal action item to review project risk\",
    \"risk_level\": \"medium\"
  }" > "$escalated_response"
summarize_response "$escalated_response"

print_step "8. Governance inputs, approver scopes, receipts, and paths are inspectable"
curl -fsS "$BASE_URL/governance/agents" | python3 -c \
  'import json,sys; print("registered_agents:", ", ".join(a["agent_id"] for a in json.load(sys.stdin)))'
curl -fsS "$BASE_URL/governance/tools" | python3 -c \
  'import json,sys; print("registered_tools:", ", ".join(f"{t['"'"'name'"'"']}@{t['"'"'version'"'"']}:{t['"'"'risk_class'"'"']}" for t in json.load(sys.stdin)))'
curl -fsS "$BASE_URL/governance/approvers" | python3 -c \
  'import json,sys; print("registered_approvers:", ", ".join(f"{a['"'"'approver_id'"'"']}:{a['"'"'role'"'"']}" for a in json.load(sys.stdin)))'
curl -fsS "$BASE_URL/governance/paths/$path_id" | python3 -c \
  'import json,sys; path=json.load(sys.stdin); print("path_outcomes:", ", ".join(a["execution_outcome"] for a in path["actions"]))'
curl -fsS "$BASE_URL/governance/approvals/$approval_id" | python3 -c \
  'import json,sys; detail=json.load(sys.stdin); print("approval_receipts:", ", ".join(r["status"] for r in detail["execution_receipts"]))'

print_step "9. Audit log records authorization decisions, receipts, paths, and outcomes"
curl -fsS "$BASE_URL/audit/recent?limit=100" > "$audit_response"
python3 - \
  "$audit_response" \
  "$safe_response" \
  "$risky_response" \
  "$denied_response" \
  "$invalid_response" \
  "$escalated_response" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as file:
    events = json.load(file)

demo_run_ids = set()
for response_path in sys.argv[2:]:
    with open(response_path, "r", encoding="utf-8") as file:
        demo_run_ids.add(json.load(file)["run_id"])

for event in [item for item in events if item.get("run_id") in demo_run_ids]:
    run_id = event.get("run_id", "")
    approval_id = event.get("approval_id", "")
    decision_id = event.get("policy_decision_id", "")
    path_action_id = event.get("path_action_id", "")
    approver_id = event.get("approver_id", "")
    print(
        f"{event['event_type']:<32} run={run_id} path_action={path_action_id} "
        f"approval={approval_id} approver={approver_id} decision={decision_id}"
    )
PY

print_step "10. Versioned evaluation proof point"
.venv/bin/python -m evals.run_policy_evals

print_step "11. Async proof point"
printf "The runtime uses asyncio.gather() in app/agent/runtime.py to run retrieval and planning concurrently.\n"
