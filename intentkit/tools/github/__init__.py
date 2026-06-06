import logging
from typing import TypedDict

from intentkit.tools.base import ToolsetConfig, ToolState
from intentkit.tools.github.base import GitHubBaseTool
from intentkit.tools.github.github_search import GitHubSearch

logger = logging.getLogger(__name__)

# Cache tools at the system level, because they are stateless
_cache: dict[str, GitHubBaseTool] = {}


class ToolStates(TypedDict):
    github_search: ToolState


class Config(ToolsetConfig):
    """Configuration for GitHub tools."""

    states: ToolStates


async def get_tools(
    config: "Config",
    is_private: bool,
    **_,
) -> list[GitHubBaseTool]:
    """Get all GitHub tools."""
    available_tools = []

    # Include tools based on their state
    for tool_name, state in config["states"].items():
        if state == "disabled":
            continue
        elif state == "public" or (state == "private" and is_private):
            available_tools.append(tool_name)

    # Get each tool using the cached getter
    return [s for name in available_tools if (s := get_github_tool(name))]


def get_github_tool(
    name: str,
) -> GitHubBaseTool | None:
    """Get a GitHub tool by name."""
    if name == "github_search":
        if name not in _cache:
            _cache[name] = GitHubSearch()
        return _cache[name]
    else:
        logger.warning("Unknown GitHub tool: %s", name)
        return None


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return True
