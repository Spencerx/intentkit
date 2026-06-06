"""CryptoPanic tool module for IntentKit.

Loads and initializes tools for fetching crypto news and providing market insights using CryptoPanic API.
"""

import logging
from typing import TypedDict

from intentkit.config.config import config as system_config
from intentkit.tools.base import ToolsetConfig, ToolState

from .base import CryptopanicBaseTool

logger = logging.getLogger(__name__)

# Cache for tool instances
_tool_cache: dict[str, CryptopanicBaseTool] = {}


class ToolStates(TypedDict):
    """Type definition for CryptoPanic tool states."""

    fetch_crypto_news: ToolState
    fetch_crypto_sentiment: ToolState


class Config(ToolsetConfig):
    """Configuration schema for CryptoPanic tools."""

    states: ToolStates


async def get_tools(
    config: Config,
    is_private: bool,
    **kwargs,
) -> list[CryptopanicBaseTool]:
    """Load CryptoPanic tools based on configuration.

    Args:
        config: Tool configuration with states and API key.
        is_private: Whether the context is private (affects tool visibility).
        store: Tool store for accessing other tools.
        **kwargs: Additional keyword arguments.

    Returns:
        List of loaded CryptoPanic tool instances.
    """
    logger.info("Loading CryptoPanic tools")
    available_tools = []

    for tool_name, state in config["states"].items():
        logger.debug("Checking tool: %s, state: %s", tool_name, state)
        if state == "disabled":
            continue
        if state == "public" or (state == "private" and is_private):
            available_tools.append(tool_name)

    loaded_tools = []
    for name in available_tools:
        tool = get_cryptopanic_tool(name)
        if tool:
            logger.info("Successfully loaded tool: %s", name)
            loaded_tools.append(tool)
        else:
            logger.warning("Failed to load tool: %s", name)

    return loaded_tools


def get_cryptopanic_tool(
    name: str,
) -> CryptopanicBaseTool | None:
    """Retrieve a CryptoPanic tool instance by name.

    Args:
        name: Name of the tool (e.g., 'fetch_crypto_news', 'fetch_crypto_sentiment').
        store: Tool store for accessing other tools.

    Returns:
        CryptoPanic tool instance or None if not found or import fails.
    """
    if name in _tool_cache:
        logger.debug("Retrieved cached tool: %s", name)
        return _tool_cache[name]

    try:
        if name == "fetch_crypto_news":
            from .fetch_crypto_news import FetchCryptoNews

            _tool_cache[name] = FetchCryptoNews()
        elif name == "fetch_crypto_sentiment":
            from .fetch_crypto_sentiment import FetchCryptoSentiment

            _tool_cache[name] = FetchCryptoSentiment()
        else:
            logger.warning("Unknown CryptoPanic tool: %s", name)
            return None

        logger.debug("Cached new tool instance: %s", name)
        return _tool_cache[name]

    except ImportError as e:
        logger.error("Failed to import CryptoPanic tool %s: %s", name, e)
        return None


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return bool(system_config.cryptopanic_api_key)
