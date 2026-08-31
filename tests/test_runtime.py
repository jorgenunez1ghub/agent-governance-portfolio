import asyncio
from dataclasses import replace

import pytest

from app.agent.runtime import approve_approval, run_agent
from app.api.schemas import AgentRunRequest
from app.audit.logger import audit_logger
from app.config import settings
from app.governance.approvals import (
    ApprovalExpiredError,
    ApprovalRetryNotAllowedError,
    ApprovalState,
    ApprovalTransitionError,
    ExecutionReceiptStatus,
    approval_store,
)
from app.governance.approvers import (
    ApprovalAuthorizationError,
    approver_registry,
)
from app.governance.path import PathActionOutcome, execution_path_store
from app.governance.policy import PolicyOutcome
from app.tools.errors import RetryableToolExecutionError, TerminalToolExecutionError
from app.tools.registry import tool_registry


DEMO_APPROVER = approver_registry.get("demo-approver")
LIMITED_APPROVER = approver_registry.get("limited-approver")


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


def test_safe_tool_execution_writes_audit_events():
    response = asyncio.run(
        run_agent(
            AgentRunRequest(
                user_id="demo-user",
                task="Create an internal action item to review project risk",
                risk_level="medium",
            )
        )
    )

    assert response.status == "completed"
    assert response.agent_id == "demo-agent"
    assert response.path_id
    assert response.path_action_id
    assert response.approval_required is False
    assert response.policy_decision is not None
    assert response.policy_decision.outcome == PolicyOutcome.allow
    assert response.tool_result is not None
    assert response.tool_result["status"] == "created"

    events = asyncio.run(audit_logger.recent_events(limit=20))
    event_types = [event["event_type"] for event in events]

    assert "run_started" in event_types
    assert "context_retrieved" in event_types
    assert "plan_created" in event_types
    assert "tool_selected" in event_types
    assert "tool_validation_passed" in event_types
    assert "policy_evaluated" in event_types
    assert "tool_executed" in event_types
    assert "run_completed" in event_types

    policy_event = next(event for event in events if event["event_type"] == "policy_evaluated")
    assert policy_event["agent_id"] == "demo-agent"
    assert policy_event["policy_decision_id"] == response.policy_decision.decision_id
    assert policy_event["tool_version"] == "1.0.0"
    assert policy_event["path_id"] == response.path_id
    assert policy_event["path_action_id"] == response.path_action_id

    path = execution_path_store.get(response.path_id)
    assert len(path.actions) == 1
    assert path.actions[0].execution_outcome == PathActionOutcome.executed


def test_approval_required_tool_flow_executes_after_approval():
    response = asyncio.run(
        run_agent(
            AgentRunRequest(
                user_id="demo-user",
                task="Send an external message about the project risk",
                risk_level="high",
            )
        )
    )

    assert response.status == "approval_required"
    assert response.approval_required is True
    assert response.policy_decision is not None
    assert response.policy_decision.outcome == PolicyOutcome.require_approval
    assert response.approval_id is not None
    assert response.proposed_action is not None
    assert response.proposed_action.tool_name == "send_external_message"

    pending = approval_store.get(response.approval_id)
    assert pending.status == ApprovalState.pending
    assert pending.agent_id == "demo-agent"
    assert pending.policy_decision_id == response.policy_decision.decision_id
    assert pending.tool_version == "1.0.0"

    approval_response = asyncio.run(approve_approval(response.approval_id, approver=DEMO_APPROVER))

    assert approval_response.status == "executed"
    assert approval_response.policy_decision_id == response.policy_decision.decision_id
    assert approval_response.path_id == response.path_id
    assert approval_response.path_action_id == response.path_action_id
    assert approval_response.tool_result is not None
    assert approval_response.tool_result["status"] == "simulated_sent"
    executed = approval_store.get(response.approval_id)
    assert executed.status == ApprovalState.executed
    assert executed.authorized_approver_id == "demo-approver"
    assert approval_response.approver_id == "demo-approver"
    assert approval_response.execution_receipt is not None
    assert approval_response.execution_receipt.approver_id == "demo-approver"

    events = asyncio.run(audit_logger.recent_events(limit=30))
    event_types = [event["event_type"] for event in events]
    assert "approval_required" in event_types
    assert "approval_approved" in event_types
    assert "tool_executed" in event_types
    assert "run_completed" in event_types
    assert "path_action_updated" in event_types


