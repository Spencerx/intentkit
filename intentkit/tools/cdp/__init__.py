"""CDP wallet interaction tools.

This module provides wallet tools that require a CDP wallet provider.
"""

from typing import TypedDict

from intentkit.tools.base import ToolsetConfig, ToolState
from intentkit.tools.cdp.base import CDPBaseTool
from intentkit.tools.cdp.get_balance import CDPGetBalance
from intentkit.tools.cdp.get_wallet_details import CDPGetWalletDetails
from intentkit.tools.cdp.native_transfer import CDPNativeTransfer


class ToolStates(TypedDict):
    cdp_get_balance: ToolState
    cdp_get_wallet_details: ToolState
    cdp_native_transfer: ToolState


class Config(ToolsetConfig):
    """Configuration for CDP tools."""

    states: ToolStates


# Cache for tool instances
_cache: dict[str, CDPBaseTool] = {
    "cdp_get_balance": CDPGetBalance(),
    "cdp_get_wallet_details": CDPGetWalletDetails(),
    "cdp_native_transfer": CDPNativeTransfer(),
}


async def get_tools(
    config: Config,
    is_private: bool,
    **_,
) -> list[CDPBaseTool]:
    """Get all enabled CDP tools.

    Args:
        config: The configuration for CDP tools.
        is_private: Whether to include private tools.

    Returns:
        A list of enabled CDP tools.
    """
    tools: list[CDPBaseTool] = []

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

    CDP wallet tools are globally available but require the agent's
    wallet provider to be configured as 'cdp'.
    """
    return True
