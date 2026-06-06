"""Casino tools for card games and dice rolling."""

import logging
from typing import TypedDict

from intentkit.tools.base import ToolsetConfig, ToolState
from intentkit.tools.casino.base import CasinoBaseTool
from intentkit.tools.casino.deck_draw import CasinoDeckDraw
from intentkit.tools.casino.deck_shuffle import CasinoDeckShuffle
from intentkit.tools.casino.dice_roll import CasinoDiceRoll

# Cache tools at the system level, because they are stateless
_cache: dict[str, CasinoBaseTool] = {}

logger = logging.getLogger(__name__)


class ToolStates(TypedDict):
    deck_shuffle: ToolState
    deck_draw: ToolState
    dice_roll: ToolState


class Config(ToolsetConfig):
    """Configuration for Casino tools."""

    states: ToolStates


async def get_tools(
    config: "Config",
    is_private: bool,
    **_,
) -> list[CasinoBaseTool]:
    """Get all Casino tools.

    Args:
        config: The configuration for Casino tools.
        is_private: Whether to include private tools.

    Returns:
        A list of Casino tools.
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
        tool = get_casino_tool(name)
        if tool:
            result.append(tool)
    return result


def get_casino_tool(
    name: str,
) -> CasinoBaseTool | None:
    """Get a Casino tool by name."""
    if name == "deck_shuffle":
        if name not in _cache:
            _cache[name] = CasinoDeckShuffle()
        return _cache[name]
    elif name == "deck_draw":
        if name not in _cache:
            _cache[name] = CasinoDeckDraw()
        return _cache[name]
    elif name == "dice_roll":
        if name not in _cache:
            _cache[name] = CasinoDiceRoll()
        return _cache[name]
    else:
        logger.warning("Unknown Casino tool: %s", name)
        return None


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return True