def test_out_of_scope_tool_is_denied_with_explanation():
    response = asyncio.run(
        run_agent(
            AgentRunRequest(
                user_id="demo-user",
                agent_id="read-only-agent",
                task="Create an internal action item to review project risk",
                risk_level="medium",
            )
        )
    )

    assert response.status == "denied"
    assert response.approval_required is False
    assert response.tool_result is None
    assert response.policy_decision is not None
    assert response.policy_decision.outcome == PolicyOutcome.deny
    assert response.policy_decision.reason_codes == ["tool_outside_agent_scope"]

    events = asyncio.run(audit_logger.recent_events(limit=20))
    event_types = [event["event_type"] for event in events]
    assert "policy_evaluated" in event_types
    assert "run_denied" in event_types
    assert "tool_executed" not in event_types


def test_unregistered_agent_is_denied():
    response = asyncio.run(
        run_agent(
            AgentRunRequest(
                user_id="demo-user",
                agent_id="unknown-agent",
                task="Look up the governance policy",
                risk_level="low",
            )
        )
    )

    assert response.status == "denied"
    assert response.policy_decision is not None
    assert response.policy_decision.reason_codes == ["agent_not_registered"]


def test_approval_is_bound_to_the_evaluated_tool_version(monkeypatch):
    response = asyncio.run(
        run_agent(
            AgentRunRequest(
                user_id="demo-user",
                task="Send an external message about the project risk",
                risk_level="high",
            )
        )
    )
    assert response.approval_id is not None

    original_tool = tool_registry.get_tool("send_external_message")
    monkeypatch.setitem(
        tool_registry._tools,
        "send_external_message",
        replace(original_tool, version="2.0.0"),
    )

    with pytest.raises(ApprovalTransitionError, match="bound to send_external_message version 1.0.0"):
        asyncio.run(approve_approval(response.approval_id, approver=DEMO_APPROVER))

    assert approval_store.get(response.approval_id).status == ApprovalState.pending


def test_invalid_tool_input_fails_before_execution():
    response = asyncio.run(
        run_agent(
            AgentRunRequest(
                user_id="demo-user",
                task="Send invalid external message about project risk",
                risk_level="high",
            )
        )
    )

    assert response.status == "failed"
    assert response.error == "Tool input validation failed."
    assert response.approval_required is False

    events = asyncio.run(audit_logger.recent_events(limit=20))
    event_types = [event["event_type"] for event in events]
    assert "tool_validation_failed" in event_types
    assert "run_failed" in event_types
    assert "policy_evaluated" not in event_types
    assert "tool_executed" not in event_types

    path = execution_path_store.get(response.path_id)
    assert path.actions[0].execution_outcome == PathActionOutcome.validation_failed


def test_failed_action_escalates_next_write_on_same_execution_path():
    failed_response = asyncio.run(
        run_agent(
            AgentRunRequest(
                user_id="demo-user",
                task="Send invalid external message about project risk",
                risk_level="high",
            )
        )
    )

    escalated_response = asyncio.run(
        run_agent(
            AgentRunRequest(
                user_id="demo-user",
                path_id=failed_response.path_id,
                task="Create an internal action item to review project risk",
                risk_level="medium",
            )
        )
    )

    assert escalated_response.status == "approval_required"
    assert escalated_response.policy_decision is not None
    assert escalated_response.policy_decision.reason_codes == [
        "prior_adverse_outcome_requires_human"
    ]
    assert escalated_response.policy_decision.execution_path_id == failed_response.path_id
    assert escalated_response.policy_decision.evaluated_path_action_count == 1

    path = execution_path_store.get(failed_response.path_id)
    assert [action.execution_outcome for action in path.actions] == [
        PathActionOutcome.validation_failed,
        PathActionOutcome.approval_required,
    ]


