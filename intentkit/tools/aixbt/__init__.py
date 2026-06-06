import logging
from typing import NotRequired, TypedDict

from intentkit.config.config import config as system_config
from intentkit.tools.aixbt.base import AIXBTBaseTool
from intentkit.tools.aixbt.projects import AIXBTProjects
from intentkit.tools.base import ToolsetConfig, ToolState

logger = logging.getLogger(__name__)

# Cache tools at the system level, because they are stateless
_cache: dict[str, AIXBTBaseTool] = {}


class ToolStates(TypedDict):
    aixbt_projects: ToolState


class Config(ToolsetConfig):
    """Configuration for AIXBT API tools."""

    states: ToolStates
    rate_limit_number: NotRequired[int]
    rate_limit_minutes: NotRequired[int]


async def get_tools(
    config: "Config",
    is_private: bool,
    **_,
) -> list[AIXBTBaseTool]:
    """Get all AIXBT API tools."""
    if not config.get("enabled", False):
        return []

    available_tools = []

    # Include tools based on their state
    for tool_name, state in config["states"].items():
        if state == "disabled":
            continue
        elif state == "public" or (state == "private" and is_private):
            available_tools.append(tool_name)

    # Get each tool using the cached getter
    return [s for name in available_tools if (s := get_aixbt_tool(name))]


def get_aixbt_tool(
    name: str,
) -> AIXBTBaseTool | None:
    """Get an AIXBT API tool by name."""

    if name == "aixbt_projects":
        if name not in _cache:
            _cache[name] = AIXBTProjects()
        return _cache[name]
    else:
        logger.warning("Unknown AIXBT tool: %s", name)
        return None


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return bool(system_config.aixbt_api_key)
