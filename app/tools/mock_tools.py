import asyncio
import uuid
from typing import Any, Dict

from app.tools.schemas import CreateActionItemInput, LookupPolicyInput, SendExternalMessageInput


async def create_action_item(input_data: CreateActionItemInput) -> Dict[str, Any]:
    await asyncio.sleep(0.01)
    return {
        "action_item_id": str(uuid.uuid4()),
        "title": input_data.title,
        "owner": input_data.owner,
        "status": "created",
    }


async def lookup_policy(input_data: LookupPolicyInput) -> Dict[str, Any]:
    await asyncio.sleep(0.01)
    return {
        "policy_id": "policy-agent-tool-approval",
        "topic": input_data.topic,
        "summary": "External actions require human approval. Read-only and internal safe tools do not.",
        "approval_required": False,
    }


async def send_external_message(input_data: SendExternalMessageInput) -> Dict[str, Any]:
    await asyncio.sleep(0.01)
    return {
        "message_id": str(uuid.uuid4()),
        "recipient": input_data.recipient,
        "channel": input_data.channel,
        "status": "simulated_sent",
    }
