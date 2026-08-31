import pytest

from app.governance.approvers import (
    ApprovalAction,
    ApproverAuthenticationError,
    ApproverIdentity,
    ApproverRegistry,
    ApproverRole,
    evaluate_approval_authorization,
)


def _approver(**overrides: object) -> ApproverIdentity:
    values = {
        "approver_id": "reviewer-1",
        "display_name": "Reviewer One",
        "role": ApproverRole.risk_reviewer,
        "allowed_tools": ("send_external_message",),
        "allowed_risk_levels": ("high",),
        "permitted_actions": (ApprovalAction.approve, ApprovalAction.reject),
        "active": True,
    }
    values.update(overrides)
    return ApproverIdentity(**values)


def test_registry_authenticates_registered_token_without_retaining_plaintext() -> None:
    registry = ApproverRegistry()
    token = "test-credential-with-enough-entropy"
    approver = _approver()

    registry.register(approver, bearer_token=token)

    assert registry.authenticate(token) == approver
    assert token not in repr(registry.__dict__)


def test_registry_rejects_invalid_and_short_credentials() -> None:
    registry = ApproverRegistry()

    with pytest.raises(ValueError, match="at least 16"):
        registry.register(_approver(), bearer_token="too-short")

    registry.register(_approver(), bearer_token="valid-test-token-value")
    with pytest.raises(ApproverAuthenticationError, match="Invalid"):
        registry.authenticate("wrong-test-token-value")


def test_authorized_reviewer_can_approve_in_scope_action() -> None:
    decision = evaluate_approval_authorization(
        approver=_approver(),
        action=ApprovalAction.approve,
        requester_id="requester-1",
        agent_id="agent-1",
        tool_name="send_external_message",
        request_risk_level="high",
    )

    assert decision.allowed is True
    assert decision.reason_codes == ("approver_authorized_for_action",)


@pytest.mark.parametrize(
    ("approver", "action", "requester_id", "agent_id", "tool", "risk", "reason"),
    [
        (
            _approver(active=False),
            ApprovalAction.approve,
            "requester-1",
            "agent-1",
            "send_external_message",
            "high",
            "approver_inactive",
        ),
        (
            _approver(),
            ApprovalAction.approve,
            "reviewer-1",
            "agent-1",
            "send_external_message",
            "high",
            "requester_cannot_approve_own_request",
        ),
        (
            _approver(),
            ApprovalAction.approve,
            "requester-1",
            "reviewer-1",
            "send_external_message",
            "high",
            "agent_cannot_approve_own_action",
        ),
        (
            _approver(permitted_actions=()),
            ApprovalAction.reject,
            "requester-1",
            "agent-1",
            "send_external_message",
            "high",
            "approval_action_not_permitted",
        ),
        (
            _approver(),
            ApprovalAction.approve,
            "requester-1",
            "agent-1",
            "create_action_item",
            "high",
            "tool_outside_approver_scope",
        ),
        (
            _approver(),
            ApprovalAction.approve,
            "requester-1",
            "agent-1",
            "send_external_message",
            "medium",
            "risk_outside_approver_scope",
        ),
    ],
)
def test_authorization_denies_governance_violations(
    approver: ApproverIdentity,
    action: ApprovalAction,
    requester_id: str,
    agent_id: str,
    tool: str,
    risk: str,
    reason: str,
) -> None:
    decision = evaluate_approval_authorization(
        approver=approver,
        action=action,
        requester_id=requester_id,
        agent_id=agent_id,
        tool_name=tool,
        request_risk_level=risk,
    )

    assert decision.allowed is False
    assert reason in decision.reason_codes
