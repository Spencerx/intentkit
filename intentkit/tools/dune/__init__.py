"""Dune tools for blockchain analytics via the Dune API."""

import logging
from collections.abc import Callable
from typing import TypedDict

from intentkit.config.config import config as system_config
from intentkit.tools.base import ToolsetConfig, ToolState
from intentkit.tools.dune.base import DuneBaseTool
from intentkit.tools.dune.execute_query import DuneExecuteQuery
from intentkit.tools.dune.get_query_results import DuneGetQueryResults
from intentkit.tools.dune.run_sql import DuneRunSQL

_cache: dict[str, DuneBaseTool] = {}

logger = logging.getLogger(__name__)

_TOOL_NAME_TO_CLASS: dict[str, Callable[[], DuneBaseTool]] = {
    "dune_execute_query": DuneExecuteQuery,
    "dune_get_query_results": DuneGetQueryResults,
    "dune_run_sql": DuneRunSQL,
}


class ToolStates(TypedDict):
    dune_execute_query: ToolState
    dune_get_query_results: ToolState
    dune_run_sql: ToolState


class Config(ToolsetConfig):
    """Configuration for Dune tools."""

    states: ToolStates


async def get_tools(
    config: "Config",
    is_private: bool,
    **_,
) -> list[DuneBaseTool]:
    """Get all enabled Dune tools."""
    available_tools = []

    for tool_name, state in config["states"].items():
        if state == "disabled":
            continue
        elif state == "public" or (state == "private" and is_private):
            available_tools.append(tool_name)

    result = []
    for name in available_tools:
        tool = get_dune_tool(name)
        if tool:
            result.append(tool)
    return result


def get_dune_tool(name: str) -> DuneBaseTool | None:
    """Get a Dune tool by name with caching."""
    if name in _cache:
        return _cache[name]

    cls = _TOOL_NAME_TO_CLASS.get(name)
    if cls is None:
        logger.warning("Unknown dune tool: %s", name)
        return None

    _cache[name] = cls()
    return _cache[name]


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return bool(system_config.dune_api_key)
