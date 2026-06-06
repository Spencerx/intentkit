"""CryptoCompare tools."""

import logging
from typing import TypedDict

from intentkit.config.config import config as system_config
from intentkit.tools.base import ToolsetConfig, ToolState
from intentkit.tools.cryptocompare.base import CryptoCompareBaseTool
from intentkit.tools.cryptocompare.fetch_news import CryptoCompareFetchNews
from intentkit.tools.cryptocompare.fetch_price import CryptoCompareFetchPrice
from intentkit.tools.cryptocompare.fetch_top_exchanges import (
    CryptoCompareFetchTopExchanges,
)
from intentkit.tools.cryptocompare.fetch_top_market_cap import (
    CryptoCompareFetchTopMarketCap,
)
from intentkit.tools.cryptocompare.fetch_top_volume import CryptoCompareFetchTopVolume
from intentkit.tools.cryptocompare.fetch_trading_signals import (
    CryptoCompareFetchTradingSignals,
)

# Cache tools at the system level, because they are stateless
_cache: dict[str, CryptoCompareBaseTool] = {}

logger = logging.getLogger(__name__)


class ToolStates(TypedDict):
    fetch_news: ToolState
    fetch_price: ToolState
    fetch_trading_signals: ToolState
    fetch_top_market_cap: ToolState
    fetch_top_exchanges: ToolState
    fetch_top_volume: ToolState


class Config(ToolsetConfig):
    """Configuration for CryptoCompare tools."""

    states: ToolStates


async def get_tools(
    config: "Config",
    is_private: bool,
    **_,
) -> list[CryptoCompareBaseTool]:
    """Get all CryptoCompare tools.

    Args:
        config: The configuration for CryptoCompare tools.
        is_private: Whether to include private tools.

    Returns:
        A list of CryptoCompare tools.
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
        tool = get_cryptocompare_tool(name)
        if tool:
            result.append(tool)
    return result


def get_cryptocompare_tool(
    name: str,
) -> CryptoCompareBaseTool | None:
    """Get a CryptoCompare tool by name.

    Args:
        name: The name of the tool to get

    Returns:
        The requested CryptoCompare tool
    """

    if name == "fetch_news":
        if name not in _cache:
            _cache[name] = CryptoCompareFetchNews()
        return _cache[name]
    elif name == "fetch_price":
        if name not in _cache:
            _cache[name] = CryptoCompareFetchPrice()
        return _cache[name]
    elif name == "fetch_trading_signals":
        if name not in _cache:
            _cache[name] = CryptoCompareFetchTradingSignals()
        return _cache[name]
    elif name == "fetch_top_market_cap":
        if name not in _cache:
            _cache[name] = CryptoCompareFetchTopMarketCap()
        return _cache[name]
    elif name == "fetch_top_exchanges":
        if name not in _cache:
            _cache[name] = CryptoCompareFetchTopExchanges()
        return _cache[name]
    elif name == "fetch_top_volume":
        if name not in _cache:
            _cache[name] = CryptoCompareFetchTopVolume()
        return _cache[name]
    else:
        logger.warning("Unknown CryptoCompare tool: %s", name)
        return None


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return bool(system_config.cryptocompare_api_key)
