from typing import Any, override

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.core.autonomous import list_autonomous_tasks
from intentkit.core.manager.tools.base import ManagerTool
from intentkit.models.agent import AgentAutonomous


class ListAutonomousTasksInput(BaseModel):
    """Input model for list_autonomous_tasks tool."""

    pass


class ListAutonomousTasksOutput(BaseModel):
    """Output model for list_autonomous_tasks tool."""

    tasks: list[AgentAutonomous] = Field(
        description="List of autonomous task configurations for the agent"
    )


class ListAutonomousTasks(ManagerTool):
    """Tool to list all autonomous tasks for an agent."""

    name: str = "system_list_autonomous_tasks"
    description: str = (
        "List all autonomous task configurations for the agent. "
        "Returns details about each task including scheduling, prompts, and status."
    )
    args_schema: ArgsSchema | None = ListAutonomousTasksInput

    @override
    async def _arun(
        self,
        **kwargs: Any,
    ) -> ListAutonomousTasksOutput:
        """List autonomous tasks for the agent.

        Args:
            config: Runtime configuration containing agent context

        Returns:
            ListAutonomousTasksOutput: List of autonomous tasks
        """
        context = self.get_context()
        agent = context.agent

        tasks = await list_autonomous_tasks(agent.id)

        return ListAutonomousTasksOutput(tasks=tasks)


# Shared tool instances
list_autonomous_tasks_tool = ListAutonomousTasks()
