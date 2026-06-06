import logging
from typing import Any, TypedDict

from intentkit.tools.base import ToolsetConfig, ToolState
from intentkit.tools.pancakeswap.add_liquidity import PancakeSwapAddLiquidity
from intentkit.tools.pancakeswap.base import PancakeSwapBaseTool
from intentkit.tools.pancakeswap.get_positions import PancakeSwapGetPositions
from intentkit.tools.pancakeswap.quote import PancakeSwapQuote
from intentkit.tools.pancakeswap.remove_liquidity import PancakeSwapRemoveLiquidity
from intentkit.tools.pancakeswap.swap import PancakeSwapSwap

logger = logging.getLogger(__name__)

_cache: dict[str, PancakeSwapBaseTool] = {}


class ToolStates(TypedDict):
    quote: ToolState
    swap: ToolState
    get_positions: ToolState
    add_liquidity: ToolState
    remove_liquidity: ToolState


class Config(ToolsetConfig):
    """Configuration for PancakeSwap tools."""

    states: ToolStates


async def get_tools(
    config: "Config",
    is_private: bool,
    **_: Any,
) -> list[PancakeSwapBaseTool]:
    """Get all PancakeSwap tools."""
    available_tools: list[str] = []

    for tool_name, state in config["states"].items():
        if state == "disabled":
            continue
        elif state == "public" or (state == "private" and is_private):
            available_tools.append(tool_name)

    result: list[PancakeSwapBaseTool] = []
    for name in available_tools:
        tool = _get_tool(name)
        if tool:
            result.append(tool)
    return result


def _get_tool(name: str) -> PancakeSwapBaseTool | None:
    if name not in _cache:
        if name == "quote":
            _cache[name] = PancakeSwapQuote()
        elif name == "swap":
            _cache[name] = PancakeSwapSwap()
        elif name == "get_positions":
            _cache[name] = PancakeSwapGetPositions()
        elif name == "add_liquidity":
            _cache[name] = PancakeSwapAddLiquidity()
        elif name == "remove_liquidity":
            _cache[name] = PancakeSwapRemoveLiquidity()
        else:
            logger.warning("Unknown pancakeswap tool: %s", name)
            return None
    return _cache[name]


def available() -> bool:
    """PancakeSwap requires no platform API keys."""
    return True
