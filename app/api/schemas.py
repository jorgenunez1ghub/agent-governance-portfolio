from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.governance.approvals import ApprovalRecord, ExecutionReceipt
from app.governance.path import ExecutionPath
from app.governance.policy import PolicyDecision


class AgentRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str = Field(min_length=1, max_length=80)
    agent_id: str = Field(default="demo-agent", min_length=1, max_length=80)
    task: str = Field(min_length=1, max_length=2000)
    risk_level: Literal["low", "medium", "high"] = "medium"
    path_id: Optional[str] = Field(default=None, min_length=1, max_length=80)


class AgentPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str
    arguments: Dict[str, Any]
    reason: str


class ToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str
    arguments: Dict[str, Any]


class ToolMetadataResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    version: str
    owner: str
    source: str
    risk_class: str
    provenance_status: str


class AgentRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["completed", "approval_required", "denied", "failed"]
    run_id: str
    agent_id: str
    path_id: str
    path_action_id: str
    plan: Optional[AgentPlan] = None
    policy_decision: Optional[PolicyDecision] = None
    tool_result: Optional[Dict[str, Any]] = None
    approval_required: bool
    approval_id: Optional[str] = None
    approval_expires_at: Optional[str] = None
    proposed_action: Optional[ToolCall] = None
    reason: Optional[str] = None
    error: Optional[str] = None


class ApprovalActionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["executed", "rejected", "execution_failed"]
    run_id: str
    approval_id: str
    agent_id: str
    policy_decision_id: str
    approver_id: str
    approval_authorization_decision_id: str
    path_id: str
    path_action_id: str
    execution_receipt: Optional[ExecutionReceipt] = None
    idempotent_replay: bool = False
    retryable: Optional[bool] = None
    tool_result: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None


class AuditEventResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timestamp: str
    event_type: str
    actor: str
    details: Dict[str, Any]
    run_id: Optional[str] = None
    approval_id: Optional[str] = None
    agent_id: Optional[str] = None
    policy_decision_id: Optional[str] = None
    tool_name: Optional[str] = None
    tool_version: Optional[str] = None
    path_id: Optional[str] = None
    path_action_id: Optional[str] = None
    execution_receipt_id: Optional[str] = None
    approver_id: Optional[str] = None
    approval_authorization_decision_id: Optional[str] = None


class AuditRecentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    events: List[AuditEventResponse]


class ExecutionPathResponse(ExecutionPath):
    pass


class ApprovalDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approval: ApprovalRecord
    execution_receipts: List[ExecutionReceipt]
