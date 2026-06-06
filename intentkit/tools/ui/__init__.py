"""UI tools."""

import logging
from typing import TypedDict

from intentkit.tools.base import ToolsetConfig, ToolState
from intentkit.tools.ui.ask_user import UIAskUser
from intentkit.tools.ui.base import UIBaseTool
from intentkit.tools.ui.show_card import UIShowCard

# Cache tools at the module level, because they are stateless
_cache: dict[str, UIBaseTool] = {}

logger = logging.getLogger(__name__)


class ToolStates(TypedDict):
    ui_show_card: ToolState
    ui_ask_user: ToolState


class Config(ToolsetConfig):
    """Configuration for UI tools."""

    states: ToolStates


async def get_tools(
    config: "Config",
    is_private: bool,
    **_,
) -> list[UIBaseTool]:
    """Get all UI tools.

    Args:
        config: The configuration for UI tools.
        is_private: Whether to include private tools.

    Returns:
        A list of UI tools.
    """
    available_tools = []

    # Include tools based on their state
    for tool_name, state in config["states"].items():
        if state == "disabled":
            continue
        elif state == "public" or (state == "private" and is_private):
            available_tools.append(tool_name)

    # Get each tool using the cached getter
    result = []
    for name in available_tools:
        tool = get_ui_tool(name)
        if tool:
            result.append(tool)
    return result


def get_ui_tool(
    name: str,
) -> UIBaseTool | None:
    """Get a UI tool by name.

    Args:
        name: The name of the tool to get

    Returns:
        The requested UI tool
    """
    if name == "ui_show_card":
        if name not in _cache:
            _cache[name] = UIShowCard()
        return _cache[name]
    elif name == "ui_ask_user":
        if name not in _cache:
            _cache[name] = UIAskUser()
        return _cache[name]
    else:
        logger.warning("Unknown UI tool: %s", name)
        return None


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return True
