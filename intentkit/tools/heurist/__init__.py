"""Heurist AI tools."""

import logging
from typing import NotRequired, TypedDict

from intentkit.config.config import config as system_config
from intentkit.tools.base import ToolsetConfig, ToolState
from intentkit.tools.heurist.base import HeuristBaseTool
from intentkit.tools.heurist.image_generation_animagine_xl import (
    ImageGenerationAnimagineXL,
)
from intentkit.tools.heurist.image_generation_arthemy_comics import (
    ImageGenerationArthemyComics,
)
from intentkit.tools.heurist.image_generation_arthemy_real import (
    ImageGenerationArthemyReal,
)
from intentkit.tools.heurist.image_generation_braindance import (
    ImageGenerationBrainDance,
)
from intentkit.tools.heurist.image_generation_cyber_realistic_xl import (
    ImageGenerationCyberRealisticXL,
)
from intentkit.tools.heurist.image_generation_flux_1_dev import ImageGenerationFlux1Dev
from intentkit.tools.heurist.image_generation_sdxl import ImageGenerationSDXL

# Cache tools at the system level, because they are stateless
_cache: dict[str, HeuristBaseTool] = {}

logger = logging.getLogger(__name__)


class ToolStates(TypedDict):
    image_generation_animagine_xl: ToolState
    image_generation_arthemy_comics: ToolState
    image_generation_arthemy_real: ToolState
    image_generation_braindance: ToolState
    image_generation_cyber_realistic_xl: ToolState
    image_generation_flux_1_dev: ToolState
    image_generation_sdxl: ToolState


class Config(ToolsetConfig):
    """Configuration for Heurist AI tools."""

    states: ToolStates
    rate_limit_number: NotRequired[int]
    rate_limit_minutes: NotRequired[int]


async def get_tools(
    config: "Config",
    is_private: bool,
    **_,
) -> list[HeuristBaseTool]:
    """Get all Heurist AI tools.

    Args:
        config: The configuration for Heurist AI tools.
        is_private: Whether to include private tools.

    Returns:
        A list of Heurist AI tools.
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
        tool = get_heurist_tool(name)
        if tool:
            result.append(tool)
    return result


def get_heurist_tool(
    name: str,
) -> HeuristBaseTool | None:
    """Get a Heurist AI tool by name.

    Args:
        name: The name of the tool to get

    Returns:
        The requested Heurist AI tool
    """
    if name == "image_generation_animagine_xl":
        if name not in _cache:
            _cache[name] = ImageGenerationAnimagineXL()
        return _cache[name]
    elif name == "image_generation_arthemy_comics":
        if name not in _cache:
            _cache[name] = ImageGenerationArthemyComics()
        return _cache[name]
    elif name == "image_generation_arthemy_real":
        if name not in _cache:
            _cache[name] = ImageGenerationArthemyReal()
        return _cache[name]
    elif name == "image_generation_braindance":
        if name not in _cache:
            _cache[name] = ImageGenerationBrainDance()
        return _cache[name]
    elif name == "image_generation_cyber_realistic_xl":
        if name not in _cache:
            _cache[name] = ImageGenerationCyberRealisticXL()
        return _cache[name]
    elif name == "image_generation_flux_1_dev":
        if name not in _cache:
            _cache[name] = ImageGenerationFlux1Dev()
        return _cache[name]
    elif name == "image_generation_sdxl":
        if name not in _cache:
            _cache[name] = ImageGenerationSDXL()
        return _cache[name]
    else:
        logger.warning("Unknown Heurist tool: %s", name)
        return None


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return bool(system_config.heurist_api_key)
