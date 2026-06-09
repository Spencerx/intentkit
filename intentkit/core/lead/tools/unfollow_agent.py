"""Tool to unfollow an agent the team currently follows."""

from __future__ import annotations

from typing import override

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.core.lead.tools.base import LeadTool


class UnfollowAgentInput(BaseModel):
    """Input model for unfollow_agent tool."""

    agent_id: str = Field(
        description="ID or slug of the agent to unfollow. "
        "Use lead_list_public_agents to see which agents are followed."
    )


class UnfollowAgentOutput(BaseModel):
    """Output model for unfollow_agent tool."""

    agent_id: str = Field(description="Resolved ID of the unfollowed agent")
    message: str = Field(description="Human-readable confirmation")


class LeadUnfollowAgent(LeadTool):
    """Unfollow an agent so it is no longer available to the lead."""

    name: str = "lead_unfollow_agent"
    description: str = (
        "Unfollow an agent (by ID or slug) the team currently follows. The "
        "agent is removed from the lead's system prompt and its posts and "
        "activities stop appearing in the team feed. Has no effect on the "
        "team's own agents."
    )
    args_schema: ArgsSchema | None = UnfollowAgentInput

    @override
    async def _arun(self, agent_id: str) -> UnfollowAgentOutput:
        from intentkit.core.agent.queries import get_agent_by_id_or_slug
        from intentkit.core.lead.cache import invalidate_lead_cache
        from intentkit.core.team import unsubscribe_agent

        context = self.get_context()
        assert context.team_id is not None

        # Resolve slug -> id when possible; fall back to the raw value so a
        # subscription to a since-deleted agent can still be cleared by ID.
        resolved = await get_agent_by_id_or_slug(agent_id)

        # Guard the team's own agents: they are auto-subscribed for the content
        # feed, and unsubscribing would delete their feed history. This tool is
        # only for unfollowing external public agents.
        if resolved and resolved.team_id == context.team_id:
            raise ToolException(
                f"'{agent_id}' is one of your own team's agents and cannot be "
                "unfollowed."
            )

        resolved_id = resolved.id if resolved else agent_id

        await unsubscribe_agent(context.team_id, resolved_id)

        # Drop the cached lead executor so the next turn rebuilds the system
        # prompt without the unfollowed agent.
        invalidate_lead_cache(context.team_id)

        return UnfollowAgentOutput(
            agent_id=resolved_id,
            message=f"No longer following '{resolved_id}'.",
        )


lead_unfollow_agent_tool = LeadUnfollowAgent()
