"""Tool to delete a team autonomous task."""

from __future__ import annotations

from typing import Any, override

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.core.autonomous import delete_autonomous_task
from intentkit.core.lead.tools.base import LeadTool


class DeleteAutonomousTaskInput(BaseModel):
    """Input model for delete_autonomous_task tool."""

    task_id: str = Field(
        description="The unique identifier of the autonomous task to delete"
    )


class DeleteAutonomousTaskOutput(BaseModel):
    """Output model for delete_autonomous_task tool."""

    success: bool = Field(
        description="Whether the task was successfully deleted", default=True
    )
    message: str = Field(description="Confirmation message about the deletion")


class LeadDeleteAutonomousTask(LeadTool):
    """Tool to delete a team autonomous task."""

    name: str = "lead_delete_autonomous_task"
    description: str = (
        "Delete a team autonomous task. Requires the task_id to identify which "
        "task to remove."
    )
    args_schema: ArgsSchema | None = DeleteAutonomousTaskInput

    @override
    async def _arun(
        self,
        task_id: str,
        **kwargs: Any,
    ) -> DeleteAutonomousTaskOutput:
        context = self.get_context()
        assert context.team_id is not None
        await delete_autonomous_task(context.team_id, task_id)
        return DeleteAutonomousTaskOutput(
            success=True, message=f"Successfully deleted autonomous task {task_id}"
        )


lead_delete_autonomous_task_tool = LeadDeleteAutonomousTask()
