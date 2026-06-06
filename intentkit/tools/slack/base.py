from langchain_core.tools.base import ToolException
from pydantic import BaseModel
from slack_sdk import WebClient

from intentkit.tools.base import IntentKitTool


class SlackBaseTool(IntentKitTool):
    """Base class for Slack tools."""

    def get_api_key(self):
        context = self.get_context()
        tool_config = context.agent.tool_config(self.category)
        slack_bot_token = tool_config.get("slack_bot_token")
        if not slack_bot_token:
            raise ToolException("Missing required slack_bot_token in configuration")
        return slack_bot_token

    category: str = "slack"

    def get_client(self, token: str) -> WebClient:
        """Get a Slack WebClient instance.

        Args:
            token: The Slack bot token to use

        Returns:
            WebClient: A configured Slack client
        """
        return WebClient(token=token)


class SlackChannel(BaseModel):
    """Model representing a Slack channel."""

    id: str
    name: str
    is_private: bool
    created: int
    creator: str
    is_archived: bool
    members: list[str] = []


class SlackMessage(BaseModel):
    """Model representing a Slack message."""

    ts: str
    text: str
    user: str
    channel: str
    thread_ts: str | None = None
