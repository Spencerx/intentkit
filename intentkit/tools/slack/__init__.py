"""Slack tools."""

import logging
from typing import TypedDict

from intentkit.tools.base import ToolsetConfig, ToolState
from intentkit.tools.slack.base import SlackBaseTool
from intentkit.tools.slack.get_channel import SlackGetChannel
from intentkit.tools.slack.get_message import SlackGetMessage
from intentkit.tools.slack.schedule_message import SlackScheduleMessage
from intentkit.tools.slack.send_message import SlackSendMessage

# we cache tools in system level, because they are stateless
_cache: dict[str, SlackBaseTool] = {}

logger = logging.getLogger(__name__)


class ToolStates(TypedDict):
    get_channel: ToolState
    get_message: ToolState
    schedule_message: ToolState
    send_message: ToolState


class Config(ToolsetConfig):
    """Configuration for Slack tools."""

    states: ToolStates
    slack_bot_token: str


async def get_tools(
    config: "Config",
    is_private: bool,
    **_,
) -> list[SlackBaseTool]:
    """Get all Slack tools."""
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
        tool = get_slack_tool(name)
        if tool:
            result.append(tool)
    return result


def get_slack_tool(
    name: str,
) -> SlackBaseTool | None:
    """Get a Slack tool by name.

    Args:
        name: The name of the tool to get

    Returns:
        The requested Slack tool
    """
    if name == "get_channel":
        if name not in _cache:
            _cache[name] = SlackGetChannel()
        return _cache[name]
    elif name == "get_message":
        if name not in _cache:
            _cache[name] = SlackGetMessage()
        return _cache[name]
    elif name == "schedule_message":
        if name not in _cache:
            _cache[name] = SlackScheduleMessage()
        return _cache[name]
    elif name == "send_message":
        if name not in _cache:
            _cache[name] = SlackSendMessage()
        return _cache[name]
    else:
        logger.warning("Unknown Slack tool: %s", name)
        return None


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return True
