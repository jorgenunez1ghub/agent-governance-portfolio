from dataclasses import replace

from app.governance.identity import AgentIdentity, AutonomyLevel, agent_registry
from app.governance.path import ExecutionPathContext, PathActionOutcome, PathActionRecord
from app.governance.policy import PolicyOutcome, evaluate_policy, requires_human_approval
from app.tools.registry import ToolProvenanceStatus, tool_registry


def test_policy_allows_trusted_tool_within_agent_scope():
    tool = tool_registry.get_tool("create_action_item")
    decision = evaluate_policy(
        agent_id="demo-agent",
        agent=agent_registry.find("demo-agent"),
        tool=tool,
        request_risk_level="medium",
    )

    assert decision.outcome == PolicyOutcome.allow
    assert decision.policy_version == "agent-governance-policy-2.1"
    assert decision.reason_codes == ["trusted_tool_within_agent_scope"]
    assert "proportional_execution" in decision.matched_rules


def test_policy_requires_approval_for_external_write():
    tool = tool_registry.get_tool("send_external_message")
    decision = evaluate_policy(
        agent_id="demo-agent",
        agent=agent_registry.find("demo-agent"),
        tool=tool,
        request_risk_level="high",
    )

    assert decision.outcome == PolicyOutcome.require_approval
    assert decision.reason_codes == ["external_write_requires_human"]
    assert "external_writes_require_approval" in decision.matched_rules


def test_policy_denies_unregistered_agent():
    tool = tool_registry.get_tool("lookup_policy")
    decision = evaluate_policy(
        agent_id="missing-agent",
        agent=None,
        tool=tool,
        request_risk_level="low",
    )

    assert decision.outcome == PolicyOutcome.deny
    assert decision.reason_codes == ["agent_not_registered"]


def test_policy_denies_tool_outside_agent_scope():
    tool = tool_registry.get_tool("create_action_item")
    decision = evaluate_policy(
        agent_id="read-only-agent",
        agent=agent_registry.find("read-only-agent"),
        tool=tool,
        request_risk_level="medium",
    )

    assert decision.outcome == PolicyOutcome.deny
    assert decision.reason_codes == ["tool_outside_agent_scope"]


def test_policy_denies_untrusted_tool_provenance():
    tool = replace(
        tool_registry.get_tool("lookup_policy"),
        provenance_status=ToolProvenanceStatus.unverified,
    )
    decision = evaluate_policy(
        agent_id="demo-agent",
        agent=agent_registry.find("demo-agent"),
        tool=tool,
        request_risk_level="low",
    )

    assert decision.outcome == PolicyOutcome.deny
    assert decision.reason_codes == ["tool_provenance_not_trusted"]


def test_policy_denies_write_for_read_only_autonomy():
    agent = AgentIdentity(
        agent_id="limited-agent",
        owner="test",
        purpose="Exercise the autonomy rule.",
        autonomy_level=AutonomyLevel.read_only,
        allowed_tools=("create_action_item",),
    )
    decision = evaluate_policy(
        agent_id=agent.agent_id,
        agent=agent,
        tool=tool_registry.get_tool("create_action_item"),
        request_risk_level="medium",
    )

    assert decision.outcome == PolicyOutcome.deny
    assert decision.reason_codes == ["agent_autonomy_insufficient"]


def test_policy_approval_check():
    assert requires_human_approval(tool_registry.get_tool("send_external_message")) is True
    assert requires_human_approval(tool_registry.get_tool("create_action_item")) is False
    assert requires_human_approval(tool_registry.get_tool("lookup_policy")) is False


def test_policy_escalates_write_after_adverse_path_outcome():
    prior_action = PathActionRecord(
        action_id="action-1",
        run_id="run-1",
        tool_name="send_external_message",
        tool_version="1.0.0",
        tool_risk_class="external_write",
        request_risk_level="high",
        execution_outcome=PathActionOutcome.validation_failed,
        recorded_at="2026-07-29T00:00:00Z",
        updated_at="2026-07-29T00:00:00Z",
    )
    path = ExecutionPathContext(
        path_id="path-1",
        agent_id="demo-agent",
        actions=(prior_action,),
    )

    decision = evaluate_policy(
        agent_id="demo-agent",
        agent=agent_registry.find("demo-agent"),
        tool=tool_registry.get_tool("create_action_item"),
        request_risk_level="medium",
        execution_path=path,
    )

    assert decision.outcome == PolicyOutcome.require_approval
    assert decision.reason_codes == ["prior_adverse_outcome_requires_human"]
    assert decision.execution_path_id == "path-1"
    assert decision.evaluated_path_action_count == 1


def test_policy_keeps_read_only_action_available_after_adverse_outcome():
    prior_action = PathActionRecord(
        action_id="action-1",
        run_id="run-1",
        tool_name="send_external_message",
        tool_version="1.0.0",
        tool_risk_class="external_write",
        request_risk_level="high",
        execution_outcome=PathActionOutcome.denied,
        recorded_at="2026-07-29T00:00:00Z",
        updated_at="2026-07-29T00:00:00Z",
    )
    path = ExecutionPathContext(
        path_id="path-1",
        agent_id="demo-agent",
        actions=(prior_action,),
    )

    decision = evaluate_policy(
        agent_id="demo-agent",
        agent=agent_registry.find("demo-agent"),
        tool=tool_registry.get_tool("lookup_policy"),
        request_risk_level="low",
        execution_path=path,
    )

    assert decision.outcome == PolicyOutcome.allow
    assert decision.reason_codes == ["trusted_tool_within_agent_scope"]
    assert decision.evaluated_path_action_count == 1
