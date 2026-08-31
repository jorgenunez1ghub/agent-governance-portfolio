import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from app.agent.planner import create_plan
from app.agent.retrieval import retrieve_context
from app.api.schemas import AgentPlan, AgentRunRequest, AgentRunResponse, ApprovalActionResponse, ToolCall
from app.audit.logger import audit_logger
from app.config import settings
from app.governance.approvals import (
    ApprovalExpiredError,
    ApprovalRecord,
    ApprovalTransitionError,
    ExecutionReceipt,
    ExecutionReceiptStatus,
    approval_store,
)
from app.governance.approvers import (
    ApprovalAction,
    ApprovalAuthorizationDecision,
    ApprovalAuthorizationError,
    ApproverIdentity,
    evaluate_approval_authorization,
)
from app.governance.identity import agent_registry
from app.governance.path import (
    ExecutionPathContext,
    PathActionOutcome,
    PathActionRecord,
    execution_path_store,
)
from app.governance.policy import PolicyDecision, PolicyOutcome, evaluate_policy
from app.tools.errors import ToolExecutionError
from app.tools.registry import ToolDefinition, tool_registry


async def run_agent(request: AgentRunRequest) -> AgentRunResponse:
    path = execution_path_store.resolve(path_id=request.path_id, agent_id=request.agent_id)
    path_context = execution_path_store.context(path_id=path.path_id, agent_id=request.agent_id)
    run_id = str(uuid.uuid4())
    path_action_id = str(uuid.uuid4())
    path_audit_fields = {
        "path_id": path.path_id,
        "path_action_id": path_action_id,
    }

    await audit_logger.log_event(
        event_type="run_started",
        run_id=run_id,
        agent_id=request.agent_id,
        actor=request.user_id,
        details={
            "task": request.task,
            "risk_level": request.risk_level,
            "prior_path_action_count": path_context.action_count,
        },
        **path_audit_fields,
    )

    plan: Optional[AgentPlan] = None
    decision: Optional[PolicyDecision] = None
    tool_definition: Optional[ToolDefinition] = None
    path_action_recorded = False

    try:
        context_task = retrieve_context(task=request.task, user_id=request.user_id)
        planning_task = create_plan(task=request.task, risk_level=request.risk_level)
        context, plan = await asyncio.gather(context_task, planning_task)

        await audit_logger.log_event(
            event_type="context_retrieved",
            run_id=run_id,
            agent_id=request.agent_id,
            actor="system",
            details={"source": context["source"], "snippet_count": len(context["snippets"])},
            **path_audit_fields,
        )
        await audit_logger.log_event(
            event_type="plan_created",
            run_id=run_id,
            agent_id=request.agent_id,
            actor="system",
            details=plan.model_dump(),
            **path_audit_fields,
        )

        tool_definition = tool_registry.get_tool(plan.tool_name)
        tool_audit_fields = {
            **path_audit_fields,
            **_tool_audit_fields(tool_definition),
        }
        await audit_logger.log_event(
            event_type="tool_selected",
            run_id=run_id,
            agent_id=request.agent_id,
            actor="system",
            details={
                "description": tool_definition.description,
                "owner": tool_definition.owner,
                "source": tool_definition.source,
                "risk_class": tool_definition.risk_class.value,
                "provenance_status": tool_definition.provenance_status.value,
            },
            **tool_audit_fields,
        )

        try:
            validated_input = tool_registry.validate_tool_input(plan.tool_name, plan.arguments)
        except ValidationError as exc:
            await audit_logger.log_event(
                event_type="tool_validation_failed",
                run_id=run_id,
                agent_id=request.agent_id,
                actor="system",
                details={"errors": _format_validation_errors(exc)},
                **tool_audit_fields,
            )
            path_action_recorded = True
            await _record_path_action(
                path_context=path_context,
                action_id=path_action_id,
                run_id=run_id,
                tool=tool_definition,
                request_risk_level=request.risk_level,
                execution_outcome=PathActionOutcome.validation_failed,
            )
            await audit_logger.log_event(
                event_type="run_failed",
                run_id=run_id,
                agent_id=request.agent_id,
                actor="system",
                details={"reason": "tool_input_validation_failed"},
                **tool_audit_fields,
            )
            return AgentRunResponse(
                status="failed",
                run_id=run_id,
                agent_id=request.agent_id,
                path_id=path.path_id,
                path_action_id=path_action_id,
                plan=plan,
                approval_required=False,
                error="Tool input validation failed.",
            )

        validated_arguments = validated_input.model_dump()
        await audit_logger.log_event(
            event_type="tool_validation_passed",
            run_id=run_id,
            agent_id=request.agent_id,
            actor="system",
            details={"arguments": validated_arguments},
            **tool_audit_fields,
        )

        decision = evaluate_policy(
            agent_id=request.agent_id,
            agent=agent_registry.find(request.agent_id),
            tool=tool_definition,
            request_risk_level=request.risk_level,
            execution_path=path_context,
        )
        decision_audit_fields = {
            **tool_audit_fields,
            "policy_decision_id": decision.decision_id,
        }
        await audit_logger.log_event(
            event_type="policy_evaluated",
            run_id=run_id,
            agent_id=request.agent_id,
            actor="policy-engine",
            details=decision.model_dump(mode="json"),
            **decision_audit_fields,
        )

        if decision.outcome == PolicyOutcome.deny:
            path_action_recorded = True
            await _record_path_action(
                path_context=path_context,
                action_id=path_action_id,
                run_id=run_id,
                tool=tool_definition,
                request_risk_level=request.risk_level,
                execution_outcome=PathActionOutcome.denied,
                decision=decision,
            )
            await audit_logger.log_event(
                event_type="run_denied",
                run_id=run_id,
                agent_id=request.agent_id,
                actor="policy-engine",
                details={
                    "reason_codes": decision.reason_codes,
                    "explanation": decision.explanation,
                },
                **decision_audit_fields,
            )
            return AgentRunResponse(
                status="denied",
                run_id=run_id,
                agent_id=request.agent_id,
                path_id=path.path_id,
                path_action_id=path_action_id,
                plan=plan,
                policy_decision=decision,
                approval_required=False,
                reason=decision.explanation,
            )

        if decision.outcome == PolicyOutcome.require_approval:
            approval = approval_store.create(
                run_id=run_id,
                agent_id=request.agent_id,
                policy_decision_id=decision.decision_id,
                path_id=path.path_id,
                path_action_id=path_action_id,
                requester_id=request.user_id,
                request_risk_level=request.risk_level,
                tool_name=plan.tool_name,
                tool_version=tool_definition.version,
                arguments=validated_arguments,
                reason=decision.explanation,
                ttl_seconds=settings.approval_ttl_seconds,
            )
            path_action_recorded = True
            await _record_path_action(
                path_context=path_context,
                action_id=path_action_id,
                run_id=run_id,
                tool=tool_definition,
                request_risk_level=request.risk_level,
                execution_outcome=PathActionOutcome.approval_required,
                decision=decision,
                approval_id=approval.approval_id,
                approval_status=approval.status.value,
            )
            await audit_logger.log_event(
                event_type="approval_required",
                run_id=run_id,
                approval_id=approval.approval_id,
                agent_id=request.agent_id,
                actor="policy-engine",
                details={
                    "reason": decision.explanation,
                    "reason_codes": decision.reason_codes,
                },
                **decision_audit_fields,
            )
            return AgentRunResponse(
                status="approval_required",
                run_id=run_id,
                agent_id=request.agent_id,
                path_id=path.path_id,
                path_action_id=path_action_id,
                plan=plan,
                policy_decision=decision,
                approval_required=True,
                approval_id=approval.approval_id,
                approval_expires_at=approval.expires_at,
                proposed_action=ToolCall(tool_name=plan.tool_name, arguments=validated_arguments),
                reason=decision.explanation,
            )

        tool_result = await tool_registry.execute_validated_tool(plan.tool_name, validated_input)
        await _log_tool_executed(
            run_id=run_id,
            agent_id=request.agent_id,
            path_id=path.path_id,
            path_action_id=path_action_id,
            decision=decision,
            tool=tool_definition,
            result=tool_result,
        )
        path_action_recorded = True
        await _record_path_action(
            path_context=path_context,
            action_id=path_action_id,
            run_id=run_id,
            tool=tool_definition,
            request_risk_level=request.risk_level,
            execution_outcome=PathActionOutcome.executed,
            decision=decision,
        )
        await audit_logger.log_event(
            event_type="run_completed",
            run_id=run_id,
            agent_id=request.agent_id,
            policy_decision_id=decision.decision_id,
            actor="system",
            details={"status": "completed"},
            **tool_audit_fields,
        )

        return AgentRunResponse(
            status="completed",
            run_id=run_id,
            agent_id=request.agent_id,
            path_id=path.path_id,
            path_action_id=path_action_id,
            plan=plan,
            policy_decision=decision,
            tool_result=tool_result,
            approval_required=False,
        )

    except Exception as exc:
        failure_audit_fields: Dict[str, Any] = dict(path_audit_fields)
        if tool_definition is not None:
            failure_audit_fields.update(_tool_audit_fields(tool_definition))
        if decision is not None:
            failure_audit_fields["policy_decision_id"] = decision.decision_id

        await audit_logger.log_event(
            event_type="run_failed",
            run_id=run_id,
            agent_id=request.agent_id,
            actor="system",
            details={"reason": str(exc), "plan": plan.model_dump() if plan else None},
            **failure_audit_fields,
        )
        if tool_definition is not None and not path_action_recorded:
            path_action_recorded = True
            await _record_path_action(
                path_context=path_context,
                action_id=path_action_id,
                run_id=run_id,
                tool=tool_definition,
                request_risk_level=request.risk_level,
                execution_outcome=PathActionOutcome.execution_failed,
                decision=decision,
            )
        return AgentRunResponse(
            status="failed",
            run_id=run_id,
            agent_id=request.agent_id,
            path_id=path.path_id,
            path_action_id=path_action_id,
            plan=plan,
            policy_decision=decision,
            approval_required=False,
            error=str(exc),
        )


