import logging
from typing import TypedDict

from intentkit.tools.base import ToolsetConfig, ToolState
from intentkit.tools.dexscreener.base import DexScreenerBaseTool
from intentkit.tools.dexscreener.get_pair_info import GetPairInfo
from intentkit.tools.dexscreener.get_token_pairs import GetTokenPairs
from intentkit.tools.dexscreener.get_tokens_info import GetTokensInfo
from intentkit.tools.dexscreener.search_token import SearchToken

# Cache tools at the system level, because they are stateless
_cache: dict[str, DexScreenerBaseTool] = {}

logger = logging.getLogger(__name__)


class ToolStates(TypedDict):
    search_token: ToolState
    get_pair_info: ToolState
    get_token_pairs: ToolState
    get_tokens_info: ToolState


_TOOL_NAME_TO_CLASS_MAP: dict[str, type[DexScreenerBaseTool]] = {
    "search_token": SearchToken,
    "get_pair_info": GetPairInfo,
    "get_token_pairs": GetTokenPairs,
    "get_tokens_info": GetTokensInfo,
}


class Config(ToolsetConfig):
    """Configuration for DexScreener tools."""

    enabled: bool
    states: ToolStates


async def get_tools(
    config: "Config",
    is_private: bool,
    **_,
) -> list[DexScreenerBaseTool]:
    """Get all DexScreener tools.

    Args:
        config: The configuration for DexScreener tools.
        is_private: Whether to include private tools.

    Returns:
        A list of DexScreener tools.
    """

    available_tools = []

    # Include tools based on their state
    for tool_name, state in config["states"].items():
        if state == "disabled":
            continue
        elif state == "public" or (state == "private" and is_private):
            available_tools.append(tool_name)

    logger.debug("Available Tools %s", available_tools)
    logger.debug("Hardcoded Tools %s", _TOOL_NAME_TO_CLASS_MAP)

    # Get each tool using the cached getter
    result = []
    for name in available_tools:
        tool = get_dexscreener_tools(name)
        if tool:
            result.append(tool)
    return result


def get_dexscreener_tools(
    name: str,
) -> DexScreenerBaseTool | None:
    """Get a DexScreener tool by name.

    Args:
        name: The name of the tool to get

    Returns:
        The requested DexScreener tool
    """

    # Return from cache immediately if already exists
    if name in _cache:
        return _cache[name]

    tool_class = _TOOL_NAME_TO_CLASS_MAP.get(name)
    if not tool_class:
        logger.warning("Unknown Dexscreener tool: %s", name)
        return None

    _cache[name] = tool_class()  # pyright: ignore[reportCallIssue]
    return _cache[name]


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return True
