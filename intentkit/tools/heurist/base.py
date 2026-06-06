"""Base class for Heurist AI tools."""

from langchain_core.tools.base import ToolException

from intentkit.config.config import config
from intentkit.tools.base import IntentKitTool


class HeuristBaseTool(IntentKitTool):
    """Base class for all Heurist AI tools.

    This class provides common functionality for all Heurist AI tools.
    """

    def get_api_key(self):
        if not config.heurist_api_key:
            raise ToolException("Heurist API key is not configured")
        return config.heurist_api_key

    category: str = "heurist"