async def approve_approval(
    approval_id: str,
    approver: ApproverIdentity,
    idempotency_key: Optional[str] = None,
) -> ApprovalActionResponse:
    approval = approval_store.get(approval_id)
    authorization = await _authorize_approval_action(
        approval=approval,
        approver=approver,
        action=ApprovalAction.approve,
    )
    resolved_key = idempotency_key or f"approval:{approval_id}"
    existing_receipt = approval_store.get_receipt_for_key(
        approval_id=approval_id,
        idempotency_key=resolved_key,
    )
    if existing_receipt is not None and existing_receipt.status != ExecutionReceiptStatus.in_progress:
        return await _replay_execution_receipt(
            approval=approval,
            receipt=existing_receipt,
            authorization=authorization,
        )

    tool_definition = tool_registry.get_tool(approval.tool_name)
    if tool_definition.version != approval.tool_version:
        raise ApprovalTransitionError(
            f"Approval {approval_id} is bound to {approval.tool_name} "
            f"version {approval.tool_version}; current version is {tool_definition.version}."
        )

    try:
        execution_start = approval_store.begin_execution(
            approval_id=approval_id,
            idempotency_key=resolved_key,
            approver_id=approver.approver_id,
            authorization_decision_id=authorization.decision_id,
        )
    except ApprovalExpiredError as exc:
        await _record_expired_approval(
            approval=exc.approval,
            tool=tool_definition,
            authorization=authorization,
        )
        raise

    if execution_start.idempotent_replay:
        return await _replay_execution_receipt(
            approval=execution_start.approval,
            receipt=execution_start.receipt,
            authorization=authorization,
        )

    approval = execution_start.approval
    receipt = execution_start.receipt
    audit_fields = _approval_audit_fields(approval, tool_definition, receipt)
    updated_action = execution_path_store.update_action(
        path_id=approval.path_id,
        action_id=approval.path_action_id,
        execution_outcome=PathActionOutcome.approval_required,
        approval_status=approval.status.value,
        approver_id=approval.authorized_approver_id,
        approval_authorization_decision_id=(
            approval.approval_authorization_decision_id
        ),
    )
    await _log_path_action_updated(
        action=updated_action,
        agent_id=approval.agent_id,
        path_id=approval.path_id,
        approval_id=approval.approval_id,
        execution_receipt_id=receipt.receipt_id,
    )
    await audit_logger.log_event(
        event_type="approval_approved",
        run_id=approval.run_id,
        approval_id=approval.approval_id,
        agent_id=approval.agent_id,
        actor=approver.approver_id,
        details={
            "status": approval.status.value,
            "attempt_number": receipt.attempt_number,
            "idempotency_key_fingerprint": receipt.idempotency_key_fingerprint,
        },
        **audit_fields,
    )
    await audit_logger.log_event(
        event_type="approval_execution_started",
        run_id=approval.run_id,
        approval_id=approval.approval_id,
        agent_id=approval.agent_id,
        actor="approval-executor",
        details=receipt.model_dump(mode="json"),
        **audit_fields,
    )

    try:
        validated_input = tool_registry.validate_tool_input(approval.tool_name, approval.arguments)
        tool_result = await tool_registry.execute_validated_tool(approval.tool_name, validated_input)
    except Exception as exc:
        error_code, retryable = _classify_tool_failure(exc)
        failed_approval, failed_receipt = approval_store.fail_execution(
            approval_id=approval.approval_id,
            receipt_id=receipt.receipt_id,
            error_code=error_code,
            error_message=str(exc),
            retryable=retryable,
        )
        failure_audit_fields = _approval_audit_fields(
            failed_approval,
            tool_definition,
            failed_receipt,
        )
        updated_action = execution_path_store.update_action(
            path_id=failed_approval.path_id,
            action_id=failed_approval.path_action_id,
            execution_outcome=PathActionOutcome.execution_failed,
            approval_status=failed_approval.status.value,
            approver_id=failed_approval.authorized_approver_id,
            approval_authorization_decision_id=(
                failed_approval.approval_authorization_decision_id
            ),
        )
        await _log_path_action_updated(
            action=updated_action,
            agent_id=failed_approval.agent_id,
            path_id=failed_approval.path_id,
            approval_id=failed_approval.approval_id,
            execution_receipt_id=failed_receipt.receipt_id,
        )
        await audit_logger.log_event(
            event_type="approval_execution_failed",
            run_id=failed_approval.run_id,
            approval_id=failed_approval.approval_id,
            agent_id=failed_approval.agent_id,
            actor="approval-executor",
            details={
                "error_code": error_code,
                "error_message": str(exc),
                "retryable": retryable,
                "attempt_number": failed_receipt.attempt_number,
            },
            **failure_audit_fields,
        )
        await _log_execution_receipt(
            approval=failed_approval,
            receipt=failed_receipt,
            tool=tool_definition,
        )
        await audit_logger.log_event(
            event_type="run_failed",
            run_id=failed_approval.run_id,
            approval_id=failed_approval.approval_id,
            agent_id=failed_approval.agent_id,
            actor="system",
            details={
                "reason": "approved_tool_execution_failed",
                "error_code": error_code,
                "retryable": retryable,
            },
            **failure_audit_fields,
        )
        return _approval_response_from_receipt(
            approval=failed_approval,
            receipt=failed_receipt,
            idempotent_replay=False,
        )

    executed_approval, succeeded_receipt = approval_store.complete_execution(
        approval_id=approval.approval_id,
        receipt_id=receipt.receipt_id,
        result=tool_result,
    )
    success_audit_fields = _approval_audit_fields(
        executed_approval,
        tool_definition,
        succeeded_receipt,
    )
    await audit_logger.log_event(
        event_type="tool_executed",
        run_id=executed_approval.run_id,
        approval_id=executed_approval.approval_id,
        agent_id=executed_approval.agent_id,
        actor="system",
        details={"result": tool_result},
        **success_audit_fields,
    )
    updated_action = execution_path_store.update_action(
        path_id=executed_approval.path_id,
        action_id=executed_approval.path_action_id,
        execution_outcome=PathActionOutcome.executed,
        approval_status=executed_approval.status.value,
        approver_id=executed_approval.authorized_approver_id,
        approval_authorization_decision_id=(
            executed_approval.approval_authorization_decision_id
        ),
    )
    await _log_path_action_updated(
        action=updated_action,
        agent_id=executed_approval.agent_id,
        path_id=executed_approval.path_id,
        approval_id=executed_approval.approval_id,
        execution_receipt_id=succeeded_receipt.receipt_id,
    )
    await _log_execution_receipt(
        approval=executed_approval,
        receipt=succeeded_receipt,
        tool=tool_definition,
    )
    await audit_logger.log_event(
        event_type="run_completed",
        run_id=executed_approval.run_id,
        approval_id=executed_approval.approval_id,
        agent_id=executed_approval.agent_id,
        actor="system",
        details={"status": "completed_after_approval"},
        **success_audit_fields,
    )
    return _approval_response_from_receipt(
        approval=executed_approval,
        receipt=succeeded_receipt,
        idempotent_replay=False,
    )


