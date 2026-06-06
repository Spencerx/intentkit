import logging
from typing import TypedDict

from intentkit.tools.base import ToolsetConfig, ToolState
from intentkit.tools.chainlist.base import ChainlistBaseTool
from intentkit.tools.chainlist.chain_lookup import ChainLookup

logger = logging.getLogger(__name__)

# Cache tools at the system level, because they are stateless
_cache: dict[str, ChainlistBaseTool] = {}


class ToolStates(TypedDict):
    chain_lookup: ToolState


class Config(ToolsetConfig):
    """Configuration for chainlist tools."""

    states: ToolStates


async def get_tools(
    config: "Config",
    is_private: bool,
    **_,
) -> list[ChainlistBaseTool]:
    """Get all chainlist tools."""
    available_tools = []

    # Include tools based on their state
    for tool_name, state in config["states"].items():
        if state == "disabled":
            continue
        elif state == "public" or (state == "private" and is_private):
            available_tools.append(tool_name)

    # Get each tool using the cached getter
    return [s for name in available_tools if (s := get_chainlist_tool(name))]


def get_chainlist_tool(
    name: str,
) -> ChainlistBaseTool | None:
    """Get a chainlist tool by name."""
    if name == "chain_lookup":
        if name not in _cache:
            _cache[name] = ChainLookup()
        return _cache[name]
    else:
        logger.warning("Unknown chainlist tool: %s", name)
        return None


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return True
