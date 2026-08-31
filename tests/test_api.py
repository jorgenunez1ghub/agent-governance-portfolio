import asyncio

import pytest
from fastapi.testclient import TestClient

from app.audit.logger import audit_logger
from app.config import settings
from app.governance.approvals import approval_store
from app.governance.path import execution_path_store
from app.main import app


client = TestClient(app)
APPROVER_AUTH = {"Authorization": f"Bearer {settings.demo_approver_token}"}
LIMITED_AUTH = {"Authorization": f"Bearer {settings.limited_approver_token}"}


@pytest.fixture(autouse=True)
def isolated_state(tmp_path):
    original_audit_path = audit_logger.path
    audit_logger.configure_path(tmp_path / "audit_log.jsonl")
    approval_store.reset()
    execution_path_store.reset()
    yield
    approval_store.reset()
    execution_path_store.reset()
    audit_logger.configure_path(original_audit_path)


def test_governance_agents_are_inspectable():
    response = client.get("/governance/agents")

    assert response.status_code == 200
    agents = {agent["agent_id"]: agent for agent in response.json()}
    assert agents["demo-agent"]["autonomy_level"] == "supervised"
    assert agents["read-only-agent"]["allowed_tools"] == ["lookup_policy"]


def test_governance_tool_provenance_is_inspectable():
    response = client.get("/governance/tools")

    assert response.status_code == 200
    tools = {tool["name"]: tool for tool in response.json()}
    assert tools["send_external_message"]["risk_class"] == "external_write"
    assert tools["send_external_message"]["provenance_status"] == "trusted"
    assert tools["send_external_message"]["version"] == "1.0.0"


def test_execution_path_is_backend_managed_and_inspectable():
    run_response = client.post(
        "/agent/run",
        json={
            "user_id": "demo-user",
            "agent_id": "demo-agent",
            "task": "Create an internal action item to review project risk",
            "risk_level": "medium",
        },
    )

    assert run_response.status_code == 200
    run_body = run_response.json()

    path_response = client.get(f"/governance/paths/{run_body['path_id']}")

    assert path_response.status_code == 200
    path = path_response.json()
    assert path["agent_id"] == "demo-agent"
    assert len(path["actions"]) == 1
    assert path["actions"][0]["action_id"] == run_body["path_action_id"]


def test_execution_path_cannot_be_continued_by_a_different_agent():
    first_response = client.post(
        "/agent/run",
        json={
            "user_id": "demo-user",
            "agent_id": "demo-agent",
            "task": "Look up the governance policy",
            "risk_level": "low",
        },
    )

    mismatch_response = client.post(
        "/agent/run",
        json={
            "user_id": "demo-user",
            "agent_id": "read-only-agent",
            "path_id": first_response.json()["path_id"],
            "task": "Look up the governance policy",
            "risk_level": "low",
        },
    )

    assert mismatch_response.status_code == 409
    assert "belongs to agent demo-agent" in mismatch_response.json()["detail"]


def test_approval_idempotency_header_replays_receipt_and_detail_is_inspectable():
    run_response = client.post(
        "/agent/run",
        json={
            "user_id": "demo-user",
            "agent_id": "demo-agent",
            "task": "Send an external message about project risk",
            "risk_level": "high",
        },
    )
    approval_id = run_response.json()["approval_id"]

    first = client.post(
        f"/approvals/{approval_id}/approve",
        headers={**APPROVER_AUTH, "Idempotency-Key": "api-retry-key"},
    )
    replay = client.post(
        f"/approvals/{approval_id}/approve",
        headers={**APPROVER_AUTH, "Idempotency-Key": "api-retry-key"},
    )
    detail = client.get(f"/governance/approvals/{approval_id}")

    assert first.status_code == replay.status_code == detail.status_code == 200
    assert replay.json()["idempotent_replay"] is True
    assert (
        replay.json()["execution_receipt"]["receipt_id"]
        == first.json()["execution_receipt"]["receipt_id"]
    )
    assert detail.json()["approval"]["status"] == "executed"
    assert len(detail.json()["execution_receipts"]) == 1


def test_expired_approval_returns_gone(monkeypatch):
    monkeypatch.setattr(settings, "approval_ttl_seconds", 0)
    run_response = client.post(
        "/agent/run",
        json={
            "user_id": "demo-user",
            "agent_id": "demo-agent",
            "task": "Send an external message about project risk",
            "risk_level": "high",
        },
    )
    approval_id = run_response.json()["approval_id"]

    approval_response = client.post(
        f"/approvals/{approval_id}/approve",
        headers={**APPROVER_AUTH, "Idempotency-Key": "expired-api-key"},
    )

    assert approval_response.status_code == 410
    assert "expired" in approval_response.json()["detail"]


def test_approver_identities_are_inspectable_without_credentials():
    response = client.get("/governance/approvers")

    assert response.status_code == 200
    approvers = {item["approver_id"]: item for item in response.json()}
    assert approvers["demo-approver"]["role"] == "risk_reviewer"
    assert "send_external_message" in approvers["demo-approver"]["allowed_tools"]
    assert all("token" not in key for item in approvers.values() for key in item)


def test_missing_or_invalid_approver_credential_returns_unauthorized():
    run_response = client.post(
        "/agent/run",
        json={
            "user_id": "demo-user",
            "agent_id": "demo-agent",
            "task": "Send an external message about project risk",
            "risk_level": "high",
        },
    )
    approval_id = run_response.json()["approval_id"]

    missing = client.post(f"/approvals/{approval_id}/approve")
    invalid = client.post(
        f"/approvals/{approval_id}/approve",
        headers={"Authorization": "Bearer invalid-approver-token"},
    )

    assert missing.status_code == invalid.status_code == 401
    assert missing.headers["www-authenticate"] == "Bearer"
    events = asyncio.run(audit_logger.recent_events(limit=20))
    failures = [
        event for event in events if event["event_type"] == "approval_authentication_failed"
    ]
    assert len(failures) == 2
    assert all(event["details"]["credential_exposed"] is False for event in failures)


def test_self_approval_and_out_of_scope_approval_return_forbidden():
    self_requested = client.post(
        "/agent/run",
        json={
            "user_id": "demo-approver",
            "agent_id": "demo-agent",
            "task": "Send an external message about project risk",
            "risk_level": "high",
        },
    ).json()
    external = client.post(
        "/agent/run",
        json={
            "user_id": "demo-user",
            "agent_id": "demo-agent",
            "task": "Send an external message about project risk",
            "risk_level": "high",
        },
    ).json()

    self_denied = client.post(
        f"/approvals/{self_requested['approval_id']}/approve",
        headers=APPROVER_AUTH,
    )
    scoped_denied = client.post(
        f"/approvals/{external['approval_id']}/approve",
        headers=LIMITED_AUTH,
    )

    assert self_denied.status_code == scoped_denied.status_code == 403
    assert self_denied.json()["detail"]["reason_codes"] == [
        "requester_cannot_approve_own_request"
    ]
    assert scoped_denied.json()["detail"]["reason_codes"] == [
        "tool_outside_approver_scope",
        "risk_outside_approver_scope",
    ]