async def reject_approval(
    approval_id: str,
    approver: ApproverIdentity,
) -> ApprovalActionResponse:
    pending_approval = approval_store.get(approval_id)
    authorization = await _authorize_approval_action(
        approval=pending_approval,
        approver=approver,
        action=ApprovalAction.reject,
    )
    tool_definition = tool_registry.get_tool(pending_approval.tool_name)
    try:
        approval = approval_store.reject(
            approval_id,
            approver_id=approver.approver_id,
            authorization_decision_id=authorization.decision_id,
        )
    except ApprovalExpiredError as exc:
        await _record_expired_approval(
            approval=exc.approval,
            tool=tool_definition,
            authorization=authorization,
        )
        raise

    audit_fields = _approval_audit_fields(approval, tool_definition)
    await audit_logger.log_event(
        event_type="approval_rejected",
        run_id=approval.run_id,
        approval_id=approval.approval_id,
        agent_id=approval.agent_id,
        actor=approver.approver_id,
        details={"reason": "human_rejected"},
        **audit_fields,
    )
    updated_action = execution_path_store.update_action(
        path_id=approval.path_id,
        action_id=approval.path_action_id,
        execution_outcome=PathActionOutcome.rejected,
        approval_status=approval.status.value,
        approver_id=approval.authorized_approver_id,
        approval_authorization_decision_id=(
            approval.approval_authorization_decision_id
        ),
    )
    await _log_path_action_updated(
        action=updated_action,
        agent_id=approval.agent_id,
        path_id=approval.path_id,
        approval_id=approval.approval_id,
    )
    await audit_logger.log_event(
        event_type="run_failed",
        run_id=approval.run_id,
        approval_id=approval.approval_id,
        agent_id=approval.agent_id,
        actor="system",
        details={"reason": "approval_rejected"},
        **audit_fields,
    )
    return ApprovalActionResponse(
        status="rejected",
        run_id=approval.run_id,
        approval_id=approval.approval_id,
        agent_id=approval.agent_id,
        policy_decision_id=approval.policy_decision_id,
        approver_id=approver.approver_id,
        approval_authorization_decision_id=authorization.decision_id,
        path_id=approval.path_id,
        path_action_id=approval.path_action_id,
        reason="Approval rejected. Tool execution was stopped.",
    )


