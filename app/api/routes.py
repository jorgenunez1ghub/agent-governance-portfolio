from typing import List, Optional

from fastapi import APIRouter, Header, HTTPException, Query, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.agent.runtime import approve_approval, reject_approval, run_agent
from app.api.schemas import (
    AgentRunRequest,
    AgentRunResponse,
    ApprovalActionResponse,
    ApprovalDetailResponse,
    AuditEventResponse,
    ExecutionPathResponse,
    ToolMetadataResponse,
)
from app.audit.logger import audit_logger
from app.governance.approvals import (
    ApprovalExpiredError,
    ApprovalNotFoundError,
    ApprovalTransitionError,
    approval_store,
)
from app.governance.approvers import (
    ApprovalAuthorizationError,
    ApproverAuthenticationError,
    ApproverIdentity,
    approver_registry,
)
from app.governance.identity import AgentIdentity, agent_registry
from app.governance.path import (
    ExecutionPathAgentMismatchError,
    ExecutionPathNotFoundError,
    execution_path_store,
)
from app.tools.registry import tool_registry

router = APIRouter()
approver_bearer = HTTPBearer(auto_error=False)


@router.post("/agent/run", response_model=AgentRunResponse)
async def run_agent_endpoint(request: AgentRunRequest) -> AgentRunResponse:
    try:
        return await run_agent(request)
    except ExecutionPathNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ExecutionPathAgentMismatchError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/approvals/{approval_id}/approve", response_model=ApprovalActionResponse)
async def approve_endpoint(
    approval_id: str,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(approver_bearer),
    idempotency_key: Optional[str] = Header(
        default=None,
        alias="Idempotency-Key",
        min_length=1,
        max_length=200,
    ),
) -> ApprovalActionResponse:
    approver = await _authenticate_approver(approval_id, credentials)
    try:
        return await approve_approval(
            approval_id,
            approver=approver,
            idempotency_key=idempotency_key,
        )
    except ApprovalNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ApprovalAuthorizationError as exc:
        raise HTTPException(
            status_code=403,
            detail={
                "message": str(exc),
                "reason_codes": list(exc.decision.reason_codes),
                "authorization_decision_id": exc.decision.decision_id,
            },
        ) from exc
    except ApprovalExpiredError as exc:
        raise HTTPException(status_code=410, detail=str(exc)) from exc
    except ApprovalTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/approvals/{approval_id}/reject", response_model=ApprovalActionResponse)
async def reject_endpoint(
    approval_id: str,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(approver_bearer),
) -> ApprovalActionResponse:
    approver = await _authenticate_approver(approval_id, credentials)
    try:
        return await reject_approval(approval_id, approver=approver)
    except ApprovalNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ApprovalAuthorizationError as exc:
        raise HTTPException(
            status_code=403,
            detail={
                "message": str(exc),
                "reason_codes": list(exc.decision.reason_codes),
                "authorization_decision_id": exc.decision.decision_id,
            },
        ) from exc
    except ApprovalExpiredError as exc:
        raise HTTPException(status_code=410, detail=str(exc)) from exc
    except ApprovalTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit/recent", response_model=List[AuditEventResponse])
async def recent_audit_events(
    limit: int = Query(default=25, ge=1, le=100),
) -> List[AuditEventResponse]:
    return await audit_logger.recent_events(limit=limit)


@router.get("/governance/agents", response_model=List[AgentIdentity])
async def list_agent_identities() -> List[AgentIdentity]:
    return agent_registry.list_agents()


@router.get("/governance/approvers", response_model=List[ApproverIdentity])
async def list_approver_identities() -> List[ApproverIdentity]:
    return approver_registry.list_approvers()


@router.get("/governance/tools", response_model=List[ToolMetadataResponse])
async def list_tool_metadata() -> List[ToolMetadataResponse]:
    return [
        ToolMetadataResponse(
            name=tool.name,
            description=tool.description,
            version=tool.version,
            owner=tool.owner,
            source=tool.source,
            risk_class=tool.risk_class.value,
            provenance_status=tool.provenance_status.value,
        )
        for tool in tool_registry.list_tools()
    ]


@router.get("/governance/paths/{path_id}", response_model=ExecutionPathResponse)
async def get_execution_path(path_id: str) -> ExecutionPathResponse:
    try:
        path = execution_path_store.get(path_id)
        return ExecutionPathResponse.model_validate(path.model_dump())
    except ExecutionPathNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/governance/approvals/{approval_id}",
    response_model=ApprovalDetailResponse,
)
async def get_approval_detail(approval_id: str) -> ApprovalDetailResponse:
    try:
        approval = approval_store.get(approval_id)
        return ApprovalDetailResponse(
            approval=approval,
            execution_receipts=approval_store.list_receipts(approval_id),
        )
    except ApprovalNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


async def _authenticate_approver(
    approval_id: str,
    credentials: Optional[HTTPAuthorizationCredentials],
) -> ApproverIdentity:
    try:
        if credentials is None or credentials.scheme.lower() != "bearer":
            raise ApproverAuthenticationError("Missing approver bearer credential.")
        return approver_registry.authenticate(credentials.credentials)
    except ApproverAuthenticationError as exc:
        await audit_logger.log_event(
            event_type="approval_authentication_failed",
            approval_id=approval_id,
            actor="anonymous",
            details={
                "reason_code": "approver_authentication_failed",
                "credential_exposed": False,
            },
        )
        raise HTTPException(
            status_code=401,
            detail="Valid approver bearer authentication is required.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
