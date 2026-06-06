"""HTTP client tools."""

import logging
from typing import TypedDict

from intentkit.tools.base import ToolsetConfig, ToolState
from intentkit.tools.http.base import HttpBaseTool
from intentkit.tools.http.get import HttpGet
from intentkit.tools.http.post import HttpPost
from intentkit.tools.http.put import HttpPut

# Cache tools at the system level, because they are stateless
_cache: dict[str, HttpBaseTool] = {}

logger = logging.getLogger(__name__)


class ToolStates(TypedDict):
    """Type definition for HTTP tool states."""

    http_get: ToolState
    http_post: ToolState
    http_put: ToolState


class Config(ToolsetConfig):
    """Configuration for HTTP client tools."""

    states: ToolStates


async def get_tools(
    config: "Config",
    is_private: bool,
    **_,
) -> list[HttpBaseTool]:
    """Get all HTTP client tools.

    Args:
        config: The configuration for HTTP client tools.
        is_private: Whether to include private tools.

    Returns:
        A list of HTTP client tools.
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
        tool = get_http_tool(name)
        if tool:
            result.append(tool)
    return result


def get_http_tool(
    name: str,
) -> HttpBaseTool | None:
    """Get an HTTP client tool by name.

    Args:
        name: The name of the tool to get

    Returns:
        The requested HTTP client tool
    """
    if name == "http_get":
        if name not in _cache:
            _cache[name] = HttpGet()
        return _cache[name]
    elif name == "http_post":
        if name not in _cache:
            _cache[name] = HttpPost()
        return _cache[name]
    elif name == "http_put":
        if name not in _cache:
            _cache[name] = HttpPut()
        return _cache[name]
    else:
        logger.warning("Unknown HTTP tool: %s", name)
        return None


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return True
