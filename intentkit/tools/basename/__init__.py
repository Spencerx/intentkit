"""Basename tools for ENS-style domain registration on Base."""

from typing import TypedDict

from intentkit.config.config import config as system_config
from intentkit.tools.base import ToolsetConfig, ToolState
from intentkit.tools.basename.base import BasenameBaseTool
from intentkit.tools.basename.register import BasenameRegister


class ToolStates(TypedDict):
    basename_register_basename: ToolState


class Config(ToolsetConfig):
    """Configuration for Basename tools."""

    states: ToolStates


# Cache for tool instances
_cache: dict[str, BasenameBaseTool] = {
    "basename_register_basename": BasenameRegister(),
}


async def get_tools(
    config: "Config",
    is_private: bool,
    **_,
) -> list[BasenameBaseTool]:
    """Get all enabled Basename tools.

    Args:
        config: The configuration for Basename tools.
        is_private: Whether to include private tools.

    Returns:
        A list of enabled Basename tools.
    """
    tools: list[BasenameBaseTool] = []

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

    Basename tools require CDP credentials for wallet operations,
    or can work with Safe/Privy wallet providers.
    """
    # Basename works with any on-chain capable wallet
    # Check if we have at least CDP credentials configured
    has_cdp = all(
        [
            bool(system_config.cdp_api_key_id),
            bool(system_config.cdp_api_key_secret),
            bool(system_config.cdp_wallet_secret),
        ]
    )
    # Or Privy credentials
    has_privy = bool(system_config.privy_app_id) and bool(
        system_config.privy_app_secret
    )

    return has_cdp or has_privy
