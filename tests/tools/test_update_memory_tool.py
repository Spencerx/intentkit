"""Tests for the UpdateMemoryTool system tool."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.tools.base import ToolException

from intentkit.abstracts.graph import AgentContext
from intentkit.core.system_tools.update_memory import (
    UpdateMemoryInput,
    UpdateMemoryTool,
)


@pytest.fixture
def mock_runtime():
    """Fixture for mocked runtime context."""
    mock_context = MagicMock(spec=AgentContext)
    mock_context.agent_id = "test-agent-1"

    with patch("intentkit.core.system_tools.base.get_runtime") as mock_get_runtime:
        mock_get_runtime.return_value.context = mock_context
        yield mock_get_runtime


class TestUpdateMemoryInput:
    def test_valid_input(self):
        inp = UpdateMemoryInput(content="Remember this fact")
        assert inp.content == "Remember this fact"

    def test_content_required(self):
        with pytest.raises(Exception):
            UpdateMemoryInput()  # pyright: ignore[reportCallIssue]


class TestUpdateMemoryTool:
    def test_tool_metadata(self):
        tool = UpdateMemoryTool()
        assert tool.name == "update_memory"
        assert "memory" in tool.description.lower()

    @pytest.mark.asyncio
    async def test_successful_memory_update(self, mock_runtime):
        tool = UpdateMemoryTool()

        with patch(
            "intentkit.core.memory.update_memory",
            new_callable=AsyncMock,
            return_value="### Updated\n\nMerged memory content",
        ) as mock_update:
            result = await tool._arun(content="User prefers dark mode")

            mock_update.assert_called_once_with(
                "test-agent-1", "User prefers dark mode"
            )
            assert "Memory updated successfully" in result
            assert "Merged memory content" in result

    @pytest.mark.asyncio
    async def test_raises_tool_exception_on_error(self, mock_runtime):
        tool = UpdateMemoryTool()

        with patch(
            "intentkit.core.memory.update_memory",
            new_callable=AsyncMock,
            side_effect=Exception("DB connection failed"),
        ):
            with pytest.raises(ToolException, match="Failed to update memory"):
                await tool._arun(content="some content")

    @pytest.mark.asyncio
    async def test_reraises_tool_exception(self, mock_runtime):
        tool = UpdateMemoryTool()

        with patch(
            "intentkit.core.memory.update_memory",
            new_callable=AsyncMock,
            side_effect=ToolException("custom tool error"),
        ):
            with pytest.raises(ToolException, match="custom tool error"):
                await tool._arun(content="some content")
