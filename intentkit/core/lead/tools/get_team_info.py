"""Tool to get team info and members."""

from __future__ import annotations

from typing import Any, override

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.core.lead.service import get_team_with_members
from intentkit.core.lead.tools.base import LeadTool
from intentkit.tools.base import NoArgsSchema


class GetTeamInfoOutput(BaseModel):
    """Output model for get_team_info tool."""

    team: dict[str, Any] = Field(description="Team info with members")


class GetTeamInfo(LeadTool):
    """Tool to get team info and members."""

    name: str = "lead_get_team_info"
    description: str = (
        "Get team information including name, avatar, all members with their roles, "
        "and public-agent quota usage (max allowed and current count)."
    )
    args_schema: ArgsSchema | None = NoArgsSchema

    @override
    async def _arun(self, **kwargs: Any) -> GetTeamInfoOutput:
        context = self.get_context()
        assert context.team_id is not None
        team_info = await get_team_with_members(context.team_id)
        return GetTeamInfoOutput(team=team_info)


get_team_info_tool = GetTeamInfo()
