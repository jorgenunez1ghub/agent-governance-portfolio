import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict

from app.config import settings

AUDIT_EVENT_TYPES = {
    "run_started",
    "context_retrieved",
    "plan_created",
    "tool_selected",
    "tool_validation_passed",
    "tool_validation_failed",
    "policy_evaluated",
    "approval_required",
    "approval_authentication_failed",
    "approval_authorization_granted",
    "approval_authorization_denied",
    "approval_approved",
    "approval_rejected",
    "approval_expired",
    "approval_execution_started",
    "approval_execution_replayed",
    "approval_execution_failed",
    "execution_receipt_recorded",
    "tool_executed",
    "run_completed",
    "run_denied",
    "run_failed",
    "path_action_recorded",
    "path_action_updated",
}


class AuditEvent(BaseModel):
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


class JsonlAuditLogger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def configure_path(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    async def log_event(
        self,
        event_type: str,
        actor: str,
        details: Dict[str, Any],
        run_id: Optional[str] = None,
        approval_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        policy_decision_id: Optional[str] = None,
        tool_name: Optional[str] = None,
        tool_version: Optional[str] = None,
        path_id: Optional[str] = None,
        path_action_id: Optional[str] = None,
        execution_receipt_id: Optional[str] = None,
        approver_id: Optional[str] = None,
        approval_authorization_decision_id: Optional[str] = None,
    ) -> AuditEvent:
        if event_type not in AUDIT_EVENT_TYPES:
            raise ValueError(f"Unsupported audit event type: {event_type}")

        event = AuditEvent(
            timestamp=_utc_now(),
            event_type=event_type,
            actor=actor,
            details=details,
            run_id=run_id,
            approval_id=approval_id,
            agent_id=agent_id,
            policy_decision_id=policy_decision_id,
            tool_name=tool_name,
            tool_version=tool_version,
            path_id=path_id,
            path_action_id=path_action_id,
            execution_receipt_id=execution_receipt_id,
            approver_id=approver_id,
            approval_authorization_decision_id=(
                approval_authorization_decision_id
            ),
        )
        # File writes are delegated to a worker thread so the async API path stays non-blocking.
        await asyncio.to_thread(self._append_event, event)
        return event

    async def recent_events(self, limit: int = 25) -> List[Dict[str, Any]]:
        return await asyncio.to_thread(self._recent_events, limit)

    def _append_event(self, event: AuditEvent) -> None:
        with self.path.open("a", encoding="utf-8") as file:
            file.write(event.model_dump_json() + "\n")

    def _recent_events(self, limit: int) -> List[Dict[str, Any]]:
        if not self.path.exists():
            return []

        events: List[Dict[str, Any]] = []
        with self.path.open("r", encoding="utf-8") as file:
            lines = [line.strip() for line in file.readlines() if line.strip()]

        for line in lines[-limit:]:
            events.append(json.loads(line))
        return events


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


audit_logger = JsonlAuditLogger(settings.audit_log_path)
