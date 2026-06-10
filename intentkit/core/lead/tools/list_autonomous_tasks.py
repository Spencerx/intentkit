"""Tool to list the team's autonomous tasks."""

from __future__ import annotations

from typing import Any, override

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.core.autonomous import list_team_autonomous_tasks
from intentkit.core.lead.tools.base import LeadTool
from intentkit.models.autonomous import AutonomousTask


class ListAutonomousTasksInput(BaseModel):
    """Input model for list_autonomous_tasks tool."""


class ListAutonomousTasksOutput(BaseModel):
    """Output model for list_autonomous_tasks tool."""

    tasks: list[AutonomousTask] = Field(
        description="List of the team's autonomous task configurations"
    )


class LeadListAutonomousTasks(LeadTool):
    """Tool to list all autonomous tasks of the team."""

    name: str = "lead_list_autonomous_tasks"
    description: str = (
        "List all autonomous tasks of the team. Returns details about each task "
        "including scheduling, prompts, target agent, and status."
    )
    args_schema: ArgsSchema | None = ListAutonomousTasksInput

    @override
    async def _arun(self, **kwargs: Any) -> ListAutonomousTasksOutput:
        context = self.get_context()
        assert context.team_id is not None
        tasks = await list_team_autonomous_tasks(context.team_id)
        return ListAutonomousTasksOutput(tasks=tasks)


lead_list_autonomous_tasks_tool = LeadListAutonomousTasks()
