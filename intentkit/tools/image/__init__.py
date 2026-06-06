"""Image generation tools across multiple providers."""

import logging
from collections.abc import Callable
from typing import TypedDict

from intentkit.config.config import config as system_config
from intentkit.tools.base import ToolsetConfig, ToolState
from intentkit.tools.image.base import ImageBaseTool
from intentkit.tools.image.gemini import GeminiImageFlash, GeminiImagePro
from intentkit.tools.image.gpt import GPTImageFlagship, GPTImageMini
from intentkit.tools.image.grok import GrokImage
from intentkit.tools.image.minimax import MiniMaxImage
from intentkit.tools.image.openrouter import FluxPro, Riverflow

# Cache tools at the system level, because they are stateless
_cache: dict[str, ImageBaseTool] = {}

logger = logging.getLogger(__name__)

_TOOL_NAME_TO_CLASS: dict[str, Callable[[], ImageBaseTool]] = {
    "image_gpt": GPTImageFlagship,
    "image_gpt_mini": GPTImageMini,
    "image_gemini_pro": GeminiImagePro,
    "image_gemini_flash": GeminiImageFlash,
    "image_grok": GrokImage,
    "image_flux_pro": FluxPro,
    "image_riverflow": Riverflow,
    "image_minimax": MiniMaxImage,
}


class ToolStates(TypedDict):
    image_gpt: ToolState
    image_gpt_mini: ToolState
    image_gemini_pro: ToolState
    image_gemini_flash: ToolState
    image_grok: ToolState
    image_flux_pro: ToolState
    image_riverflow: ToolState
    image_minimax: ToolState


class Config(ToolsetConfig):
    """Configuration for image generation tools."""

    states: ToolStates


async def get_tools(
    config: "Config",
    is_private: bool,
    **_,
) -> list[ImageBaseTool]:
    """Get all image generation tools.

    Args:
        config: The configuration for image tools.
        is_private: Whether to include private tools.

    Returns:
        A list of image generation tools.
    """
    available_tools = []

    for tool_name, state in config["states"].items():
        if state == "disabled":
            continue
        elif state == "public" or (state == "private" and is_private):
            available_tools.append(tool_name)

    result = []
    for name in available_tools:
        tool = get_image_tool(name)
        if tool:
            result.append(tool)
    return result


def get_image_tool(name: str) -> ImageBaseTool | None:
    """Get an image tool by name with caching."""
    if name in _cache:
        return _cache[name]

    cls = _TOOL_NAME_TO_CLASS.get(name)
    if cls is None:
        logger.warning("Unknown image tool: %s", name)
        return None

    _cache[name] = cls()
    return _cache[name]


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return bool(
        system_config.openai_api_key
        or system_config.google_api_key
        or system_config.xai_api_key
        or system_config.openrouter_api_key
        or system_config.minimax_plan_api_key
    )
