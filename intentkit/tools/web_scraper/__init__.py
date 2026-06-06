"""Web scraper tools for content indexing and retrieval."""

import logging
from typing import TypedDict

from intentkit.config.config import config as system_config
from intentkit.tools.base import ToolOwnerState, ToolsetConfig, ToolState
from intentkit.tools.web_scraper.base import WebScraperBaseTool
from intentkit.tools.web_scraper.document_indexer import DocumentIndexer
from intentkit.tools.web_scraper.scrape_and_index import (
    QueryIndexedContent,
    ScrapeAndIndex,
)
from intentkit.tools.web_scraper.website_indexer import WebsiteIndexer

# Cache tools at the system level, because they are stateless
_cache: dict[str, WebScraperBaseTool] = {}

logger = logging.getLogger(__name__)


class ToolStates(TypedDict):
    scrape_and_index: ToolOwnerState
    query_indexed_content: ToolState
    website_indexer: ToolOwnerState
    document_indexer: ToolOwnerState


class Config(ToolsetConfig):
    """Configuration for web scraper tools."""

    states: ToolStates


async def get_tools(
    config: "Config",
    is_private: bool,
    **_,
) -> list[WebScraperBaseTool]:
    """Get all web scraper tools.

    Args:
        config: The configuration for web scraper tools.
        is_private: Whether to include private tools.

    Returns:
        A list of web scraper tools.
    """
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
        tool = get_web_scraper_tool(name)
        if tool:
            result.append(tool)
    return result


def get_web_scraper_tool(
    name: str,
) -> WebScraperBaseTool | None:
    """Get a web scraper tool by name.

    Args:
        name: The name of the tool to get

    Returns:
        The requested web scraper tool
    """
    if name == "scrape_and_index":
        if name not in _cache:
            _cache[name] = ScrapeAndIndex()
        return _cache[name]
    elif name == "query_indexed_content":
        if name not in _cache:
            _cache[name] = QueryIndexedContent()
        return _cache[name]
    elif name == "website_indexer":
        if name not in _cache:
            _cache[name] = WebsiteIndexer()
        return _cache[name]
    elif name == "document_indexer":
        if name not in _cache:
            _cache[name] = DocumentIndexer()
        return _cache[name]
    else:
        logger.warning("Unknown web scraper tool: %s", name)
        return None


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return bool(system_config.openai_api_key)
