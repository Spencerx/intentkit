"""Publish / unpublish helpers for team-owned agents."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import delete, func, select

from intentkit.config.db import get_session
from intentkit.core.agent.public_info import apply_public_info_update
from intentkit.models.agent import AgentPublicInfo, AgentTable
from intentkit.models.agent.core import AgentVisibility
from intentkit.models.team import TeamTable
from intentkit.models.team_feed import TeamSubscriptionTable
from intentkit.utils.error import IntentKitAPIError

if TYPE_CHECKING:
    from intentkit.models.agent import Agent


async def publish_agent(*, agent_id: str, public_info: AgentPublicInfo) -> "Agent":
    """Mark an agent as public after merging in the supplied public info.

    Enforces the owning team's ``public_agent_limit`` before flipping
    visibility. Only fields explicitly provided in ``public_info`` are written
    so callers can update a single field (matches ``update_public_info``).

    Raises:
        IntentKitAPIError 404: agent missing.
        IntentKitAPIError 400: agent has no team_id (cannot enforce limit).
        IntentKitAPIError 403: team has reached its public_agent_limit.
    """
    from intentkit.models.agent import Agent

    async with get_session() as session:
        result = await session.execute(
            select(AgentTable).where(AgentTable.id == agent_id)
        )
        db_agent = result.scalar_one_or_none()
        if not db_agent:
            raise IntentKitAPIError(404, "NotFound", f"Agent {agent_id} not found")

        if not db_agent.team_id:
            raise IntentKitAPIError(
                400,
                "AgentHasNoTeam",
                "Only team-owned agents can be published",
            )

        # Re-publishing an already public agent is allowed and bypasses the
        # quota check so operators can update public_info without losing
        # access to their own existing slot.
        is_already_public = (
            db_agent.visibility is not None
            and db_agent.visibility >= AgentVisibility.PUBLIC
        )

        if not is_already_public:
            # SELECT FOR UPDATE on the team row serializes concurrent publishes
            # against the same team so the limit can't be exceeded by a race
            # between two simultaneous quota checks.
            team = await session.get(TeamTable, db_agent.team_id, with_for_update=True)
            if team is None:
                raise IntentKitAPIError(
                    404, "TeamNotFound", f"Team {db_agent.team_id} not found"
                )

            current_public_count = (
                await session.scalar(
                    select(func.count(AgentTable.id)).where(
                        AgentTable.team_id == db_agent.team_id,
                        AgentTable.visibility >= AgentVisibility.PUBLIC,
                        AgentTable.archived_at.is_(None),
                    )
                )
                or 0
            )

            if current_public_count >= team.public_agent_limit:
                raise IntentKitAPIError(
                    403,
                    "PublicAgentLimitReached",
                    f"Team has reached its public agent limit ({team.public_agent_limit})",
                )

        apply_public_info_update(db_agent, public_info)
        db_agent.visibility = AgentVisibility.PUBLIC

        await session.commit()
        await session.refresh(db_agent)

        return Agent.model_validate(db_agent)


async def unpublish_agent(*, agent_id: str) -> "Agent":
    """Flip an agent back to TEAM visibility and clear its subscriptions.

    Activity / post feed rows are intentionally retained. Only the
    ``team_subscriptions`` rows are cleared so the agent stops appearing on
    subscriber timelines going forward.

    Raises:
        IntentKitAPIError 404: agent missing.
    """
    from intentkit.models.agent import Agent

    async with get_session() as session:
        result = await session.execute(
            select(AgentTable).where(AgentTable.id == agent_id)
        )
        db_agent = result.scalar_one_or_none()
        if not db_agent:
            raise IntentKitAPIError(404, "NotFound", f"Agent {agent_id} not found")

        db_agent.visibility = AgentVisibility.TEAM

        await session.execute(
            delete(TeamSubscriptionTable).where(
                TeamSubscriptionTable.agent_id == agent_id
            )
        )

        await session.commit()
        await session.refresh(db_agent)

        return Agent.model_validate(db_agent)
