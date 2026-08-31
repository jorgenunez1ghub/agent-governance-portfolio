import asyncio
from typing import Any, Dict, List


async def retrieve_context(task: str, user_id: str) -> Dict[str, Any]:
    """Mock context retrieval for a local MVP."""
    await asyncio.sleep(0.01)
    snippets: List[str] = [
        "Safe internal tools may execute without human approval.",
        "External communications require explicit human approval before execution.",
        "Every governed run must write structured audit events.",
    ]

    return {
        "user_id": user_id,
        "task_excerpt": task[:160],
        "source": "mock_governance_context",
        "snippets": snippets,
    }
