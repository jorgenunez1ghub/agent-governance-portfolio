import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict


class ApprovalState(str, Enum):
    pending = "pending"
    executing = "executing"
    execution_failed = "execution_failed"
    executed = "executed"
    rejected = "rejected"
    expired = "expired"


class ExecutionReceiptStatus(str, Enum):
    in_progress = "in_progress"
    succeeded = "succeeded"
    failed = "failed"


class ExecutionReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    receipt_id: str
    approval_id: str
    run_id: str
    agent_id: str
    policy_decision_id: str
    path_id: str
    path_action_id: str
    approver_id: str
    approval_authorization_decision_id: str
    tool_name: str
    tool_version: str
    idempotency_key_fingerprint: str
    attempt_number: int
    status: ExecutionReceiptStatus
    retryable: Optional[bool] = None
    result: Optional[Dict[str, Any]] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    started_at: str
    completed_at: Optional[str] = None


class ApprovalRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approval_id: str
    run_id: str
    agent_id: str
    policy_decision_id: str
    path_id: str
    path_action_id: str
    requester_id: str
    request_risk_level: str
    tool_name: str
    tool_version: str
    arguments: Dict[str, Any]
    status: ApprovalState
    reason: str
    expires_at: str
    attempt_count: int = 0
    active_receipt_id: Optional[str] = None
    execution_receipt_ids: Tuple[str, ...] = ()
    authorized_approver_id: Optional[str] = None
    approval_authorization_decision_id: Optional[str] = None
    created_at: str
    updated_at: str


