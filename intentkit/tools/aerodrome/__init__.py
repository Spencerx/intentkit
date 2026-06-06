import logging
from typing import Any, TypedDict

from intentkit.tools.aerodrome.add_liquidity import AerodromeAddLiquidity
from intentkit.tools.aerodrome.base import AerodromeBaseTool
from intentkit.tools.aerodrome.get_positions import AerodromeGetPositions
from intentkit.tools.aerodrome.quote import AerodromeQuote
from intentkit.tools.aerodrome.remove_liquidity import AerodromeRemoveLiquidity
from intentkit.tools.aerodrome.swap import AerodromeSwap
from intentkit.tools.base import ToolsetConfig, ToolState

logger = logging.getLogger(__name__)

_cache: dict[str, AerodromeBaseTool] = {}


class ToolStates(TypedDict):
    quote: ToolState
    swap: ToolState
    get_positions: ToolState
    add_liquidity: ToolState
    remove_liquidity: ToolState


class Config(ToolsetConfig):
    """Configuration for Aerodrome tools."""

    states: ToolStates


async def get_tools(
    config: "Config",
    is_private: bool,
    **_: Any,
) -> list[AerodromeBaseTool]:
    """Get all Aerodrome tools."""
    available_tools: list[str] = []

    for tool_name, state in config["states"].items():
        if state == "disabled":
            continue
        elif state == "public" or (state == "private" and is_private):
            available_tools.append(tool_name)

    result: list[AerodromeBaseTool] = []
    for name in available_tools:
        tool = _get_tool(name)
        if tool:
            result.append(tool)
    return result


def _get_tool(name: str) -> AerodromeBaseTool | None:
    if name not in _cache:
        if name == "quote":
            _cache[name] = AerodromeQuote()
        elif name == "swap":
            _cache[name] = AerodromeSwap()
        elif name == "get_positions":
            _cache[name] = AerodromeGetPositions()
        elif name == "add_liquidity":
            _cache[name] = AerodromeAddLiquidity()
        elif name == "remove_liquidity":
            _cache[name] = AerodromeRemoveLiquidity()
        else:
            logger.warning("Unknown aerodrome tool: %s", name)
            return None
    return _cache[name]


def available() -> bool:
    """Aerodrome requires no platform API keys."""
    return True
