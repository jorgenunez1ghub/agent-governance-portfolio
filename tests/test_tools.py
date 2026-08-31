import asyncio

import pytest
from pydantic import ValidationError

from app.tools.registry import tool_registry


def test_registry_contains_required_tools():
    tool_names = {tool.name for tool in tool_registry.list_tools()}

    assert "create_action_item" in tool_names
    assert "lookup_policy" in tool_names
    assert "send_external_message" in tool_names


def test_registered_tools_have_versioned_trusted_provenance():
    for tool in tool_registry.list_tools():
        assert tool.version == "1.0.0"
        assert tool.owner == "agent-governance-team"
        assert tool.source == "local_builtin"
        assert tool.provenance_status.value == "trusted"


def test_tool_input_validation_rejects_invalid_external_message():
    with pytest.raises(ValidationError):
        tool_registry.validate_tool_input(
            "send_external_message",
            {"recipient": "not-an-email", "message": "hello"},
        )


def test_lookup_policy_tool_executes_with_valid_input():
    validated = tool_registry.validate_tool_input("lookup_policy", {"topic": "approval policy"})
    result = asyncio.run(tool_registry.execute_validated_tool("lookup_policy", validated))

    assert result["policy_id"] == "policy-agent-tool-approval"
    assert result["approval_required"] is False