async def _replay_execution_receipt(
    *,
    approval: ApprovalRecord,
    receipt: ExecutionReceipt,
    authorization: ApprovalAuthorizationDecision,
) -> ApprovalActionResponse:
    audit_fields = _approval_audit_fields(approval, receipt=receipt)
    audit_fields.update(
        {
            "approver_id": authorization.approver_id,
            "approval_authorization_decision_id": authorization.decision_id,
        }
    )
    await audit_logger.log_event(
        event_type="approval_execution_replayed",
        run_id=approval.run_id,
        approval_id=approval.approval_id,
        agent_id=approval.agent_id,
        actor=authorization.approver_id,
        details={
            "receipt_status": receipt.status.value,
            "attempt_number": receipt.attempt_number,
            "idempotency_key_fingerprint": receipt.idempotency_key_fingerprint,
        },
        **audit_fields,
    )
    return _approval_response_from_receipt(
        approval=approval,
        receipt=receipt,
        idempotent_replay=True,
    )


async def _authorize_approval_action(
    *,
    approval: ApprovalRecord,
    approver: ApproverIdentity,
    action: ApprovalAction,
) -> ApprovalAuthorizationDecision:
    decision = evaluate_approval_authorization(
        approver=approver,
        action=action,
        requester_id=approval.requester_id,
        agent_id=approval.agent_id,
        tool_name=approval.tool_name,
        request_risk_level=approval.request_risk_level,
    )
    audit_fields = _approval_audit_fields(approval)
    audit_fields.update(
        {
            "approver_id": approver.approver_id,
            "approval_authorization_decision_id": decision.decision_id,
        }
    )
    await audit_logger.log_event(
        event_type=(
            "approval_authorization_granted"
            if decision.allowed
            else "approval_authorization_denied"
        ),
        run_id=approval.run_id,
        approval_id=approval.approval_id,
        agent_id=approval.agent_id,
        actor=approver.approver_id,
        details={
            **decision.model_dump(mode="json"),
            "approver_role": approver.role.value,
            "requester_id": approval.requester_id,
            "requester_identity_verified": False,
            "tool_name": approval.tool_name,
            "request_risk_level": approval.request_risk_level,
        },
        **audit_fields,
    )
    if not decision.allowed:
        raise ApprovalAuthorizationError(decision)
    return decision


