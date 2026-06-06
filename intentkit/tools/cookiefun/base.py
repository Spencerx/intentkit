import logging

from langchain_core.tools.base import ToolException

from intentkit.config.config import config
from intentkit.tools.base import IntentKitTool

logger = logging.getLogger(__name__)


class CookieFunBaseTool(IntentKitTool):
    """Base class for CookieFun tools."""

    category: str = "cookiefun"

    def get_api_key(self) -> str:
        if not config.cookiefun_api_key:
            raise ToolException("CookieFun API key is not configured")
        return config.cookiefun_api_key
