"""Elfa tools."""

import logging
from typing import TypedDict

from intentkit.config.config import config as system_config
from intentkit.tools.base import ToolsetConfig, ToolState
from intentkit.tools.elfa.base import ElfaBaseTool
from intentkit.tools.elfa.mention import (
    ElfaGetTopMentions,
    ElfaSearchMentions,
)
from intentkit.tools.elfa.stats import ElfaGetSmartStats
from intentkit.tools.elfa.tokens import ElfaGetTrendingTokens

# Cache tools at the system level, because they are stateless
_cache: dict[str, ElfaBaseTool] = {}

logger = logging.getLogger(__name__)


class ToolStates(TypedDict):
    get_top_mentions: ToolState
    search_mentions: ToolState
    get_trending_tokens: ToolState
    get_smart_stats: ToolState


class Config(ToolsetConfig):
    """Configuration for Elfa tools."""

    states: ToolStates


async def get_tools(
    config: "Config",
    is_private: bool,
    **_,
) -> list[ElfaBaseTool]:
    """Get all Elfa tools.

    Args:
        config: The configuration for Elfa tools.
        is_private: Whether to include private tools.

    Returns:
        A list of Elfa tools.
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
        tool = get_elfa_tool(name)
        if tool:
            result.append(tool)
    return result


def get_elfa_tool(
    name: str,
) -> ElfaBaseTool | None:
    """Get an Elfa tool by name.

    Args:
        name: The name of the tool to get

    Returns:
        The requested Elfa tool
    """

    if name == "get_top_mentions":
        if name not in _cache:
            _cache[name] = ElfaGetTopMentions()
        return _cache[name]

    elif name == "search_mentions":
        if name not in _cache:
            _cache[name] = ElfaSearchMentions()
        return _cache[name]

    elif name == "get_trending_tokens":
        if name not in _cache:
            _cache[name] = ElfaGetTrendingTokens()
        return _cache[name]

    elif name == "get_smart_stats":
        if name not in _cache:
            _cache[name] = ElfaGetSmartStats()
        return _cache[name]

    else:
        logger.warning("Unknown Elfa tool: %s", name)
        return None


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return bool(system_config.elfa_api_key)
