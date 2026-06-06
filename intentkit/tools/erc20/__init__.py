"""ERC20 token tools."""

from typing import TypedDict

from intentkit.tools.base import ToolsetConfig, ToolState
from intentkit.tools.erc20.base import ERC20BaseTool
from intentkit.tools.erc20.get_balance import ERC20GetBalance
from intentkit.tools.erc20.get_token_address import ERC20GetTokenAddress
from intentkit.tools.erc20.transfer import ERC20Transfer


class ToolStates(TypedDict):
    erc20_get_balance: ToolState
    erc20_transfer: ToolState
    erc20_get_token_address: ToolState


class Config(ToolsetConfig):
    """Configuration for ERC20 tools."""

    states: ToolStates


# Cache for tool instances
_cache: dict[str, ERC20BaseTool] = {
    "erc20_get_balance": ERC20GetBalance(),
    "erc20_transfer": ERC20Transfer(),
    "erc20_get_token_address": ERC20GetTokenAddress(),
}


async def get_tools(
    config: Config,
    is_private: bool,
    **_,
) -> list[ERC20BaseTool]:
    """Get all enabled ERC20 tools.

    Args:
        config: The configuration for ERC20 tools.
        is_private: Whether to include private tools.

    Returns:
        A list of enabled ERC20 tools.
    """
    tools: list[ERC20BaseTool] = []

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

    ERC20 tools are available for any EVM-compatible wallet (CDP, Safe/Privy).
    They don't require specific CDP credentials since they work with any wallet.
    """
    return True
