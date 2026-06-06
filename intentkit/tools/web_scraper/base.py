from langchain_core.tools.base import ToolException

from intentkit.config.config import config
from intentkit.tools.base import IntentKitTool


class WebScraperBaseTool(IntentKitTool):
    """Base class for web scraper tools."""

    category: str = "web_scraper"

    def get_openai_api_key(self) -> str:
        """Retrieve the OpenAI API key for embedding operations."""
        if not config.openai_api_key:
            raise ToolException("OpenAI API key is not configured")
        return config.openai_api_key
