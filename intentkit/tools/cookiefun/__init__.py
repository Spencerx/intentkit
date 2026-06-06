from typing import TypedDict

from intentkit.config.config import config as system_config
from intentkit.tools.base import ToolsetConfig, ToolState
from intentkit.tools.cookiefun.base import CookieFunBaseTool, logger
from intentkit.tools.cookiefun.get_account_details import GetAccountDetails
from intentkit.tools.cookiefun.get_account_feed import GetAccountFeed
from intentkit.tools.cookiefun.get_account_smart_followers import (
    GetAccountSmartFollowers,
)
from intentkit.tools.cookiefun.get_sectors import GetSectors
from intentkit.tools.cookiefun.search_accounts import SearchAccounts

# Cache tools at the system level, because they are stateless
_cache: dict[str, CookieFunBaseTool] = {}


class ToolStates(TypedDict):
    """States for CookieFun tools."""

    get_sectors: ToolState
    get_account_details: ToolState
    get_account_smart_followers: ToolState
    search_accounts: ToolState
    get_account_feed: ToolState


class Config(ToolsetConfig):
    """Configuration for CookieFun tools."""

    states: ToolStates


async def get_tools(
    config: "Config",
    is_private: bool,
    **_,
) -> list[CookieFunBaseTool]:
    """Get all CookieFun tools."""
    available_tools = []

    # Include tools based on their state
    for tool_name, state in config["states"].items():
        if state == "disabled":
            continue
        elif state == "public" or (state == "private" and is_private):
            available_tools.append(tool_name)

    # Get each tool using the cached getter
    tools = [s for name in available_tools if (s := get_cookiefun_tool(name))]
    logger.info("Returning %d CookieFun tools", len(tools))
    return tools


def get_cookiefun_tool(
    name: str,
) -> CookieFunBaseTool | None:
    """Get a CookieFun tool by name."""

    if name not in _cache:
        if name == "get_sectors":
            _cache[name] = GetSectors()
        elif name == "get_account_details":
            _cache[name] = GetAccountDetails()
        elif name == "get_account_smart_followers":
            _cache[name] = GetAccountSmartFollowers()
        elif name == "search_accounts":
            _cache[name] = SearchAccounts()
        elif name == "get_account_feed":
            _cache[name] = GetAccountFeed()
        else:
            logger.warning("Unknown CookieFun tool: %s", name)
            return None

    return _cache[name]


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return bool(system_config.cookiefun_api_key)
