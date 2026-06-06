"""DappLooker tools for crypto market data and analytics."""

import logging
from typing import TypedDict

from intentkit.config.config import config as system_config
from intentkit.tools.base import ToolsetConfig, ToolState
from intentkit.tools.dapplooker.base import DappLookerBaseTool
from intentkit.tools.dapplooker.dapplooker_token_data import DappLookerTokenData

# Cache tools at the system level, because they are stateless
_cache: dict[str, DappLookerBaseTool] = {}

logger = logging.getLogger(__name__)


class ToolStates(TypedDict):
    dapplooker_token_data: ToolState


class Config(ToolsetConfig):
    """Configuration for DappLooker tools."""

    states: ToolStates


async def get_tools(
    config: "Config",
    is_private: bool,
    **_,
) -> list[DappLookerBaseTool]:
    """Get all DappLooker tools.

    Args:
        config: The configuration for DappLooker tools.
        is_private: Whether to include private tools.

    Returns:
        A list of DappLooker tools.
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
        tool = get_dapplooker_tool(name)
        if tool:
            result.append(tool)
    return result


def get_dapplooker_tool(
    name: str,
) -> DappLookerBaseTool | None:
    """Get a DappLooker tool by name.

    Args:
        name: The name of the tool to get

    Returns:
        The requested DappLooker tool
    """
    if name == "dapplooker_token_data":
        if name not in _cache:
            _cache[name] = DappLookerTokenData()
        return _cache[name]
    else:
        logger.warning("Unknown DappLooker tool: %s", name)
        return None


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return bool(system_config.dapplooker_api_key)
