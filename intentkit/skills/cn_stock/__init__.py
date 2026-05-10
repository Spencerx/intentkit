"""Chinese A-share market data skills (akshare-backed)."""

import logging
from typing import TypedDict

from intentkit.skills.base import SkillConfig, SkillState
from intentkit.skills.cn_stock.base import CNStockBaseTool
from intentkit.skills.cn_stock.get_announcement import GetAnnouncement
from intentkit.skills.cn_stock.get_board import GetBoard
from intentkit.skills.cn_stock.get_capital_flow import GetCapitalFlow
from intentkit.skills.cn_stock.get_financials import GetFinancials
from intentkit.skills.cn_stock.get_index import GetIndex
from intentkit.skills.cn_stock.get_kline import GetKLine
from intentkit.skills.cn_stock.get_news import GetNews
from intentkit.skills.cn_stock.get_quote import GetQuote
from intentkit.skills.cn_stock.is_trading_day import IsTradingDay

logger = logging.getLogger(__name__)


class SkillStates(TypedDict, total=False):
    get_quote: SkillState
    get_kline: SkillState
    get_index: SkillState
    get_board: SkillState
    get_capital_flow: SkillState
    get_news: SkillState
    get_announcement: SkillState
    get_financials: SkillState
    is_trading_day: SkillState


class Config(SkillConfig):
    """Configuration for cn_stock skills."""

    states: SkillStates


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


async def get_skills(
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
            logger.warning("Unknown cn_stock skill: %s", name)
            continue
        available.append(tool)
    return available
