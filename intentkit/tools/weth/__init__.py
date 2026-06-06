"""WETH wrapping/unwrapping tools."""

from typing import TypedDict

from intentkit.tools.base import ToolsetConfig, ToolState
from intentkit.tools.weth.base import WethBaseTool
from intentkit.tools.weth.unwrap_eth import WETHUnwrapEth
from intentkit.tools.weth.wrap_eth import WETHWrapEth


class ToolStates(TypedDict):
    weth_wrap_eth: ToolState
    weth_unwrap_eth: ToolState


class Config(ToolsetConfig):
    """Configuration for WETH tools."""

    states: ToolStates


# Cache for tool instances
_cache: dict[str, WethBaseTool] = {
    "weth_wrap_eth": WETHWrapEth(),
    "weth_unwrap_eth": WETHUnwrapEth(),
}


async def get_tools(
    config: Config,
    is_private: bool,
    **_,
) -> list[WethBaseTool]:
    """Get all enabled WETH tools.

    Args:
        config: The configuration for WETH tools.
        is_private: Whether to include private tools.

    Returns:
        A list of enabled WETH tools.
    """
    tools: list[WethBaseTool] = []

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

    WETH tools are available for any EVM-compatible wallet (CDP, Safe/Privy)
    on networks that have WETH deployed.
    """
    return True
