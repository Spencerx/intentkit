"""Tool to list available tools for agent configuration."""

from __future__ import annotations

import asyncio
from typing import Any, override

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.core.lead.tools.base import LeadTool
from intentkit.tools.base import NoArgsSchema


class ListAvailableToolsOutput(BaseModel):
    """Output model for list_available_tools tool."""

    tools_text: str = Field(
        description="Hierarchical text listing all available tools by category"
    )


class LeadListAvailableTools(LeadTool):
    """Tool to list all available tools organized by category."""

    name: str = "lead_list_available_tools"
    description: str = (
        "List all available tools organized by category. "
        "Returns tool names, descriptions, and category groupings "
        "for configuring agents."
    )
    args_schema: ArgsSchema | None = NoArgsSchema

    @override
    async def _arun(self, **kwargs: Any) -> ListAvailableToolsOutput:
        from intentkit.core.manager.service import get_tools_hierarchical_text

        tools_text = await asyncio.to_thread(get_tools_hierarchical_text)
        return ListAvailableToolsOutput(tools_text=tools_text)


lead_list_available_tools_tool = LeadListAvailableTools()
