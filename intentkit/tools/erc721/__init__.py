"""ERC721 NFT tools."""

from typing import TypedDict

from intentkit.tools.base import ToolsetConfig, ToolState
from intentkit.tools.erc721.base import ERC721BaseTool
from intentkit.tools.erc721.get_balance import ERC721GetBalance
from intentkit.tools.erc721.mint import ERC721Mint
from intentkit.tools.erc721.transfer import ERC721Transfer


class ToolStates(TypedDict):
    erc721_get_balance: ToolState
    erc721_mint: ToolState
    erc721_transfer: ToolState


class Config(ToolsetConfig):
    """Configuration for ERC721 tools."""

    states: ToolStates


# Cache for tool instances
_cache: dict[str, ERC721BaseTool] = {
    "erc721_get_balance": ERC721GetBalance(),
    "erc721_mint": ERC721Mint(),
    "erc721_transfer": ERC721Transfer(),
}


async def get_tools(
    config: Config,
    is_private: bool,
    **_,
) -> list[ERC721BaseTool]:
    """Get all enabled ERC721 tools.

    Args:
        config: The configuration for ERC721 tools.
        is_private: Whether to include private tools.

    Returns:
        A list of enabled ERC721 tools.
    """
    tools: list[ERC721BaseTool] = []

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

    ERC721 tools are available for any EVM-compatible wallet (CDP, Safe/Privy).
    They don't require specific CDP credentials since they work with any wallet.
    """
    return True
