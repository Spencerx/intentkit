from langchain_core.tools.base import ToolException

from intentkit.config.config import config
from intentkit.tools.base import IntentKitTool

ALLORA_BASE_URL = "https://api.upshot.xyz/v2/allora"


class AlloraBaseTool(IntentKitTool):
    """Base class for Allora tools."""

    def get_api_key(self):
        if not config.allora_api_key:
            raise ToolException("Allora API key is not configured")
        return config.allora_api_key

    category: str = "allora"