async def _record_expired_approval(
    *,
    approval: ApprovalRecord,
    tool: ToolDefinition,
    authorization: ApprovalAuthorizationDecision,
) -> None:
    audit_fields = _approval_audit_fields(approval, tool)
    audit_fields.update(
        {
            "approver_id": authorization.approver_id,
            "approval_authorization_decision_id": authorization.decision_id,
        }
    )
    updated_action = execution_path_store.update_action(
        path_id=approval.path_id,
        action_id=approval.path_action_id,
        execution_outcome=PathActionOutcome.expired,
        approval_status=approval.status.value,
        approver_id=authorization.approver_id,
        approval_authorization_decision_id=authorization.decision_id,
    )
    await _log_path_action_updated(
        action=updated_action,
        agent_id=approval.agent_id,
        path_id=approval.path_id,
        approval_id=approval.approval_id,
    )
    await audit_logger.log_event(
        event_type="approval_expired",
        run_id=approval.run_id,
        approval_id=approval.approval_id,
        agent_id=approval.agent_id,
        actor=authorization.approver_id,
        details={
            "status": approval.status.value,
            "expires_at": approval.expires_at,
        },
        **audit_fields,
    )
    await audit_logger.log_event(
        event_type="run_failed",
        run_id=approval.run_id,
        approval_id=approval.approval_id,
        agent_id=approval.agent_id,
        actor="system",
        details={"reason": "approval_expired"},
        **audit_fields,
    )


