"""Superfluid streaming payment tools."""

from typing import TypedDict

from intentkit.tools.base import ToolsetConfig, ToolState
from intentkit.tools.superfluid.base import SuperfluidBaseTool
from intentkit.tools.superfluid.create_flow import SuperfluidCreateFlow
from intentkit.tools.superfluid.delete_flow import SuperfluidDeleteFlow
from intentkit.tools.superfluid.update_flow import SuperfluidUpdateFlow


class ToolStates(TypedDict):
    superfluid_create_flow: ToolState
    superfluid_update_flow: ToolState
    superfluid_delete_flow: ToolState


class Config(ToolsetConfig):
    """Configuration for Superfluid tools."""

    states: ToolStates


# Cache for tool instances
_cache: dict[str, SuperfluidBaseTool] = {
    "superfluid_create_flow": SuperfluidCreateFlow(),
    "superfluid_update_flow": SuperfluidUpdateFlow(),
    "superfluid_delete_flow": SuperfluidDeleteFlow(),
}


async def get_tools(
    config: Config,
    is_private: bool,
    **_,
) -> list[SuperfluidBaseTool]:
    """Get all enabled Superfluid tools.

    Args:
        config: The configuration for Superfluid tools.
        is_private: Whether to include private tools.

    Returns:
        A list of enabled Superfluid tools.
    """
    tools: list[SuperfluidBaseTool] = []

    for tool_name, state in config["states"].items():
        if state == "disabled":
            continue
        if state == "public" or (state == "private" and is_private):
            # Check cache first
            if tool_name in _cache:
                tools.append(_cache[tool_name])

    return tools


def available() -> bool:
    """Check if this toolset is available based on system config.

    Superfluid tools are available for any EVM-compatible wallet (CDP, Safe/Privy).
    They don't require specific CDP credentials since they work with any wallet.
    """
    return True
