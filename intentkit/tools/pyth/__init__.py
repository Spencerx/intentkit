"""Pyth price oracle tools."""

from typing import TypedDict

from intentkit.tools.base import ToolsetConfig, ToolState
from intentkit.tools.pyth.base import PythBaseTool
from intentkit.tools.pyth.fetch_price import PythFetchPrice
from intentkit.tools.pyth.fetch_price_feed import PythFetchPriceFeed


class ToolStates(TypedDict):
    pyth_fetch_price: ToolState
    pyth_fetch_price_feed: ToolState


class Config(ToolsetConfig):
    """Configuration for Pyth tools."""

    states: ToolStates


# Cache for stateless tools
_cache: dict[str, PythBaseTool] = {
    "pyth_fetch_price": PythFetchPrice(),
    "pyth_fetch_price_feed": PythFetchPriceFeed(),
}


async def get_tools(
    config: Config,
    is_private: bool,
    **_,
) -> list[PythBaseTool]:
    """Get all enabled Pyth tools.

    Args:
        config: The configuration for Pyth tools.
        is_private: Whether to include private tools.

    Returns:
        A list of enabled Pyth tools.
    """
    tools: list[PythBaseTool] = []

    for tool_name, state in config["states"].items():
        if state == "disabled":
            continue
        if state == "public" or (state == "private" and is_private):
            # Check cache first
            if tool_name in _cache:
                tools.append(_cache[tool_name])

    return tools


def available() -> bool:
    """Check if this toolset is available based on system config.

    Pyth tools only require HTTP access to the Pyth Hermes API,
    so they are always available.
    """
    return True
