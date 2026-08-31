import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict

from app.governance.identity import AgentIdentity, AutonomyLevel
from app.governance.path import ExecutionPathContext
from app.tools.registry import ToolDefinition, ToolProvenanceStatus, ToolRiskClass

POLICY_VERSION = "agent-governance-policy-2.1"
RiskLevel = Literal["low", "medium", "high"]


class PolicyOutcome(str, Enum):
    allow = "allow"
    require_approval = "require_approval"
    deny = "deny"


class PolicyDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_id: str
    policy_version: str
    outcome: PolicyOutcome
    agent_id: str
    tool_name: str
    tool_version: str
    request_risk_level: RiskLevel
    matched_rules: List[str]
    reason_codes: List[str]
    explanation: str
    evaluated_at: str
    execution_path_id: Optional[str] = None
    evaluated_path_action_count: int = 0


def evaluate_policy(
    *,
    agent_id: str,
    agent: Optional[AgentIdentity],
    tool: ToolDefinition,
    request_risk_level: RiskLevel,
    execution_path: Optional[ExecutionPathContext] = None,
) -> PolicyDecision:
    matched_rules: List[str] = []

    if agent is None:
        return _decision(
            outcome=PolicyOutcome.deny,
            agent_id=agent_id,
            tool=tool,
            request_risk_level=request_risk_level,
            matched_rules=["agent_must_be_registered"],
            reason_codes=["agent_not_registered"],
            explanation=f"Agent {agent_id} is not registered and cannot execute tools.",
            execution_path=execution_path,
        )

    matched_rules.append("agent_must_be_registered")

    if tool.provenance_status != ToolProvenanceStatus.trusted:
        return _decision(
            outcome=PolicyOutcome.deny,
            agent_id=agent_id,
            tool=tool,
            request_risk_level=request_risk_level,
            matched_rules=matched_rules + ["tool_provenance_must_be_trusted"],
            reason_codes=["tool_provenance_not_trusted"],
            explanation=(
                f"{tool.name} version {tool.version} has provenance status "
                f"{tool.provenance_status.value} and cannot execute."
            ),
            execution_path=execution_path,
        )

    matched_rules.append("tool_provenance_must_be_trusted")

    if tool.name not in agent.allowed_tools:
        return _decision(
            outcome=PolicyOutcome.deny,
            agent_id=agent_id,
            tool=tool,
            request_risk_level=request_risk_level,
            matched_rules=matched_rules + ["agent_tool_scope"],
            reason_codes=["tool_outside_agent_scope"],
            explanation=f"{tool.name} is outside the registered tool scope for agent {agent_id}.",
            execution_path=execution_path,
        )

    matched_rules.append("agent_tool_scope")

    if agent.autonomy_level == AutonomyLevel.read_only and tool.risk_class != ToolRiskClass.read_only:
        return _decision(
            outcome=PolicyOutcome.deny,
            agent_id=agent_id,
            tool=tool,
            request_risk_level=request_risk_level,
            matched_rules=matched_rules + ["read_only_agents_cannot_write"],
            reason_codes=["agent_autonomy_insufficient"],
            explanation=f"Agent {agent_id} is read-only and cannot use {tool.risk_class.value} tools.",
            execution_path=execution_path,
        )

    matched_rules.append("agent_autonomy_allows_tool_risk")

    if (
        execution_path is not None
        and execution_path.has_adverse_outcome
        and tool.risk_class != ToolRiskClass.read_only
    ):
        return _decision(
            outcome=PolicyOutcome.require_approval,
            agent_id=agent_id,
            tool=tool,
            request_risk_level=request_risk_level,
            matched_rules=matched_rules + ["adverse_path_requires_approval"],
            reason_codes=["prior_adverse_outcome_requires_human"],
            explanation=(
                f"Execution path {execution_path.path_id} contains a denied, failed, or rejected "
                "action. The next write requires human review."
            ),
            execution_path=execution_path,
        )

    if tool.risk_class == ToolRiskClass.external_write:
        return _decision(
            outcome=PolicyOutcome.require_approval,
            agent_id=agent_id,
            tool=tool,
            request_risk_level=request_risk_level,
            matched_rules=matched_rules + ["external_writes_require_approval"],
            reason_codes=["external_write_requires_human"],
            explanation=f"{tool.name} can affect people or systems outside this app and requires human approval.",
            execution_path=execution_path,
        )

    if request_risk_level == "high" and tool.risk_class != ToolRiskClass.read_only:
        return _decision(
            outcome=PolicyOutcome.require_approval,
            agent_id=agent_id,
            tool=tool,
            request_risk_level=request_risk_level,
            matched_rules=matched_rules + ["high_risk_writes_require_approval"],
            reason_codes=["high_risk_request_requires_human"],
            explanation="High-risk write requests require human approval.",
            execution_path=execution_path,
        )

    return _decision(
        outcome=PolicyOutcome.allow,
        agent_id=agent_id,
        tool=tool,
        request_risk_level=request_risk_level,
        matched_rules=matched_rules + ["proportional_execution"],
        reason_codes=["trusted_tool_within_agent_scope"],
        explanation=f"{tool.name} is trusted, within agent scope, and allowed for automatic execution.",
        execution_path=execution_path,
    )


def requires_human_approval(tool: ToolDefinition) -> bool:
    """Compatibility helper for the Milestone 1.5 policy API."""
    return tool.approval_required


def approval_reason(tool: ToolDefinition) -> str:
    """Compatibility helper for the Milestone 1.5 policy API."""
    if tool.approval_required:
        return f"{tool.name} requires approval because it can affect systems or people outside this app."
    return f"{tool.name} is approved for automatic execution under the current policy."


def _decision(
    *,
    outcome: PolicyOutcome,
    agent_id: str,
    tool: ToolDefinition,
    request_risk_level: RiskLevel,
    matched_rules: List[str],
    reason_codes: List[str],
    explanation: str,
    execution_path: Optional[ExecutionPathContext] = None,
) -> PolicyDecision:
    return PolicyDecision(
        decision_id=str(uuid.uuid4()),
        policy_version=POLICY_VERSION,
        outcome=outcome,
        agent_id=agent_id,
        tool_name=tool.name,
        tool_version=tool.version,
        request_risk_level=request_risk_level,
        matched_rules=matched_rules,
        reason_codes=reason_codes,
        explanation=explanation,
        evaluated_at=_utc_now(),
        execution_path_id=execution_path.path_id if execution_path else None,
        evaluated_path_action_count=execution_path.action_count if execution_path else 0,
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
