from langchain_core.tools.base import ToolException

from intentkit.config.config import config
from intentkit.tools.base import IntentKitTool

AIXBT_BASE_URL = "https://api.aixbt.tech/v1"


class AIXBTBaseTool(IntentKitTool):
    """Base class for AIXBT API tools."""

    category: str = "aixbt"

    def get_api_key(self) -> str:
        if not config.aixbt_api_key:
            raise ToolException("AIXBT API key is not configured")
        return config.aixbt_api_key