async def _log_execution_receipt(
    *,
    approval: ApprovalRecord,
    receipt: ExecutionReceipt,
    tool: ToolDefinition,
) -> None:
    await audit_logger.log_event(
        event_type="execution_receipt_recorded",
        run_id=approval.run_id,
        approval_id=approval.approval_id,
        agent_id=approval.agent_id,
        actor="approval-store",
        details=receipt.model_dump(mode="json"),
        **_approval_audit_fields(approval, tool, receipt),
    )


def _approval_response_from_receipt(
    *,
    approval: ApprovalRecord,
    receipt: ExecutionReceipt,
    idempotent_replay: bool,
) -> ApprovalActionResponse:
    succeeded = receipt.status == ExecutionReceiptStatus.succeeded
    return ApprovalActionResponse(
        status="executed" if succeeded else "execution_failed",
        run_id=approval.run_id,
        approval_id=approval.approval_id,
        agent_id=approval.agent_id,
        policy_decision_id=approval.policy_decision_id,
        approver_id=receipt.approver_id,
        approval_authorization_decision_id=receipt.approval_authorization_decision_id,
        path_id=approval.path_id,
        path_action_id=approval.path_action_id,
        execution_receipt=receipt,
        idempotent_replay=idempotent_replay,
        retryable=receipt.retryable,
        tool_result=receipt.result,
        reason=receipt.error_message if not succeeded else None,
    )


