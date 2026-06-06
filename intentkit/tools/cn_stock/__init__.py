"""Chinese A-share market data tools (akshare-backed)."""

import logging
from typing import TypedDict

from intentkit.tools.base import ToolsetConfig, ToolState
from intentkit.tools.cn_stock.base import CNStockBaseTool
from intentkit.tools.cn_stock.get_announcement import GetAnnouncement
from intentkit.tools.cn_stock.get_board import GetBoard
from intentkit.tools.cn_stock.get_capital_flow import GetCapitalFlow
from intentkit.tools.cn_stock.get_financials import GetFinancials
from intentkit.tools.cn_stock.get_index import GetIndex
from intentkit.tools.cn_stock.get_kline import GetKLine
from intentkit.tools.cn_stock.get_news import GetNews
from intentkit.tools.cn_stock.get_quote import GetQuote
from intentkit.tools.cn_stock.is_trading_day import IsTradingDay

logger = logging.getLogger(__name__)


class ToolStates(TypedDict, total=False):
    get_quote: ToolState
    get_kline: ToolState
    get_index: ToolState
    get_board: ToolState
    get_capital_flow: ToolState
    get_news: ToolState
    get_announcement: ToolState
    get_financials: ToolState
    is_trading_day: ToolState


class Config(ToolsetConfig):
    """Configuration for cn_stock tools."""

    states: ToolStates


# Tool instances are stateless across calls; build once at import and reuse.
_TOOLS: dict[str, CNStockBaseTool] = {
    "get_quote": GetQuote(),
    "get_kline": GetKLine(),
    "get_index": GetIndex(),
    "get_board": GetBoard(),
    "get_capital_flow": GetCapitalFlow(),
    "get_news": GetNews(),
    "get_announcement": GetAnnouncement(),
    "get_financials": GetFinancials(),
    "is_trading_day": IsTradingDay(),
}


async def get_tools(
    config: "Config",
    is_private: bool,
    **_,
) -> list[CNStockBaseTool]:
    available: list[CNStockBaseTool] = []
    for name, state in config["states"].items():
        if state == "disabled":
            continue
        if state == "private" and not is_private:
            continue
        tool = _TOOLS.get(name)
        if tool is None:
            logger.warning("Unknown cn_stock tool: %s", name)
            continue
        available.append(tool)
    return available
