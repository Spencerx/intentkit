"""Wallet Portfolio Tools for IntentKit."""

import logging
from typing import TypedDict

from intentkit.config.config import config as system_config
from intentkit.tools.base import ToolsetConfig, ToolState
from intentkit.tools.moralis.base import WalletBaseTool
from intentkit.tools.moralis.fetch_chain_portfolio import FetchChainPortfolio
from intentkit.tools.moralis.fetch_nft_portfolio import FetchNftPortfolio
from intentkit.tools.moralis.fetch_solana_portfolio import FetchSolanaPortfolio
from intentkit.tools.moralis.fetch_wallet_portfolio import FetchWalletPortfolio

logger = logging.getLogger(__name__)


class ToolStates(TypedDict):
    """Configuration of states for wallet tools."""

    fetch_wallet_portfolio: ToolState
    fetch_chain_portfolio: ToolState
    fetch_nft_portfolio: ToolState
    fetch_solana_portfolio: ToolState


class Config(ToolsetConfig):
    """Configuration for Wallet Portfolio tools."""

    states: ToolStates
    supported_chains: dict[str, bool]


async def get_tools(
    config: "Config",
    is_private: bool,
    **_,
) -> list[WalletBaseTool]:
    """Get all Wallet Portfolio tools.

    Args:
        config: Tool configuration
        is_private: Whether the request is from an authenticated user
        chain_provider: Optional chain provider for blockchain interactions
        **_: Additional arguments

    Returns:
        List of enabled wallet tools
    """
    available_tools = []

    # Include tools based on their state
    for tool_name, state in config["states"].items():
        if state == "disabled":
            continue
        elif state == "public" or (state == "private" and is_private):
            # Check chain support for Solana-specific tools
            if tool_name == "fetch_solana_portfolio" and not config.get(
                "supported_chains", {}
            ).get("solana", True):
                continue

            available_tools.append(tool_name)

    # Get each tool using the getter
    result = []
    for name in available_tools:
        tool = get_wallet_tool(name)
        if tool:
            result.append(tool)
    return result


def get_wallet_tool(
    name: str,
) -> WalletBaseTool | None:
    """Get a specific Wallet Portfolio tool by name.

    Args:
        name: Name of the tool to get

    Returns:
        The requested tool
    """
    tool_classes = {
        "fetch_wallet_portfolio": FetchWalletPortfolio,
        "fetch_chain_portfolio": FetchChainPortfolio,
        "fetch_nft_portfolio": FetchNftPortfolio,
        "fetch_solana_portfolio": FetchSolanaPortfolio,
    }

    if name not in tool_classes:
        logger.warning("Unknown Wallet Portfolio tool: %s", name)
        return None

    return tool_classes[name]()


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return bool(system_config.moralis_api_key)
