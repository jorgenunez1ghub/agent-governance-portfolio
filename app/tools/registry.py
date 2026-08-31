from dataclasses import dataclass
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Type

from pydantic import BaseModel

from app.tools.mock_tools import create_action_item, lookup_policy, send_external_message
from app.tools.schemas import CreateActionItemInput, LookupPolicyInput, SendExternalMessageInput

ToolHandler = Callable[[BaseModel], Awaitable[Dict[str, Any]]]


class ToolRiskClass(str, Enum):
    read_only = "read_only"
    internal_write = "internal_write"
    external_write = "external_write"


class ToolProvenanceStatus(str, Enum):
    trusted = "trusted"
    unverified = "unverified"
    blocked = "blocked"


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_model: Type[BaseModel]
    handler: ToolHandler
    version: str
    owner: str
    source: str
    risk_class: ToolRiskClass
    provenance_status: ToolProvenanceStatus

    @property
    def approval_required(self) -> bool:
        """Compatibility helper for Milestone 1.5 callers."""
        return self.risk_class == ToolRiskClass.external_write


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        self._tools[tool.name] = tool

    def get_tool(self, tool_name: str) -> ToolDefinition:
        try:
            return self._tools[tool_name]
        except KeyError as exc:
            raise KeyError(f"Unknown tool: {tool_name}") from exc

    def list_tools(self) -> List[ToolDefinition]:
        return list(self._tools.values())

    def validate_tool_input(self, tool_name: str, arguments: Dict[str, Any]) -> BaseModel:
        # The planner proposes arguments, but the backend validates them before any policy or execution step.
        tool = self.get_tool(tool_name)
        return tool.input_model.model_validate(arguments)

    async def execute_validated_tool(self, tool_name: str, validated_input: BaseModel) -> Dict[str, Any]:
        tool = self.get_tool(tool_name)
        return await tool.handler(validated_input)


tool_registry = ToolRegistry()
tool_registry.register(
    ToolDefinition(
        name="create_action_item",
        description="Creates a mock internal action item.",
        input_model=CreateActionItemInput,
        handler=create_action_item,
        version="1.0.0",
        owner="agent-governance-team",
        source="local_builtin",
        risk_class=ToolRiskClass.internal_write,
        provenance_status=ToolProvenanceStatus.trusted,
    )
)
tool_registry.register(
    ToolDefinition(
        name="lookup_policy",
        description="Looks up a mock governance policy.",
        input_model=LookupPolicyInput,
        handler=lookup_policy,
        version="1.0.0",
        owner="agent-governance-team",
        source="local_builtin",
        risk_class=ToolRiskClass.read_only,
        provenance_status=ToolProvenanceStatus.trusted,
    )
)
tool_registry.register(
    ToolDefinition(
        name="send_external_message",
        description="Simulates sending a message outside the system.",
        input_model=SendExternalMessageInput,
        handler=send_external_message,
        version="1.0.0",
        owner="agent-governance-team",
        source="local_builtin",
        risk_class=ToolRiskClass.external_write,
        provenance_status=ToolProvenanceStatus.trusted,
    )
)
