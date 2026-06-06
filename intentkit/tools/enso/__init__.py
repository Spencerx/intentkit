"""Enso tools."""

import logging
from typing import NotRequired, TypedDict

from intentkit.config.config import config as system_config
from intentkit.tools.base import ToolsetConfig, ToolState
from intentkit.tools.enso.base import EnsoBaseTool
from intentkit.tools.enso.best_yield import EnsoGetBestYield
from intentkit.tools.enso.networks import EnsoGetNetworks
from intentkit.tools.enso.prices import EnsoGetPrices
from intentkit.tools.enso.route import EnsoRouteShortcut
from intentkit.tools.enso.tokens import EnsoGetTokens
from intentkit.tools.enso.wallet import (
    EnsoGetWalletApprovals,
    EnsoGetWalletBalances,
    EnsoWalletApprove,
)

logger = logging.getLogger(__name__)


class ToolStates(TypedDict):
    get_networks: ToolState
    get_tokens: ToolState
    get_prices: ToolState
    get_wallet_approvals: ToolState
    get_wallet_balances: ToolState
    wallet_approve: ToolState
    route_shortcut: ToolState
    get_best_yield: ToolState


class Config(ToolsetConfig):
    """Configuration for Enso tools."""

    states: ToolStates
    api_token: NotRequired[str]
    main_tokens: NotRequired[list[str]]


async def get_tools(
    config: Config,
    is_private: bool,
    **_,
) -> list[EnsoBaseTool]:
    """Get all Enso tools."""
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
        tool = get_enso_tool(name)
        if tool:
            result.append(tool)
    return result


def get_enso_tool(
    name: str,
) -> EnsoBaseTool | None:
    """Get an Enso tool by name.

    Args:
        name: The name of the tool to get

    Returns:
        The requested Enso tool
    """
    if name == "get_networks":
        return EnsoGetNetworks()
    if name == "get_tokens":
        return EnsoGetTokens()
    if name == "get_prices":
        return EnsoGetPrices()
    if name == "get_wallet_approvals":
        return EnsoGetWalletApprovals()
    if name == "get_wallet_balances":
        return EnsoGetWalletBalances()
    if name == "wallet_approve":
        return EnsoWalletApprove()
    if name == "route_shortcut":
        return EnsoRouteShortcut()
    if name == "get_best_yield":
        return EnsoGetBestYield()
    else:
        logger.warning("Unknown Enso tool: %s", name)
        return None


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return bool(system_config.enso_api_token)
