"""x402 toolset."""

import logging
from typing import TypedDict

from intentkit.tools.base import ToolsetConfig, ToolState
from intentkit.tools.x402.base import X402BaseTool
from intentkit.tools.x402.check_price import X402CheckPrice
from intentkit.tools.x402.get_orders import X402GetOrders
from intentkit.tools.x402.http_request import X402HttpRequest
from intentkit.tools.x402.pay import X402Pay

logger = logging.getLogger(__name__)

_cache: dict[str, X402BaseTool] = {}


class ToolStates(TypedDict):
    x402_http_request: ToolState
    x402_check_price: ToolState
    x402_pay: ToolState
    x402_get_orders: ToolState


class Config(ToolsetConfig):
    """Configuration for x402 tools."""

    states: ToolStates


_TOOL_BUILDERS: dict[str, type[X402BaseTool]] = {
    "x402_http_request": X402HttpRequest,
    "x402_check_price": X402CheckPrice,
    "x402_pay": X402Pay,
    "x402_get_orders": X402GetOrders,
}


async def get_tools(
    config: "Config",
    is_private: bool,
    **_,
) -> list[X402BaseTool]:
    """Return enabled x402 tools for the agent."""
    enabled_tools = []
    for tool_name, state in config["states"].items():
        if state == "disabled":
            continue
        if state == "public" or (state == "private" and is_private):
            enabled_tools.append(tool_name)

    result: list[X402BaseTool] = []
    for name in enabled_tools:
        tool = _get_tool(name)
        if tool:
            result.append(tool)
    return result


def _get_tool(name: str) -> X402BaseTool | None:
    builder = _TOOL_BUILDERS.get(name)
    if builder:
        if name not in _cache:
            _cache[name] = builder()
        return _cache[name]
    logger.warning("Unknown x402 tool requested: %s", name)
    return None


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return True
