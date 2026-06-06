"""XMTP tools."""

import logging
from typing import TypedDict

from intentkit.tools.base import ToolsetConfig, ToolState
from intentkit.tools.xmtp.base import XmtpBaseTool
from intentkit.tools.xmtp.price import XmtpGetSwapPrice
from intentkit.tools.xmtp.swap import XmtpSwap
from intentkit.tools.xmtp.transfer import XmtpTransfer

# Cache tools at the module level, because they are stateless
_cache: dict[str, XmtpBaseTool] = {}

logger = logging.getLogger(__name__)


class ToolStates(TypedDict):
    xmtp_transfer: ToolState
    xmtp_swap: ToolState
    xmtp_get_swap_price: ToolState


class Config(ToolsetConfig):
    """Configuration for XMTP tools."""

    states: ToolStates


async def get_tools(
    config: "Config",
    is_private: bool,
    **_,
) -> list[XmtpBaseTool]:
    """Get all XMTP tools.

    Args:
        config: The configuration for XMTP tools.
        is_private: Whether to include private tools.

    Returns:
        A list of XMTP tools.
    """
    available_tools = []

    # Include tools based on their state
    for tool_name, state in config["states"].items():
        if state == "disabled":
            continue
        elif state == "public" or (state == "private" and is_private):
            available_tools.append(tool_name)

    # Get each tool using the cached getter
    result = []
    for name in available_tools:
        tool = get_xmtp_tool(name)
        if tool:
            result.append(tool)
    return result


def get_xmtp_tool(
    name: str,
) -> XmtpBaseTool | None:
    """Get an XMTP tool by name.

    Args:
        name: The name of the tool to get

    Returns:
        The requested XMTP tool
    """
    if name == "xmtp_transfer":
        if name not in _cache:
            _cache[name] = XmtpTransfer()
        return _cache[name]
    elif name == "xmtp_swap":
        if name not in _cache:
            _cache[name] = XmtpSwap()
        return _cache[name]
    elif name == "xmtp_get_swap_price":
        if name not in _cache:
            _cache[name] = XmtpGetSwapPrice()
        return _cache[name]
    else:
        logger.warning("Unknown XMTP tool: %s", name)
        return None


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return True
