import logging
from typing import TypedDict

from intentkit.config.config import config as system_config
from intentkit.tools.base import ToolsetConfig, ToolState
from intentkit.tools.unrealspeech.base import UnrealSpeechBaseTool
from intentkit.tools.unrealspeech.text_to_speech import TextToSpeech

logger = logging.getLogger(__name__)

# Cache tools at the system level, because they are stateless
_cache: dict[str, UnrealSpeechBaseTool] = {}


class ToolStates(TypedDict):
    text_to_speech: ToolState


class Config(ToolsetConfig):
    """Configuration for UnrealSpeech tools."""

    states: ToolStates


async def get_tools(
    config: "Config",
    is_private: bool,
    **_,
) -> list[UnrealSpeechBaseTool]:
    """Get all UnrealSpeech tools."""
    available_tools = []

    # Include tools based on their state
    for tool_name, state in config["states"].items():
        if state == "disabled":
            continue
        elif state == "public" or (state == "private" and is_private):
            available_tools.append(tool_name)

    # Get each tool using the cached getter
    return [s for name in available_tools if (s := get_unrealspeech_tool(name))]


def get_unrealspeech_tool(
    name: str,
) -> UnrealSpeechBaseTool | None:
    """Get an UnrealSpeech tool by name."""
    if name == "text_to_speech":
        if name not in _cache:
            _cache[name] = TextToSpeech()
        return _cache[name]
    else:
        logger.warning("Unknown UnrealSpeech tool: %s", name)
        return None


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return bool(system_config.unrealspeech_api_key)
