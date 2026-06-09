"""Tool to follow a public agent so the lead can delegate to it."""

from __future__ import annotations

from typing import override

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.core.lead.tools.base import LeadTool
from intentkit.utils.error import IntentKitAPIError


class FollowAgentInput(BaseModel):
    """Input model for follow_agent tool."""

    agent_id: str = Field(
        description="ID or slug of the public agent to follow. "
        "Use lead_list_public_agents to discover agents."
    )


class FollowAgentOutput(BaseModel):
    """Output model for follow_agent tool."""

    agent_id: str = Field(description="Resolved ID of the followed agent")
    name: str | None = Field(default=None, description="Name of the followed agent")
    message: str = Field(description="Human-readable confirmation")


class LeadFollowAgent(LeadTool):
    """Follow a public agent so the lead can delegate to it like a team agent."""

    name: str = "lead_follow_agent"
    description: str = (
        "Follow a public agent (by ID or slug) so it becomes available to the "
        "lead for delegation, just like a team agent. Followed agents are "
        "injected into the lead's system prompt and can be called via "
        "lead_call_agent. Following also brings the agent's posts and "
        "activities into the team feed."
    )
    args_schema: ArgsSchema | None = FollowAgentInput

    @override
    async def _arun(self, agent_id: str) -> FollowAgentOutput:
        from intentkit.core.agent.queries import get_agent_by_id_or_slug
        from intentkit.core.lead.cache import invalidate_lead_cache
        from intentkit.core.team import subscribe_agent

        context = self.get_context()
        assert context.team_id is not None

        resolved = await get_agent_by_id_or_slug(agent_id)
        if not resolved:
            raise ToolException(f"Agent '{agent_id}' not found")

        try:
            await subscribe_agent(context.team_id, resolved.id)
        except IntentKitAPIError as e:
            raise ToolException(e.message) from e

        # Drop the cached lead executor so the next turn rebuilds the system
        # prompt with the newly followed agent in the "Followed Agents" section.
        invalidate_lead_cache(context.team_id)

        return FollowAgentOutput(
            agent_id=resolved.id,
            name=resolved.name,
            message=(
                f"Now following '{resolved.name or resolved.id}'. "
                "You can delegate to it via lead_call_agent."
            ),
        )


lead_follow_agent_tool = LeadFollowAgent()