class ExecutionStart(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approval: ApprovalRecord
    receipt: ExecutionReceipt
    idempotent_replay: bool


class ApprovalNotFoundError(Exception):
    pass


class ExecutionReceiptNotFoundError(Exception):
    pass


class ApprovalTransitionError(Exception):
    pass


class ApprovalExpiredError(ApprovalTransitionError):
    def __init__(self, approval: ApprovalRecord) -> None:
        self.approval = approval
        super().__init__(
            f"Approval {approval.approval_id} expired at {approval.expires_at} and cannot execute."
        )


class ApprovalExecutionInProgressError(ApprovalTransitionError):
    def __init__(self, receipt: ExecutionReceipt) -> None:
        self.receipt = receipt
        super().__init__(
            f"Approval {receipt.approval_id} is already executing under receipt {receipt.receipt_id}."
        )


class ApprovalIdempotencyConflictError(ApprovalTransitionError):
    pass


class ApprovalRetryNotAllowedError(ApprovalTransitionError):
    pass


class InMemoryApprovalStore:
    def __init__(self) -> None:
        self._approvals: Dict[str, ApprovalRecord] = {}
        self._receipts: Dict[str, ExecutionReceipt] = {}
        self._receipt_ids_by_fingerprint: Dict[Tuple[str, str], str] = {}

    def create(
        self,
        *,
        run_id: str,
        agent_id: str,
        policy_decision_id: str,
        path_id: str,
        path_action_id: str,
        requester_id: str,
        request_risk_level: str,
        tool_name: str,
        tool_version: str,
        arguments: Dict[str, Any],
        reason: str,
        ttl_seconds: int,
        now: Optional[datetime] = None,
    ) -> ApprovalRecord:
        current_time = _as_utc(now or datetime.now(timezone.utc))
        approval = ApprovalRecord(
            approval_id=str(uuid.uuid4()),
            run_id=run_id,
            agent_id=agent_id,
            policy_decision_id=policy_decision_id,
            path_id=path_id,
            path_action_id=path_action_id,
            requester_id=requester_id,
            request_risk_level=request_risk_level,
            tool_name=tool_name,
            tool_version=tool_version,
            arguments=arguments,
            status=ApprovalState.pending,
            reason=reason,
            expires_at=_format_time(current_time + timedelta(seconds=ttl_seconds)),
            created_at=_format_time(current_time),
            updated_at=_format_time(current_time),
        )
        self._approvals[approval.approval_id] = approval
        return approval

    def get(self, approval_id: str) -> ApprovalRecord:
        try:
            return self._approvals[approval_id]
        except KeyError as exc:
            raise ApprovalNotFoundError(f"Approval not found: {approval_id}") from exc

    def get_receipt(self, receipt_id: str) -> ExecutionReceipt:
        try:
            return self._receipts[receipt_id]
        except KeyError as exc:
            raise ExecutionReceiptNotFoundError(
                f"Execution receipt not found: {receipt_id}"
            ) from exc

    def get_receipt_for_key(
        self,
        *,
        approval_id: str,
        idempotency_key: str,
    ) -> Optional[ExecutionReceipt]:
        receipt_id = self._receipt_ids_by_fingerprint.get(
            (approval_id, _fingerprint(idempotency_key))
        )
        return self.get_receipt(receipt_id) if receipt_id else None

    def list_receipts(self, approval_id: str) -> List[ExecutionReceipt]:
        approval = self.get(approval_id)
        return [self.get_receipt(receipt_id) for receipt_id in approval.execution_receipt_ids]

    def begin_execution(
        self,
        *,
        approval_id: str,
        idempotency_key: str,
        approver_id: str,
        authorization_decision_id: str,
        now: Optional[datetime] = None,
    ) -> ExecutionStart:
        if not 1 <= len(idempotency_key) <= 200:
            raise ValueError("Idempotency key must contain between 1 and 200 characters.")

        approval = self.get(approval_id)
        existing_receipt = self.get_receipt_for_key(
            approval_id=approval_id,
            idempotency_key=idempotency_key,
        )
        if existing_receipt is not None:
            if existing_receipt.status == ExecutionReceiptStatus.in_progress:
                raise ApprovalExecutionInProgressError(existing_receipt)
            return ExecutionStart(
                approval=approval,
                receipt=existing_receipt,
                idempotent_replay=True,
            )

        current_time = _as_utc(now or datetime.now(timezone.utc))
        approval = self._expire_if_due(approval, current_time)
        if approval.status == ApprovalState.expired:
            raise ApprovalExpiredError(approval)

        if approval.status == ApprovalState.execution_failed:
            previous_receipt = (
                self.get_receipt(approval.active_receipt_id)
                if approval.active_receipt_id
                else None
            )
            if previous_receipt is None or previous_receipt.retryable is not True:
                raise ApprovalRetryNotAllowedError(
                    f"Approval {approval_id} has a terminal execution failure and cannot retry."
                )
        elif approval.status != ApprovalState.pending:
            if approval.status == ApprovalState.executed:
                raise ApprovalIdempotencyConflictError(
                    f"Approval {approval_id} already executed under a different idempotency key."
                )
            raise ApprovalTransitionError(
                f"Approval {approval_id} is {approval.status.value} and cannot begin execution."
            )

        receipt = ExecutionReceipt(
            receipt_id=str(uuid.uuid4()),
            approval_id=approval.approval_id,
            run_id=approval.run_id,
            agent_id=approval.agent_id,
            policy_decision_id=approval.policy_decision_id,
            path_id=approval.path_id,
            path_action_id=approval.path_action_id,
            approver_id=approver_id,
            approval_authorization_decision_id=authorization_decision_id,
            tool_name=approval.tool_name,
            tool_version=approval.tool_version,
            idempotency_key_fingerprint=_fingerprint(idempotency_key),
            attempt_number=approval.attempt_count + 1,
            status=ExecutionReceiptStatus.in_progress,
            started_at=_format_time(current_time),
        )
        self._receipts[receipt.receipt_id] = receipt
        self._receipt_ids_by_fingerprint[
            (approval_id, receipt.idempotency_key_fingerprint)
        ] = receipt.receipt_id

        updated_approval = approval.model_copy(
            update={
                "status": ApprovalState.executing,
                "attempt_count": receipt.attempt_number,
                "active_receipt_id": receipt.receipt_id,
                "authorized_approver_id": approver_id,
                "approval_authorization_decision_id": authorization_decision_id,
                "execution_receipt_ids": (
                    *approval.execution_receipt_ids,
                    receipt.receipt_id,
                ),
                "updated_at": _format_time(current_time),
            }
        )
        self._approvals[approval_id] = updated_approval
        return ExecutionStart(
            approval=updated_approval,
            receipt=receipt,
            idempotent_replay=False,
        )

    def complete_execution(
        self,
        *,
        approval_id: str,
        receipt_id: str,
        result: Dict[str, Any],
        now: Optional[datetime] = None,
    ) -> Tuple[ApprovalRecord, ExecutionReceipt]:
        current_time = _as_utc(now or datetime.now(timezone.utc))
        approval, receipt = self._require_active_execution(approval_id, receipt_id)
        completed_receipt = receipt.model_copy(
            update={
                "status": ExecutionReceiptStatus.succeeded,
                "retryable": False,
                "result": result,
                "completed_at": _format_time(current_time),
            }
        )
        executed_approval = approval.model_copy(
            update={
                "status": ApprovalState.executed,
                "updated_at": _format_time(current_time),
            }
        )
        self._receipts[receipt_id] = completed_receipt
        self._approvals[approval_id] = executed_approval
        return executed_approval, completed_receipt

    def fail_execution(
        self,
        *,
        approval_id: str,
        receipt_id: str,
        error_code: str,
        error_message: str,
        retryable: bool,
        now: Optional[datetime] = None,
    ) -> Tuple[ApprovalRecord, ExecutionReceipt]:
        current_time = _as_utc(now or datetime.now(timezone.utc))
        approval, receipt = self._require_active_execution(approval_id, receipt_id)
        failed_receipt = receipt.model_copy(
            update={
                "status": ExecutionReceiptStatus.failed,
                "retryable": retryable,
                "error_code": error_code,
                "error_message": error_message,
                "completed_at": _format_time(current_time),
            }
        )
        failed_approval = approval.model_copy(
            update={
                "status": ApprovalState.execution_failed,
                "updated_at": _format_time(current_time),
            }
        )
        self._receipts[receipt_id] = failed_receipt
        self._approvals[approval_id] = failed_approval
        return failed_approval, failed_receipt

    def reject(
        self,
        approval_id: str,
        *,
        approver_id: str,
        authorization_decision_id: str,
        now: Optional[datetime] = None,
    ) -> ApprovalRecord:
        current_time = _as_utc(now or datetime.now(timezone.utc))
        approval = self._expire_if_due(self.get(approval_id), current_time)
        if approval.status == ApprovalState.expired:
            raise ApprovalExpiredError(approval)
        if approval.status != ApprovalState.pending:
            raise ApprovalTransitionError(
                f"Approval {approval.approval_id} is {approval.status.value}; "
                "only pending approvals can be rejected."
            )
        rejected = approval.model_copy(
            update={
                "status": ApprovalState.rejected,
                "authorized_approver_id": approver_id,
                "approval_authorization_decision_id": authorization_decision_id,
                "updated_at": _format_time(current_time),
            }
        )
        self._approvals[approval_id] = rejected
        return rejected

    def expire_if_due(
        self,
        approval_id: str,
        *,
        now: Optional[datetime] = None,
    ) -> ApprovalRecord:
        current_time = _as_utc(now or datetime.now(timezone.utc))
        return self._expire_if_due(self.get(approval_id), current_time)

    def reset(self) -> None:
        self._approvals.clear()
        self._receipts.clear()
        self._receipt_ids_by_fingerprint.clear()

    def _expire_if_due(
        self,
        approval: ApprovalRecord,
        current_time: datetime,
    ) -> ApprovalRecord:
        if approval.status == ApprovalState.execution_failed:
            previous_receipt = (
                self.get_receipt(approval.active_receipt_id)
                if approval.active_receipt_id
                else None
            )
            if previous_receipt is None or previous_receipt.retryable is not True:
                return approval
        elif approval.status != ApprovalState.pending:
            return approval
        if current_time < _parse_time(approval.expires_at):
            return approval

        expired = approval.model_copy(
            update={
                "status": ApprovalState.expired,
                "updated_at": _format_time(current_time),
            }
        )
        self._approvals[approval.approval_id] = expired
        return expired

    def _require_active_execution(
        self,
        approval_id: str,
        receipt_id: str,
    ) -> Tuple[ApprovalRecord, ExecutionReceipt]:
        approval = self.get(approval_id)
        receipt = self.get_receipt(receipt_id)
        if approval.status != ApprovalState.executing:
            raise ApprovalTransitionError(
                f"Approval {approval_id} is {approval.status.value}; expected executing."
            )
        if approval.active_receipt_id != receipt_id:
            raise ApprovalTransitionError(
                f"Receipt {receipt_id} is not the active execution for approval {approval_id}."
            )
        if receipt.status != ExecutionReceiptStatus.in_progress:
            raise ApprovalTransitionError(
                f"Receipt {receipt_id} is {receipt.status.value}; expected in_progress."
            )
        return approval, receipt


def _fingerprint(idempotency_key: str) -> str:
    return hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _format_time(value: datetime) -> str:
    return _as_utc(value).isoformat().replace("+00:00", "Z")


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


approval_store = InMemoryApprovalStore()
