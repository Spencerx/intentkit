"""Polymarket prediction market tools."""

import logging
from typing import TypedDict

from intentkit.tools.base import ToolsetConfig, ToolState
from intentkit.tools.polymarket.base import PolymarketBaseTool
from intentkit.tools.polymarket.cancel_order import CancelOrder
from intentkit.tools.polymarket.get_market import GetMarket
from intentkit.tools.polymarket.get_orderbook import GetOrderbook
from intentkit.tools.polymarket.get_orders import GetOrders
from intentkit.tools.polymarket.get_positions import GetPositions
from intentkit.tools.polymarket.get_price_history import GetPriceHistory
from intentkit.tools.polymarket.get_trades import GetTrades
from intentkit.tools.polymarket.place_order import PlaceOrder
from intentkit.tools.polymarket.search_markets import SearchMarkets

# Cache tools at the system level, because they are stateless
_cache: dict[str, PolymarketBaseTool] = {}

logger = logging.getLogger(__name__)


class ToolStates(TypedDict):
    search_markets: ToolState
    get_market: ToolState
    get_orderbook: ToolState
    get_price_history: ToolState
    place_order: ToolState
    cancel_order: ToolState
    get_positions: ToolState
    get_orders: ToolState
    get_trades: ToolState


_TOOL_NAME_TO_CLASS_MAP: dict[str, type[PolymarketBaseTool]] = {
    "search_markets": SearchMarkets,
    "get_market": GetMarket,
    "get_orderbook": GetOrderbook,
    "get_price_history": GetPriceHistory,
    "place_order": PlaceOrder,
    "cancel_order": CancelOrder,
    "get_positions": GetPositions,
    "get_orders": GetOrders,
    "get_trades": GetTrades,
}


class Config(ToolsetConfig):
    """Configuration for Polymarket tools."""

    enabled: bool
    states: ToolStates


async def get_tools(
    config: "Config",
    is_private: bool,
    **_,
) -> list[PolymarketBaseTool]:
    """Get all Polymarket tools based on config.

    Args:
        config: The configuration for Polymarket tools.
        is_private: Whether to include private tools.

    Returns:
        A list of Polymarket tools.
    """
    available_tools = []

    for tool_name, state in config["states"].items():
        if state == "disabled":
            continue
        elif state == "public" or (state == "private" and is_private):
            available_tools.append(tool_name)

    logger.debug("Available Polymarket tools: %s", available_tools)

    result = []
    for name in available_tools:
        tool = _get_tool(name)
        if tool:
            result.append(tool)
    return result


def _get_tool(name: str) -> PolymarketBaseTool | None:
    """Get a Polymarket tool by name, with caching."""
    if name in _cache:
        return _cache[name]

    tool_class = _TOOL_NAME_TO_CLASS_MAP.get(name)
    if not tool_class:
        logger.warning("Unknown Polymarket tool: %s", name)
        return None

    _cache[name] = tool_class()  # pyright: ignore[reportCallIssue]
    return _cache[name]


def available() -> bool:
    """Check if Polymarket tools are available.

    Always returns True since public tools need no API keys.
    Authenticated tools check wallet at runtime.
    """
    return True
