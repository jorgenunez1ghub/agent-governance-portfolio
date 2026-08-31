import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field

RiskLevel = Literal["low", "medium", "high"]


class PathActionOutcome(str, Enum):
    validation_failed = "validation_failed"
    denied = "denied"
    approval_required = "approval_required"
    executed = "executed"
    rejected = "rejected"
    expired = "expired"
    execution_failed = "execution_failed"


class PathActionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_id: str
    run_id: str
    tool_name: str
    tool_version: str
    tool_risk_class: str
    request_risk_level: RiskLevel
    policy_decision_id: Optional[str] = None
    policy_outcome: Optional[str] = None
    approval_id: Optional[str] = None
    approval_status: Optional[str] = None
    approver_id: Optional[str] = None
    approval_authorization_decision_id: Optional[str] = None
    execution_outcome: PathActionOutcome
    recorded_at: str
    updated_at: str


class ExecutionPath(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path_id: str
    agent_id: str
    actions: List[PathActionRecord] = Field(default_factory=list)
    created_at: str
    updated_at: str


class ExecutionPathContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path_id: str
    agent_id: str
    actions: Tuple[PathActionRecord, ...] = ()

    @property
    def action_count(self) -> int:
        return len(self.actions)

    @property
    def has_adverse_outcome(self) -> bool:
        adverse_outcomes = {
            PathActionOutcome.validation_failed,
            PathActionOutcome.denied,
            PathActionOutcome.rejected,
            PathActionOutcome.expired,
            PathActionOutcome.execution_failed,
        }
        return any(action.execution_outcome in adverse_outcomes for action in self.actions)


class ExecutionPathNotFoundError(Exception):
    pass


class ExecutionPathAgentMismatchError(Exception):
    pass


class PathActionNotFoundError(Exception):
    pass


class InMemoryExecutionPathStore:
    def __init__(self) -> None:
        self._paths: Dict[str, ExecutionPath] = {}

    def resolve(self, *, path_id: Optional[str], agent_id: str) -> ExecutionPath:
        if path_id is None:
            return self.create(agent_id=agent_id)

        path = self.get(path_id)
        if path.agent_id != agent_id:
            raise ExecutionPathAgentMismatchError(
                f"Execution path {path_id} belongs to agent {path.agent_id}, not {agent_id}."
            )
        return path

    def create(self, *, agent_id: str) -> ExecutionPath:
        now = _utc_now()
        path = ExecutionPath(
            path_id=str(uuid.uuid4()),
            agent_id=agent_id,
            created_at=now,
            updated_at=now,
        )
        self._paths[path.path_id] = path
        return path

    def get(self, path_id: str) -> ExecutionPath:
        try:
            return self._paths[path_id]
        except KeyError as exc:
            raise ExecutionPathNotFoundError(f"Execution path not found: {path_id}") from exc

    def context(self, *, path_id: str, agent_id: str) -> ExecutionPathContext:
        path = self.resolve(path_id=path_id, agent_id=agent_id)
        return ExecutionPathContext(
            path_id=path.path_id,
            agent_id=path.agent_id,
            actions=tuple(path.actions),
        )

    def append_action(self, *, path_id: str, action: PathActionRecord) -> PathActionRecord:
        path = self.get(path_id)
        if any(existing.action_id == action.action_id for existing in path.actions):
            raise ValueError(f"Path action already exists: {action.action_id}")

        updated_path = path.model_copy(
            update={
                "actions": [*path.actions, action],
                "updated_at": _utc_now(),
            }
        )
        self._paths[path_id] = updated_path
        return action

    def update_action(
        self,
        *,
        path_id: str,
        action_id: str,
        execution_outcome: PathActionOutcome,
        approval_status: Optional[str],
        approver_id: Optional[str] = None,
        approval_authorization_decision_id: Optional[str] = None,
    ) -> PathActionRecord:
        path = self.get(path_id)
        updated_action: Optional[PathActionRecord] = None
        updated_actions: List[PathActionRecord] = []

        for action in path.actions:
            if action.action_id == action_id:
                updated_action = action.model_copy(
                    update={
                        "execution_outcome": execution_outcome,
                        "approval_status": approval_status,
                        "approver_id": approver_id,
                        "approval_authorization_decision_id": (
                            approval_authorization_decision_id
                        ),
                        "updated_at": _utc_now(),
                    }
                )
                updated_actions.append(updated_action)
            else:
                updated_actions.append(action)

        if updated_action is None:
            raise PathActionNotFoundError(
                f"Path action {action_id} was not found in execution path {path_id}."
            )

        self._paths[path_id] = path.model_copy(
            update={
                "actions": updated_actions,
                "updated_at": _utc_now(),
            }
        )
        return updated_action

    def reset(self) -> None:
        self._paths.clear()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


execution_path_store = InMemoryExecutionPathStore()
