import hashlib
import uuid
from enum import Enum
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field

from app.config import settings


class ApproverRole(str, Enum):
    risk_reviewer = "risk_reviewer"
    governance_admin = "governance_admin"
    audit_observer = "audit_observer"


class ApprovalAction(str, Enum):
    approve = "approve"
    reject = "reject"


class ApproverIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approver_id: str = Field(min_length=1, max_length=80)
    display_name: str = Field(min_length=1, max_length=120)
    role: ApproverRole
    allowed_tools: Tuple[str, ...]
    allowed_risk_levels: Tuple[str, ...]
    permitted_actions: Tuple[ApprovalAction, ...]
    active: bool = True


class ApprovalAuthorizationDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_id: str
    approver_id: str
    action: ApprovalAction
    allowed: bool
    reason_codes: Tuple[str, ...]
    explanation: str


class ApproverAuthenticationError(Exception):
    pass


class ApprovalAuthorizationError(Exception):
    def __init__(self, decision: ApprovalAuthorizationDecision) -> None:
        self.decision = decision
        super().__init__(decision.explanation)


class ApproverRegistry:
    def __init__(self) -> None:
        self._approvers: Dict[str, ApproverIdentity] = {}
        self._approver_ids_by_token_fingerprint: Dict[str, str] = {}

    def register(self, approver: ApproverIdentity, *, bearer_token: str) -> None:
        if len(bearer_token) < 16:
            raise ValueError("Approver bearer tokens must contain at least 16 characters.")
        fingerprint = _token_fingerprint(bearer_token)
        existing_id = self._approver_ids_by_token_fingerprint.get(fingerprint)
        if existing_id is not None and existing_id != approver.approver_id:
            raise ValueError("Approver bearer tokens must be unique.")
        self._approvers[approver.approver_id] = approver
        self._approver_ids_by_token_fingerprint[fingerprint] = approver.approver_id

    def authenticate(self, bearer_token: str) -> ApproverIdentity:
        approver_id = self._approver_ids_by_token_fingerprint.get(
            _token_fingerprint(bearer_token)
        )
        approver = self._approvers.get(approver_id) if approver_id else None
        if approver is None:
            raise ApproverAuthenticationError("Invalid approver bearer credential.")
        return approver

    def get(self, approver_id: str) -> ApproverIdentity:
        try:
            return self._approvers[approver_id]
        except KeyError as exc:
            raise ApproverAuthenticationError("Approver identity is not registered.") from exc

    def find(self, approver_id: str) -> Optional[ApproverIdentity]:
        return self._approvers.get(approver_id)

    def list_approvers(self) -> List[ApproverIdentity]:
        return list(self._approvers.values())


def evaluate_approval_authorization(
    *,
    approver: ApproverIdentity,
    action: ApprovalAction,
    requester_id: str,
    agent_id: str,
    tool_name: str,
    request_risk_level: str,
) -> ApprovalAuthorizationDecision:
    reason_codes = []
    if not approver.active:
        reason_codes.append("approver_inactive")
    if approver.approver_id == requester_id:
        reason_codes.append("requester_cannot_approve_own_request")
    if approver.approver_id == agent_id:
        reason_codes.append("agent_cannot_approve_own_action")
    if action not in approver.permitted_actions:
        reason_codes.append("approval_action_not_permitted")
    if "*" not in approver.allowed_tools and tool_name not in approver.allowed_tools:
        reason_codes.append("tool_outside_approver_scope")
    if (
        "*" not in approver.allowed_risk_levels
        and request_risk_level not in approver.allowed_risk_levels
    ):
        reason_codes.append("risk_outside_approver_scope")

    allowed = not reason_codes
    return ApprovalAuthorizationDecision(
        decision_id=str(uuid.uuid4()),
        approver_id=approver.approver_id,
        action=action,
        allowed=allowed,
        reason_codes=("approver_authorized_for_action",) if allowed else tuple(reason_codes),
        explanation=(
            f"Approver {approver.approver_id} is authorized to {action.value} this action."
            if allowed
            else (
                f"Approver {approver.approver_id} is not authorized to {action.value} "
                f"this action: {', '.join(reason_codes)}."
            )
        ),
    )


def _token_fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


approver_registry = ApproverRegistry()
approver_registry.register(
    ApproverIdentity(
        approver_id="demo-approver",
        display_name="Demo Risk Reviewer",
        role=ApproverRole.risk_reviewer,
        allowed_tools=("create_action_item", "send_external_message"),
        allowed_risk_levels=("medium", "high"),
        permitted_actions=(ApprovalAction.approve, ApprovalAction.reject),
    ),
    bearer_token=settings.demo_approver_token,
)
approver_registry.register(
    ApproverIdentity(
        approver_id="limited-approver",
        display_name="Limited Internal Reviewer",
        role=ApproverRole.risk_reviewer,
        allowed_tools=("create_action_item",),
        allowed_risk_levels=("medium",),
        permitted_actions=(ApprovalAction.approve, ApprovalAction.reject),
    ),
    bearer_token=settings.limited_approver_token,
)
approver_registry.register(
    ApproverIdentity(
        approver_id="governance-admin",
        display_name="Governance Administrator",
        role=ApproverRole.governance_admin,
        allowed_tools=("*",),
        allowed_risk_levels=("*",),
        permitted_actions=(ApprovalAction.approve, ApprovalAction.reject),
    ),
    bearer_token=settings.governance_admin_token,
)
approver_registry.register(
    ApproverIdentity(
        approver_id="audit-observer",
        display_name="Audit Observer",
        role=ApproverRole.audit_observer,
        allowed_tools=("*",),
        allowed_risk_levels=("*",),
        permitted_actions=(),
    ),
    bearer_token=settings.audit_observer_token,
)
