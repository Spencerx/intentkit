"""Base module for CryptoPanic tools.

Defines the base class and shared utilities for CryptoPanic tools.
"""

from langchain_core.tools.base import ToolException

from intentkit.config.config import config
from intentkit.tools.base import IntentKitTool

base_url = "https://cryptopanic.com/api/v1/posts/"


class CryptopanicBaseTool(IntentKitTool):
    """Base class for CryptoPanic tools.

    Provides common functionality for interacting with the CryptoPanic API,
    including API key retrieval and shared helpers.
    """

    category: str = "cryptopanic"

    def get_api_key(self):
        if not config.cryptopanic_api_key:
            raise ToolException("CryptoPanic API key is not configured")
        return config.cryptopanic_api_key
