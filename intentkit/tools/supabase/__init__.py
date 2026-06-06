"""Supabase tools."""

import logging
from typing import NotRequired, TypedDict

from intentkit.tools.base import ToolsetConfig, ToolState
from intentkit.tools.supabase.base import SupabaseBaseTool
from intentkit.tools.supabase.delete_data import SupabaseDeleteData
from intentkit.tools.supabase.fetch_data import SupabaseFetchData
from intentkit.tools.supabase.insert_data import SupabaseInsertData
from intentkit.tools.supabase.invoke_function import SupabaseInvokeFunction
from intentkit.tools.supabase.update_data import SupabaseUpdateData
from intentkit.tools.supabase.upsert_data import SupabaseUpsertData

# Cache tools at the system level, because they are stateless
_cache: dict[str, SupabaseBaseTool] = {}

logger = logging.getLogger(__name__)


class ToolStates(TypedDict):
    fetch_data: ToolState
    insert_data: ToolState
    update_data: ToolState
    upsert_data: ToolState
    delete_data: ToolState
    invoke_function: ToolState


class Config(ToolsetConfig):
    """Configuration for Supabase tools."""

    states: ToolStates
    supabase_url: str
    supabase_key: str
    public_write_tables: NotRequired[str]
    public_key: NotRequired[str]


async def get_tools(
    config: "Config",
    is_private: bool,
    **_,
) -> list[SupabaseBaseTool]:
    """Get all Supabase tools."""
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
        tool = get_supabase_tool(name)
        if tool:
            result.append(tool)
    return result


def get_supabase_tool(
    name: str,
) -> SupabaseBaseTool | None:
    """Get a Supabase tool by name.

    Args:
        name: The name of the tool to get

    Returns:
        The requested Supabase tool
    """
    if name == "fetch_data":
        if name not in _cache:
            _cache[name] = SupabaseFetchData()
        return _cache[name]
    elif name == "insert_data":
        if name not in _cache:
            _cache[name] = SupabaseInsertData()
        return _cache[name]
    elif name == "update_data":
        if name not in _cache:
            _cache[name] = SupabaseUpdateData()
        return _cache[name]
    elif name == "upsert_data":
        if name not in _cache:
            _cache[name] = SupabaseUpsertData()
        return _cache[name]
    elif name == "delete_data":
        if name not in _cache:
            _cache[name] = SupabaseDeleteData()
        return _cache[name]
    elif name == "invoke_function":
        if name not in _cache:
            _cache[name] = SupabaseInvokeFunction()
        return _cache[name]
    else:
        logger.warning("Unknown Supabase tool: %s", name)
        return None


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return True
