import asyncio

from app.api.schemas import AgentPlan


async def create_plan(task: str, risk_level: str) -> AgentPlan:
    """Mock a model planning call without requiring an API key."""
    await asyncio.sleep(0.01)
    normalized_task = task.lower()

    if "invalid" in normalized_task:
        return AgentPlan(
            tool_name="send_external_message",
            arguments={"recipient": "not-an-email", "message": "Invalid recipient demo"},
            reason="The task asks for an external message, but includes intentionally invalid input.",
        )

    if risk_level == "high" or "external" in normalized_task or "email" in normalized_task or "send" in normalized_task:
        return AgentPlan(
            tool_name="send_external_message",
            arguments={
                "recipient": "external@example.com",
                "message": f"Governed agent draft: {task}",
            },
            reason="External communication is a high-risk action and must be reviewed.",
        )

    if "policy" in normalized_task or "rule" in normalized_task or "governance" in normalized_task:
        return AgentPlan(
            tool_name="lookup_policy",
            arguments={"topic": "agent tool approvals"},
            reason="The user is asking for policy guidance rather than an action.",
        )

    return AgentPlan(
        tool_name="create_action_item",
        arguments={
            "title": "Review project risk",
            "description": task,
            "owner": "demo-user",
        },
        reason="The user requested a safe internal follow-up task.",
    )
