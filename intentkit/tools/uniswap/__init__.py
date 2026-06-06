import logging
from typing import Any, TypedDict

from intentkit.tools.base import ToolsetConfig, ToolState
from intentkit.tools.uniswap.add_liquidity import UniswapAddLiquidity
from intentkit.tools.uniswap.base import UniswapBaseTool
from intentkit.tools.uniswap.get_positions import UniswapGetPositions
from intentkit.tools.uniswap.quote import UniswapQuote
from intentkit.tools.uniswap.remove_liquidity import UniswapRemoveLiquidity
from intentkit.tools.uniswap.swap import UniswapSwap

logger = logging.getLogger(__name__)

_cache: dict[str, UniswapBaseTool] = {}


class ToolStates(TypedDict):
    quote: ToolState
    swap: ToolState
    get_positions: ToolState
    add_liquidity: ToolState
    remove_liquidity: ToolState


class Config(ToolsetConfig):
    """Configuration for Uniswap tools."""

    states: ToolStates


async def get_tools(
    config: "Config",
    is_private: bool,
    **_: Any,
) -> list[UniswapBaseTool]:
    """Get all Uniswap tools."""
    available_tools: list[str] = []

    for tool_name, state in config["states"].items():
        if state == "disabled":
            continue
        elif state == "public" or (state == "private" and is_private):
            available_tools.append(tool_name)

    result: list[UniswapBaseTool] = []
    for name in available_tools:
        tool = _get_tool(name)
        if tool:
            result.append(tool)
    return result


def _get_tool(name: str) -> UniswapBaseTool | None:
    if name not in _cache:
        if name == "quote":
            _cache[name] = UniswapQuote()
        elif name == "swap":
            _cache[name] = UniswapSwap()
        elif name == "get_positions":
            _cache[name] = UniswapGetPositions()
        elif name == "add_liquidity":
            _cache[name] = UniswapAddLiquidity()
        elif name == "remove_liquidity":
            _cache[name] = UniswapRemoveLiquidity()
        else:
            logger.warning("Unknown uniswap tool: %s", name)
            return None
    return _cache[name]


def available() -> bool:
    """Uniswap requires no platform API keys."""
    return True
