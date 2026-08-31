import os
from pathlib import Path

from pydantic import BaseModel, Field


def _approval_ttl_from_environment() -> int:
    return int(os.getenv("APPROVAL_TTL_SECONDS", "900"))


def _credential_from_environment(name: str, default: str) -> str:
    return os.getenv(name, default)


class Settings(BaseModel):
    app_name: str = "Agent Governance MVP"
    audit_log_path: Path = Path("app/storage/audit_log.jsonl")
    approval_ttl_seconds: int = Field(
        default_factory=_approval_ttl_from_environment,
        ge=1,
        le=86400,
    )
    demo_approver_token: str = Field(
        default_factory=lambda: _credential_from_environment(
            "DEMO_APPROVER_TOKEN",
            "local-demo-approver-token-change-me",
        ),
        min_length=16,
    )
    limited_approver_token: str = Field(
        default_factory=lambda: _credential_from_environment(
            "LIMITED_APPROVER_TOKEN",
            "local-limited-approver-token-change-me",
        ),
        min_length=16,
    )
    governance_admin_token: str = Field(
        default_factory=lambda: _credential_from_environment(
            "GOVERNANCE_ADMIN_TOKEN",
            "local-governance-admin-token-change-me",
        ),
        min_length=16,
    )
    audit_observer_token: str = Field(
        default_factory=lambda: _credential_from_environment(
            "AUDIT_OBSERVER_TOKEN",
            "local-audit-observer-token-change-me",
        ),
        min_length=16,
    )


settings = Settings()
