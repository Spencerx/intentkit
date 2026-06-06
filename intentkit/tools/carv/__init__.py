import logging
from typing import TypedDict

from intentkit.config.config import config as system_config
from intentkit.tools.base import ToolsetConfig, ToolState
from intentkit.tools.carv.base import CarvBaseTool
from intentkit.tools.carv.fetch_news import FetchNewsTool
from intentkit.tools.carv.onchain_query import OnchainQueryTool
from intentkit.tools.carv.token_info_and_price import TokenInfoAndPriceTool

logger = logging.getLogger(__name__)

_cache: dict[str, CarvBaseTool] = {}

_TOOL_NAME_TO_CLASS_MAP: dict[str, type[CarvBaseTool]] = {
    "onchain_query": OnchainQueryTool,
    "token_info_and_price": TokenInfoAndPriceTool,
    "fetch_news": FetchNewsTool,
}


class ToolStates(TypedDict):
    onchain_query: ToolState
    token_info_and_price: ToolState
    fetch_news: ToolState


class Config(ToolsetConfig):
    enabled: bool
    states: ToolStates  # type: ignore

    # optional
    rate_limit_number: int | None
    rate_limit_minutes: int | None


async def get_tools(
    config: "Config",
    is_private: bool,
    **_,
) -> list[CarvBaseTool]:
    """
    Factory function to create and return CARV tool tools based on the provided configuration.

    Args:
        config: The configuration object for the CARV tool.
        is_private: A boolean indicating whether the request is from a private context.

    Returns:
        A list of `CarvBaseTool` instances.
    """
    # Check if the entire category is disabled first
    if not config.get("enabled", False):
        return []

    available_tools: list[CarvBaseTool] = []
    tool_states = config.get("states", {})

    # Iterate through all known tools defined in the map
    for tool_name in _TOOL_NAME_TO_CLASS_MAP:
        state = tool_states.get(
            tool_name, "disabled"
        )  # Default to disabled if not in config

        if state == "disabled":
            continue
        elif state == "public" or (state == "private" and is_private):
            # If enabled, get the tool instance using the factory function
            tool_instance = get_carv_tool(tool_name)
            if tool_instance:
                available_tools.append(tool_instance)
            else:
                logger.warning("Could not instantiate known tool: %s", tool_name)

    return available_tools


def get_carv_tool(
    name: str,
) -> CarvBaseTool | None:
    """
    Factory function to retrieve a cached CARV tool instance by name.

    Args:
        name: The name of the CARV tool to retrieve.

    Returns:
        The requested `CarvBaseTool` instance if found and enabled, otherwise None.
    """

    # Return from cache immediately if already exists
    if name in _cache:
        return _cache[name]

    # Get the class from the map
    tool_class = _TOOL_NAME_TO_CLASS_MAP.get(name)

    if tool_class:
        try:
            # Instantiate the tool and add to cache
            instance = tool_class()  # pyright: ignore[reportCallIssue]
            _cache[name] = instance
            return instance
        except Exception as e:
            logger.error(
                "Failed to instantiate Carv tool '%s': %s", name, e, exc_info=True
            )
            return None  # Failed to instantiate
    else:
        # This handles cases where a name might be in config but not in our map
        logger.warning("Attempted to get unknown Carv tool: %s", name)
        return None


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return bool(system_config.carv_api_key)
