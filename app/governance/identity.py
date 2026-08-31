from enum import Enum
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field


class AutonomyLevel(str, Enum):
    read_only = "read_only"
    supervised = "supervised"


class AgentIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: str = Field(min_length=1, max_length=80)
    owner: str = Field(min_length=1, max_length=120)
    purpose: str = Field(min_length=1, max_length=500)
    autonomy_level: AutonomyLevel
    allowed_tools: Tuple[str, ...]


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: Dict[str, AgentIdentity] = {}

    def register(self, agent: AgentIdentity) -> None:
        self._agents[agent.agent_id] = agent

    def find(self, agent_id: str) -> Optional[AgentIdentity]:
        return self._agents.get(agent_id)

    def list_agents(self) -> List[AgentIdentity]:
        return list(self._agents.values())


agent_registry = AgentRegistry()
agent_registry.register(
    AgentIdentity(
        agent_id="demo-agent",
        owner="agent-governance-team",
        purpose="Demonstrate governed internal and external tool execution.",
        autonomy_level=AutonomyLevel.supervised,
        allowed_tools=("create_action_item", "lookup_policy", "send_external_message"),
    )
)
agent_registry.register(
    AgentIdentity(
        agent_id="read-only-agent",
        owner="agent-governance-team",
        purpose="Demonstrate an agent restricted to policy lookup.",
        autonomy_level=AutonomyLevel.read_only,
        allowed_tools=("lookup_policy",),
    )
)