def test_duplicate_approval_replays_receipt_without_reexecuting_tool(monkeypatch):
    original_tool = tool_registry.get_tool("send_external_message")
    execution_count = 0

    async def counting_handler(input_data):
        nonlocal execution_count
        execution_count += 1
        return await original_tool.handler(input_data)

    monkeypatch.setitem(
        tool_registry._tools,
        original_tool.name,
        replace(original_tool, handler=counting_handler),
    )
    response = asyncio.run(
        run_agent(
            AgentRunRequest(
                user_id="demo-user",
                task="Send an external message about project risk",
                risk_level="high",
            )
        )
    )
    assert response.approval_id is not None

    first = asyncio.run(
        approve_approval(response.approval_id, approver=DEMO_APPROVER, idempotency_key="stable-key")
    )
    current_tool = tool_registry.get_tool("send_external_message")
    monkeypatch.setitem(
        tool_registry._tools,
        current_tool.name,
        replace(current_tool, version="2.0.0"),
    )
    replay = asyncio.run(
        approve_approval(response.approval_id, approver=DEMO_APPROVER, idempotency_key="stable-key")
    )

    assert first.status == replay.status == "executed"
    assert first.execution_receipt is not None
    assert replay.execution_receipt is not None
    assert replay.execution_receipt.receipt_id == first.execution_receipt.receipt_id
    assert replay.idempotent_replay is True
    assert execution_count == 1
    assert len(approval_store.list_receipts(response.approval_id)) == 1

    events = asyncio.run(audit_logger.recent_events(limit=50))
    event_types = [event["event_type"] for event in events]
    assert event_types.count("tool_executed") == 1
    assert "approval_execution_replayed" in event_types
    replay_event = next(
        event for event in events if event["event_type"] == "approval_execution_replayed"
    )
    assert replay_event["tool_version"] == "1.0.0"


def test_retryable_failure_replays_then_succeeds_with_new_key(monkeypatch):
    original_tool = tool_registry.get_tool("send_external_message")
    execution_count = 0

    async def flaky_handler(input_data):
        nonlocal execution_count
        execution_count += 1
        if execution_count == 1:
            raise RetryableToolExecutionError(
                code="mock_transient_failure",
                message="Temporary mock provider failure.",
            )
        return await original_tool.handler(input_data)

    monkeypatch.setitem(
        tool_registry._tools,
        original_tool.name,
        replace(original_tool, handler=flaky_handler),
    )
    response = asyncio.run(
        run_agent(
            AgentRunRequest(
                user_id="demo-user",
                task="Send an external message about project risk",
                risk_level="high",
            )
        )
    )
    assert response.approval_id is not None

    failed = asyncio.run(
        approve_approval(response.approval_id, approver=DEMO_APPROVER, idempotency_key="attempt-1")
    )
    failed_replay = asyncio.run(
        approve_approval(response.approval_id, approver=DEMO_APPROVER, idempotency_key="attempt-1")
    )
    succeeded = asyncio.run(
        approve_approval(response.approval_id, approver=DEMO_APPROVER, idempotency_key="attempt-2")
    )

    assert failed.status == "execution_failed"
    assert failed.retryable is True
    assert failed.execution_receipt is not None
    assert failed.execution_receipt.status == ExecutionReceiptStatus.failed
    assert failed_replay.idempotent_replay is True
    assert failed_replay.execution_receipt == failed.execution_receipt
    assert succeeded.status == "executed"
    assert succeeded.execution_receipt is not None
    assert succeeded.execution_receipt.attempt_number == 2
    assert execution_count == 2
    assert [
        receipt.status for receipt in approval_store.list_receipts(response.approval_id)
    ] == [
        ExecutionReceiptStatus.failed,
        ExecutionReceiptStatus.succeeded,
    ]


