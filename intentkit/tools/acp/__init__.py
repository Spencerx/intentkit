"""ACP (Agentic Commerce Protocol) toolset."""

import logging
from typing import TypedDict

from intentkit.tools.base import ToolsetConfig, ToolState

from .base import AcpBaseTool
from .cancel_checkout import AcpCancelCheckout
from .complete_checkout import AcpCompleteCheckout
from .create_checkout import AcpCreateCheckout
from .get_checkout import AcpGetCheckout
from .list_products import AcpListProducts

logger = logging.getLogger(__name__)

_cache: dict[str, AcpBaseTool] = {}


class ToolStates(TypedDict):
    acp_list_products: ToolState
    acp_create_checkout: ToolState
    acp_get_checkout: ToolState
    acp_complete_checkout: ToolState
    acp_cancel_checkout: ToolState


class Config(ToolsetConfig):
    """Configuration for ACP tools."""

    states: ToolStates


_TOOL_BUILDERS: dict[str, type[AcpBaseTool]] = {
    "acp_list_products": AcpListProducts,
    "acp_create_checkout": AcpCreateCheckout,
    "acp_get_checkout": AcpGetCheckout,
    "acp_complete_checkout": AcpCompleteCheckout,
    "acp_cancel_checkout": AcpCancelCheckout,
}


async def get_tools(
    config: "Config",
    is_private: bool,
    **_,
) -> list[AcpBaseTool]:
    """Return enabled ACP tools for the agent."""
    enabled_tools = []
    for tool_name, state in config["states"].items():
        if state == "disabled":
            continue
        if state == "public" or (state == "private" and is_private):
            enabled_tools.append(tool_name)

    result: list[AcpBaseTool] = []
    for name in enabled_tools:
        tool = _get_tool(name)
        if tool:
            result.append(tool)
    return result


def _get_tool(name: str) -> AcpBaseTool | None:
    builder = _TOOL_BUILDERS.get(name)
    if builder:
        if name not in _cache:
            _cache[name] = builder()
        return _cache[name]
    logger.warning("Unknown ACP tool requested: %s", name)
    return None


def available() -> bool:
    """Check if this toolset is available."""
    return True
