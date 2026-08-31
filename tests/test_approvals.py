from datetime import datetime, timedelta, timezone

import pytest

from app.governance.approvals import (
    ApprovalExpiredError,
    ApprovalExecutionInProgressError,
    ApprovalIdempotencyConflictError,
    ApprovalRetryNotAllowedError,
    ApprovalState,
    ExecutionReceiptStatus,
    InMemoryApprovalStore,
)


def _create_approval(
    store: InMemoryApprovalStore,
    *,
    now: datetime,
    ttl_seconds: int = 60,
):
    return store.create(
        run_id="run-1",
        agent_id="demo-agent",
        policy_decision_id="decision-1",
        path_id="path-1",
        path_action_id="action-1",
        requester_id="requester-1",
        request_risk_level="high",
        tool_name="send_external_message",
        tool_version="1.0.0",
        arguments={"recipient": "demo@example.com", "message": "hello"},
        reason="External write requires approval.",
        ttl_seconds=ttl_seconds,
        now=now,
    )


def test_expired_approval_fails_closed_before_receipt_creation():
    store = InMemoryApprovalStore()
    now = datetime(2026, 7, 29, tzinfo=timezone.utc)
    approval = _create_approval(store, now=now, ttl_seconds=30)

    with pytest.raises(ApprovalExpiredError):
        store.begin_execution(
            approval_id=approval.approval_id,
            idempotency_key="attempt-1",
            approver_id="demo-approver",
            authorization_decision_id="authz-1",
            now=now + timedelta(seconds=30),
        )

    assert store.get(approval.approval_id).status == ApprovalState.expired
    assert store.list_receipts(approval.approval_id) == []


def test_same_idempotency_key_replays_completed_receipt():
    store = InMemoryApprovalStore()
    now = datetime(2026, 7, 29, tzinfo=timezone.utc)
    approval = _create_approval(store, now=now)

    start = store.begin_execution(
        approval_id=approval.approval_id,
        idempotency_key="stable-key",
        approver_id="demo-approver",
        authorization_decision_id="authz-1",
        now=now,
    )
    executed, receipt = store.complete_execution(
        approval_id=approval.approval_id,
        receipt_id=start.receipt.receipt_id,
        result={"status": "simulated_sent"},
        now=now + timedelta(seconds=1),
    )
    replay = store.begin_execution(
        approval_id=approval.approval_id,
        idempotency_key="stable-key",
        approver_id="demo-approver",
        authorization_decision_id="authz-1",
        now=now + timedelta(seconds=2),
    )

    assert executed.status == ApprovalState.executed
    assert receipt.status == ExecutionReceiptStatus.succeeded
    assert replay.idempotent_replay is True
    assert replay.receipt.receipt_id == receipt.receipt_id
    assert replay.receipt.idempotency_key_fingerprint != "stable-key"
    assert all(
        key_fingerprint != "stable-key"
        for _, key_fingerprint in store._receipt_ids_by_fingerprint
    )

    with pytest.raises(ApprovalIdempotencyConflictError):
        store.begin_execution(
            approval_id=approval.approval_id,
            idempotency_key="different-key",
            approver_id="demo-approver",
            authorization_decision_id="authz-1",
            now=now + timedelta(seconds=3),
        )


def test_in_progress_receipt_blocks_duplicate_execution():
    store = InMemoryApprovalStore()
    now = datetime(2026, 7, 29, tzinfo=timezone.utc)
    approval = _create_approval(store, now=now)
    start = store.begin_execution(
        approval_id=approval.approval_id,
        idempotency_key="attempt-1",
        approver_id="demo-approver",
        authorization_decision_id="authz-1",
        now=now,
    )

    with pytest.raises(ApprovalExecutionInProgressError):
        store.begin_execution(
            approval_id=approval.approval_id,
            idempotency_key="attempt-1",
            approver_id="demo-approver",
            authorization_decision_id="authz-1",
            now=now + timedelta(seconds=1),
        )

    assert store.get_receipt(start.receipt.receipt_id).status == ExecutionReceiptStatus.in_progress


def test_retryable_failure_allows_one_new_key_and_terminal_failure_stops_retries():
    store = InMemoryApprovalStore()
    now = datetime(2026, 7, 29, tzinfo=timezone.utc)
    approval = _create_approval(store, now=now)

    first = store.begin_execution(
        approval_id=approval.approval_id,
        idempotency_key="attempt-1",
        approver_id="demo-approver",
        authorization_decision_id="authz-1",
        now=now,
    )
    failed_approval, failed_receipt = store.fail_execution(
        approval_id=approval.approval_id,
        receipt_id=first.receipt.receipt_id,
        error_code="mock_timeout",
        error_message="Temporary timeout.",
        retryable=True,
        now=now + timedelta(seconds=1),
    )

    assert failed_approval.status == ApprovalState.execution_failed
    assert failed_receipt.retryable is True

    replay = store.begin_execution(
        approval_id=approval.approval_id,
        idempotency_key="attempt-1",
        approver_id="demo-approver",
        authorization_decision_id="authz-1",
        now=now + timedelta(seconds=2),
    )
    assert replay.idempotent_replay is True
    assert replay.receipt.receipt_id == failed_receipt.receipt_id

    second = store.begin_execution(
        approval_id=approval.approval_id,
        idempotency_key="attempt-2",
        approver_id="demo-approver",
        authorization_decision_id="authz-1",
        now=now + timedelta(seconds=3),
    )
    terminal_approval, terminal_receipt = store.fail_execution(
        approval_id=approval.approval_id,
        receipt_id=second.receipt.receipt_id,
        error_code="mock_terminal",
        error_message="Terminal failure.",
        retryable=False,
        now=now + timedelta(seconds=4),
    )

    assert second.receipt.attempt_number == 2
    assert terminal_approval.status == ApprovalState.execution_failed
    assert terminal_receipt.retryable is False

    with pytest.raises(ApprovalRetryNotAllowedError):
        store.begin_execution(
            approval_id=approval.approval_id,
            idempotency_key="attempt-3",
            approver_id="demo-approver",
            authorization_decision_id="authz-1",
            now=now + timedelta(seconds=65),
        )
    assert store.get(approval.approval_id).status == ApprovalState.execution_failed