def test_terminal_execution_failure_disallows_new_retry_key(monkeypatch):
    original_tool = tool_registry.get_tool("send_external_message")
    execution_count = 0

    async def terminal_handler(input_data):
        nonlocal execution_count
        execution_count += 1
        raise TerminalToolExecutionError(
            code="mock_terminal_failure",
            message="Terminal mock provider failure.",
        )

    monkeypatch.setitem(
        tool_registry._tools,
        original_tool.name,
        replace(original_tool, handler=terminal_handler),
    )
    response = asyncio.run(
        run_agent(
            AgentRunRequest(
                user_id="demo-user",
                task="Send an external message about project risk",
                risk_level="high",
            )
        )
    )
    assert response.approval_id is not None

    failed = asyncio.run(
        approve_approval(response.approval_id, approver=DEMO_APPROVER, idempotency_key="attempt-1")
    )
    replay = asyncio.run(
        approve_approval(response.approval_id, approver=DEMO_APPROVER, idempotency_key="attempt-1")
    )

    assert failed.status == "execution_failed"
    assert failed.retryable is False
    assert replay.idempotent_replay is True
    with pytest.raises(ApprovalRetryNotAllowedError):
        asyncio.run(
            approve_approval(response.approval_id, approver=DEMO_APPROVER, idempotency_key="attempt-2")
        )
    assert execution_count == 1


def test_expired_approval_fails_closed_and_updates_path(monkeypatch):
    monkeypatch.setattr(settings, "approval_ttl_seconds", 0)
    response = asyncio.run(
        run_agent(
            AgentRunRequest(
                user_id="demo-user",
                task="Send an external message about project risk",
                risk_level="high",
            )
        )
    )
    assert response.approval_id is not None

    with pytest.raises(ApprovalExpiredError):
        asyncio.run(
            approve_approval(response.approval_id, approver=DEMO_APPROVER, idempotency_key="expired-key")
        )

    approval = approval_store.get(response.approval_id)
    assert approval.status == ApprovalState.expired
    assert approval_store.list_receipts(response.approval_id) == []
    path = execution_path_store.get(response.path_id)
    assert path.actions[0].execution_outcome == PathActionOutcome.expired

    events = asyncio.run(audit_logger.recent_events(limit=50))
    event_types = [event["event_type"] for event in events]
    assert "approval_expired" in event_types
    assert "tool_executed" not in event_types


def test_requester_cannot_approve_own_request():
    response = asyncio.run(
        run_agent(
            AgentRunRequest(
                user_id="demo-approver",
                task="Send an external message about project risk",
                risk_level="high",
            )
        )
    )
    assert response.approval_id is not None

    with pytest.raises(ApprovalAuthorizationError) as error:
        asyncio.run(
            approve_approval(
                response.approval_id,
                approver=DEMO_APPROVER,
                idempotency_key="self-approval",
            )
        )

    assert error.value.decision.reason_codes == (
        "requester_cannot_approve_own_request",
    )
    approval = approval_store.get(response.approval_id)
    assert approval.status == ApprovalState.pending
    assert approval_store.list_receipts(response.approval_id) == []
    events = asyncio.run(audit_logger.recent_events(limit=50))
    denied = next(
        event for event in events if event["event_type"] == "approval_authorization_denied"
    )
    assert denied["approver_id"] == "demo-approver"
    assert denied["details"]["requester_identity_verified"] is False
    assert "approval_execution_started" not in {event["event_type"] for event in events}


def test_out_of_scope_approver_is_denied_without_execution():
    response = asyncio.run(
        run_agent(
            AgentRunRequest(
                user_id="demo-user",
                task="Send an external message about project risk",
                risk_level="high",
            )
        )
    )
    assert response.approval_id is not None

    with pytest.raises(ApprovalAuthorizationError) as error:
        asyncio.run(
            approve_approval(
                response.approval_id,
                approver=LIMITED_APPROVER,
                idempotency_key="out-of-scope",
            )
        )

    assert error.value.decision.reason_codes == (
        "tool_outside_approver_scope",
        "risk_outside_approver_scope",
    )
    assert approval_store.get(response.approval_id).status == ApprovalState.pending
    assert approval_store.list_receipts(response.approval_id) == []
