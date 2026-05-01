"""Skill for the manager agent to publish (or republish) the active agent."""

from __future__ import annotations

import json
from typing import Any, override

from langchain_core.tools import ArgsSchema

from intentkit.core.agent.publish import publish_agent
from intentkit.core.manager.service import get_latest_public_info
from intentkit.core.manager.skills.base import ManagerSkill
from intentkit.models.agent import AgentPublicInfo, AgentPublishInput
from intentkit.utils.error import IntentKitAPIError
from intentkit.utils.schema import resolve_schema_refs


class PublishAgentSkill(ManagerSkill):
    """Skill to publish the active agent to public via the four-field form."""

    name: str = "publish_agent"
    description: str = (
        "Publish the current agent to public, or update its public listing. "
        "Collects the four fields shown in the publish form: description, "
        "example_intro, examples (1-6 prompts with name/description/prompt), "
        "and tags (0-3 from the predefined category list). The platform fixes "
        "fee_percentage at 1 and leaves all other public-info fields untouched. "
        "If the team has reached its public_agent_limit and the agent is not "
        "already public, this fails — check lead_get_team_info first."
    )
    args_schema: ArgsSchema | None = {
        "type": "object",
        "properties": {
            "publish_input": resolve_schema_refs(AgentPublishInput.model_json_schema()),
        },
        "required": ["publish_input"],
        "additionalProperties": False,
    }

    @override
    async def _arun(self, **kwargs: Any) -> str:
        context = self.get_context()
        if not context.user_id:
            raise ValueError("User identifier missing from context")

        if "publish_input" not in kwargs:
            raise ValueError("Missing required argument 'publish_input'")

        # Mirrors UpdatePublicInfoSkill: confirm ownership before mutating.
        try:
            await get_latest_public_info(
                agent_id=context.agent_id,
                user_id=context.user_id,
            )
        except IntentKitAPIError as exc:
            if exc.key == "AgentNotFound":
                return (
                    "Agent not found. Only deployed agents owned by the current "
                    "user can be published."
                )
            raise

        publish_input = AgentPublishInput.model_validate(kwargs["publish_input"])

        try:
            updated_agent = await publish_agent(
                agent_id=context.agent_id,
                public_info=publish_input.to_public_info(),
            )
        except IntentKitAPIError as exc:
            if exc.key == "PublicAgentLimitReached":
                return (
                    "Cannot publish: the team has reached its public-agent limit. "
                    "Ask the user to unpublish another agent first, or to upgrade "
                    "the team's quota."
                )
            if exc.key == "AgentHasNoTeam":
                return (
                    "Cannot publish: this agent is not owned by a team. Only "
                    "team-owned agents can be published."
                )
            raise

        return json.dumps(
            AgentPublicInfo.model_validate(updated_agent).model_dump(mode="json"),
            indent=2,
        )


publish_agent_skill = PublishAgentSkill()
