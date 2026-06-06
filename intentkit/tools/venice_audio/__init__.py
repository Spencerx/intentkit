import logging
from typing import Literal, TypedDict

from intentkit.config.config import config as system_config
from intentkit.tools.base import ToolsetConfig, ToolState
from intentkit.tools.venice_audio.base import VeniceAudioBaseTool
from intentkit.tools.venice_audio.venice_audio import VeniceAudioTool

logger = logging.getLogger(__name__)

_cache: dict[str, VeniceAudioBaseTool] = {}

_TOOL_NAME_TO_CLASS_MAP = {
    "text_to_speech": VeniceAudioTool,
    # Add new mappings here: "tool_name": ToolClassName
}


class ToolStates(TypedDict):
    text_to_speech: ToolState


class Config(ToolsetConfig):
    enabled: bool
    voice_model: Literal["af_heart", "bm_lewis", "custom"]
    states: ToolStates  # type: ignore

    # conditionally required
    voice_model_custom: list[str] | None

    # optional
    rate_limit_number: int | None
    rate_limit_minutes: int | None


async def get_tools(
    config: "Config",
    is_private: bool,
    **_,  # Allow for extra arguments if the loader passes them
) -> list[VeniceAudioBaseTool]:
    """
    Factory function to create and return Venice Audio tool tools.

    Args:
        config: The configuration dictionary for the Venice Audio tool.
        agent_id: The ID of the agent requesting the tools.

    Returns:
        A list of VeniceAudioBaseTool instances for the Venice Audio tool.
    """
    # Check if the entire category is disabled first
    if not config.get("enabled", False):
        return []

    available_tools: list[VeniceAudioBaseTool] = []
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
            tool_instance = get_venice_audio_tool(tool_name)
            if tool_instance:
                available_tools.append(tool_instance)
            else:
                # This case should ideally not happen if the map is correct
                logger.warning("Could not instantiate known tool: %s", tool_name)

    return available_tools


def get_venice_audio_tool(
    name: str,
) -> VeniceAudioBaseTool | None:
    """
    Factory function to get a cached Venice Audio tool instance by name.

    Args:
        name: The name of voice model.

    Returns:
        The requested Venice Audio tool instance, or None if the name is unknown.
    """

    # Return from cache immediately if already exists
    if name in _cache:
        return _cache[name]

    # Cache and return the newly created instance
    _cache[name] = VeniceAudioTool()
    return _cache[name]


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return bool(system_config.venice_api_key)
