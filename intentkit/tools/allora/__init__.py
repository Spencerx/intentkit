"""Allora tool module."""

import logging
from typing import TypedDict

from intentkit.config.config import config as system_config
from intentkit.tools.allora.base import AlloraBaseTool
from intentkit.tools.allora.price import AlloraGetPrice
from intentkit.tools.base import ToolsetConfig, ToolState

# Cache tools at the system level, because they are stateless
_cache: dict[str, AlloraBaseTool] = {}

logger = logging.getLogger(__name__)


class ToolStates(TypedDict):
    get_price_prediction: ToolState


class Config(ToolsetConfig):
    """Configuration for Allora tools."""

    states: ToolStates


async def get_tools(
    config: "Config",
    is_private: bool,
    **_,
) -> list[AlloraBaseTool]:
    """Get all Allora tools.

    Args:
        config: The configuration for Allora tools.
        is_private: Whether to include private tools.

    Returns:
        A list of Allora tools.
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
        tool = get_allora_tool(name)
        if tool:
            result.append(tool)
    return result


def get_allora_tool(
    name: str,
) -> AlloraBaseTool | None:
    """Get an Allora tool by name.

    Args:
        name: The name of the tool to get

    Returns:
        The requested Allora tool
    """
    if name == "get_price_prediction":
        if name not in _cache:
            _cache[name] = AlloraGetPrice()
        return _cache[name]
    else:
        logger.warning("Unknown Allora tool: %s", name)
        return None


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return bool(system_config.allora_api_key)