async def _record_path_action(
    *,
    path_context: ExecutionPathContext,
    action_id: str,
    run_id: str,
    tool: ToolDefinition,
    request_risk_level: str,
    execution_outcome: PathActionOutcome,
    decision: Optional[PolicyDecision] = None,
    approval_id: Optional[str] = None,
    approval_status: Optional[str] = None,
) -> PathActionRecord:
    now = _utc_now()
    action = PathActionRecord(
        action_id=action_id,
        run_id=run_id,
        tool_name=tool.name,
        tool_version=tool.version,
        tool_risk_class=tool.risk_class.value,
        request_risk_level=request_risk_level,
        policy_decision_id=decision.decision_id if decision else None,
        policy_outcome=decision.outcome.value if decision else None,
        approval_id=approval_id,
        approval_status=approval_status,
        execution_outcome=execution_outcome,
        recorded_at=now,
        updated_at=now,
    )
    execution_path_store.append_action(path_id=path_context.path_id, action=action)
    await audit_logger.log_event(
        event_type="path_action_recorded",
        run_id=run_id,
        approval_id=approval_id,
        agent_id=path_context.agent_id,
        policy_decision_id=decision.decision_id if decision else None,
        tool_name=tool.name,
        tool_version=tool.version,
        path_id=path_context.path_id,
        path_action_id=action_id,
        actor="execution-path-store",
        details=action.model_dump(mode="json"),
    )
    return action


async def _log_path_action_updated(
    *,
    action: PathActionRecord,
    agent_id: str,
    path_id: str,
    approval_id: Optional[str],
    execution_receipt_id: Optional[str] = None,
) -> None:
    await audit_logger.log_event(
        event_type="path_action_updated",
        run_id=action.run_id,
        approval_id=approval_id,
        agent_id=agent_id,
        policy_decision_id=action.policy_decision_id,
        tool_name=action.tool_name,
        tool_version=action.tool_version,
        path_id=path_id,
        path_action_id=action.action_id,
        execution_receipt_id=execution_receipt_id,
        approver_id=action.approver_id,
        approval_authorization_decision_id=(
            action.approval_authorization_decision_id
        ),
        actor="execution-path-store",
        details=action.model_dump(mode="json"),
    )


async def _log_tool_executed(
    *,
    run_id: str,
    agent_id: str,
    path_id: str,
    path_action_id: str,
    decision: PolicyDecision,
    tool: ToolDefinition,
    result: Dict[str, Any],
    approval_id: Optional[str] = None,
) -> None:
    await audit_logger.log_event(
        event_type="tool_executed",
        run_id=run_id,
        approval_id=approval_id,
        agent_id=agent_id,
        policy_decision_id=decision.decision_id,
        tool_name=tool.name,
        tool_version=tool.version,
        path_id=path_id,
        path_action_id=path_action_id,
        actor="system",
        details={"result": result},
    )


def _tool_audit_fields(tool: ToolDefinition) -> Dict[str, str]:
    return {"tool_name": tool.name, "tool_version": tool.version}


def _approval_audit_fields(
    approval: Any,
    tool: Optional[ToolDefinition] = None,
    receipt: Optional[ExecutionReceipt] = None,
) -> Dict[str, Any]:
    fields: Dict[str, Any] = {
        "policy_decision_id": approval.policy_decision_id,
        "tool_name": approval.tool_name,
        "tool_version": approval.tool_version,
        "path_id": approval.path_id,
        "path_action_id": approval.path_action_id,
    }
    approver_id = (
        receipt.approver_id if receipt is not None else approval.authorized_approver_id
    )
    authorization_decision_id = (
        receipt.approval_authorization_decision_id
        if receipt is not None
        else approval.approval_authorization_decision_id
    )
    if approver_id is not None:
        fields["approver_id"] = approver_id
    if authorization_decision_id is not None:
        fields["approval_authorization_decision_id"] = authorization_decision_id
    if receipt is not None:
        fields["execution_receipt_id"] = receipt.receipt_id
    return fields


def _classify_tool_failure(exc: Exception) -> tuple[str, bool]:
    if isinstance(exc, ToolExecutionError):
        return exc.code, exc.retryable
    return "unexpected_tool_execution_error", False


def _format_validation_errors(exc: ValidationError) -> List[Dict[str, Any]]:
    formatted_errors: List[Dict[str, Any]] = []
    for error in exc.errors():
        formatted_errors.append(
            {
                "loc": list(error.get("loc", [])),
                "msg": error.get("msg", ""),
                "type": error.get("type", ""),
            }
        )
    return formatted_errors


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
