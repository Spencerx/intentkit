"""Token tools for blockchain token analysis."""

import logging
from typing import TypedDict

from intentkit.config.config import config as system_config
from intentkit.tools.base import ToolsetConfig, ToolState
from intentkit.tools.token.base import TokenBaseTool
from intentkit.tools.token.erc20_transfers import ERC20Transfers
from intentkit.tools.token.token_analytics import TokenAnalytics
from intentkit.tools.token.token_price import TokenPrice
from intentkit.tools.token.token_search import TokenSearch

# Cache tools at the system level, because they are stateless
_cache: dict[str, TokenBaseTool] = {}

logger = logging.getLogger(__name__)


class ToolStates(TypedDict):
    """State configurations for Token tools."""

    token_price: ToolState
    token_erc20_transfers: ToolState
    token_search: ToolState
    token_analytics: ToolState


class Config(ToolsetConfig):
    """Configuration for Token blockchain analysis tools."""

    states: ToolStates


async def get_tools(
    config: "Config",
    is_private: bool,
    **_,
) -> list[TokenBaseTool]:
    """Get all Token blockchain analysis tools.

    Args:
        config: The configuration for Token tools.
        is_private: Whether to include private tools.

    Returns:
        A list of Token blockchain analysis tools.
    """
    if "states" not in config:
        logger.error("No 'states' field in config")  # pyright: ignore[reportUnreachable]
        return []

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
        tool = get_token_tool(name)
        if tool:
            result.append(tool)

    return result


def get_token_tool(
    name: str,
) -> TokenBaseTool | None:
    """Get a Token blockchain analysis tool by name.

    Args:
        name: The name of the tool to get

    Returns:
        The requested Token blockchain analysis tool
    """
    if name in _cache:
        return _cache[name]

    tool = None
    if name == "token_price":
        tool = TokenPrice()
    elif name == "token_erc20_transfers":
        tool = ERC20Transfers()
    elif name == "token_search":
        tool = TokenSearch()
    elif name == "token_analytics":
        tool = TokenAnalytics()
    else:
        logger.warning("Unknown Token tool: %s", name)
        return None

    if tool:
        _cache[name] = tool

    return tool


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return bool(system_config.moralis_api_key)
