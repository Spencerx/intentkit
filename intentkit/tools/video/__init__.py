"""Video generation tools across multiple providers."""

import logging
from collections.abc import Callable
from typing import TypedDict

from intentkit.config.config import config as system_config
from intentkit.tools.base import ToolsetConfig, ToolState
from intentkit.tools.video.base import VideoBaseTool
from intentkit.tools.video.gemini import VeoVideo, VeoVideoFast
from intentkit.tools.video.gpt import SoraVideo, SoraVideoPro
from intentkit.tools.video.grok import GrokVideo
from intentkit.tools.video.minimax import HailuoVideo

# Cache tools at the system level, because they are stateless
_cache: dict[str, VideoBaseTool] = {}

logger = logging.getLogger(__name__)

_TOOL_NAME_TO_CLASS: dict[str, Callable[[], VideoBaseTool]] = {
    "video_grok": GrokVideo,
    "video_sora": SoraVideo,
    "video_sora_pro": SoraVideoPro,
    "video_veo": VeoVideo,
    "video_veo_fast": VeoVideoFast,
    "video_hailuo": HailuoVideo,
}


class ToolStates(TypedDict):
    video_grok: ToolState
    video_sora: ToolState
    video_sora_pro: ToolState
    video_veo: ToolState
    video_veo_fast: ToolState
    video_hailuo: ToolState


class Config(ToolsetConfig):
    """Configuration for video generation tools."""

    states: ToolStates


async def get_tools(
    config: "Config",
    is_private: bool,
    **_,
) -> list[VideoBaseTool]:
    """Get all video generation tools.

    Args:
        config: The configuration for video tools.
        is_private: Whether to include private tools.

    Returns:
        A list of video generation tools.
    """
    available_tools = []

    for tool_name, state in config["states"].items():
        if state == "disabled":
            continue
        elif state == "public" or (state == "private" and is_private):
            available_tools.append(tool_name)

    result = []
    for name in available_tools:
        tool = get_video_tool(name)
        if tool:
            result.append(tool)
    return result


def get_video_tool(name: str) -> VideoBaseTool | None:
    """Get a video tool by name with caching."""
    if name in _cache:
        return _cache[name]

    cls = _TOOL_NAME_TO_CLASS.get(name)
    if cls is None:
        logger.warning("Unknown video tool: %s", name)
        return None

    _cache[name] = cls()
    return _cache[name]


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return bool(
        system_config.openai_api_key
        or system_config.google_api_key
        or system_config.xai_api_key
        or system_config.minimax_plan_api_key
    )
