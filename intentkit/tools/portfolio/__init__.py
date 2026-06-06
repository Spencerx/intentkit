"""Portfolio tools for blockchain wallet analysis."""

import logging
from typing import TypedDict

from intentkit.config.config import config as system_config
from intentkit.tools.base import ToolsetConfig, ToolState
from intentkit.tools.portfolio.base import PortfolioBaseTool
from intentkit.tools.portfolio.token_balances import TokenBalances
from intentkit.tools.portfolio.wallet_approvals import WalletApprovals
from intentkit.tools.portfolio.wallet_defi_positions import WalletDefiPositions
from intentkit.tools.portfolio.wallet_history import WalletHistory
from intentkit.tools.portfolio.wallet_net_worth import WalletNetWorth
from intentkit.tools.portfolio.wallet_nfts import WalletNFTs
from intentkit.tools.portfolio.wallet_profitability import WalletProfitability
from intentkit.tools.portfolio.wallet_profitability_summary import (
    WalletProfitabilitySummary,
)
from intentkit.tools.portfolio.wallet_stats import WalletStats
from intentkit.tools.portfolio.wallet_swaps import WalletSwaps

# Cache tools at the system level, because they are stateless
_cache: dict[str, PortfolioBaseTool] = {}

logger = logging.getLogger(__name__)


class ToolStates(TypedDict):
    """State configurations for Portfolio tools."""

    wallet_history: ToolState
    token_balances: ToolState
    wallet_approvals: ToolState
    wallet_swaps: ToolState
    wallet_net_worth: ToolState
    wallet_profitability_summary: ToolState
    wallet_profitability: ToolState
    wallet_stats: ToolState
    wallet_defi_positions: ToolState
    wallet_nfts: ToolState


class Config(ToolsetConfig):
    """Configuration for Portfolio blockchain analysis tools."""

    states: ToolStates


async def get_tools(
    config: "Config",
    is_private: bool,
    **_,
) -> list[PortfolioBaseTool]:
    """Get all Portfolio blockchain analysis tools.

    Args:
        config: The configuration for Portfolio tools.
        is_private: Whether to include private tools.

    Returns:
        A list of Portfolio blockchain analysis tools.
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
        tool = get_portfolio_tool(name)
        if tool:
            result.append(tool)
    return result


def get_portfolio_tool(
    name: str,
) -> PortfolioBaseTool | None:
    """Get a portfolio tool by name."""
    if name == "wallet_history":
        if name not in _cache:
            _cache[name] = WalletHistory()
        return _cache[name]
    elif name == "token_balances":
        if name not in _cache:
            _cache[name] = TokenBalances()
        return _cache[name]
    elif name == "wallet_approvals":
        if name not in _cache:
            _cache[name] = WalletApprovals()
        return _cache[name]
    elif name == "wallet_swaps":
        if name not in _cache:
            _cache[name] = WalletSwaps()
        return _cache[name]
    elif name == "wallet_net_worth":
        if name not in _cache:
            _cache[name] = WalletNetWorth()
        return _cache[name]
    elif name == "wallet_profitability_summary":
        if name not in _cache:
            _cache[name] = WalletProfitabilitySummary()
        return _cache[name]
    elif name == "wallet_profitability":
        if name not in _cache:
            _cache[name] = WalletProfitability()
        return _cache[name]
    elif name == "wallet_stats":
        if name not in _cache:
            _cache[name] = WalletStats()
        return _cache[name]
    elif name == "wallet_defi_positions":
        if name not in _cache:
            _cache[name] = WalletDefiPositions()
        return _cache[name]
    elif name == "wallet_nfts":
        if name not in _cache:
            _cache[name] = WalletNFTs()
        return _cache[name]
    else:
        logger.warning("Unknown portfolio tool: %s", name)
        return None


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return bool(system_config.moralis_api_key)
