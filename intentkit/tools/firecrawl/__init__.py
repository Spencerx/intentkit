"""Firecrawl tools for web scraping and crawling."""

import logging
from typing import NotRequired, TypedDict

from intentkit.config.config import config as system_config
from intentkit.tools.base import ToolsetConfig, ToolState
from intentkit.tools.firecrawl.base import FirecrawlBaseTool
from intentkit.tools.firecrawl.clear import FirecrawlClearIndexedContent
from intentkit.tools.firecrawl.crawl import FirecrawlCrawl
from intentkit.tools.firecrawl.query import FirecrawlQueryIndexedContent
from intentkit.tools.firecrawl.scrape import FirecrawlScrape

# Cache tools at the system level, because they are stateless
_cache: dict[str, FirecrawlBaseTool] = {}

logger = logging.getLogger(__name__)


class ToolStates(TypedDict):
    firecrawl_scrape: ToolState
    firecrawl_crawl: ToolState
    firecrawl_query_indexed_content: ToolState
    firecrawl_clear_indexed_content: ToolState


class Config(ToolsetConfig):
    """Configuration for Firecrawl tools."""

    states: ToolStates
    rate_limit_number: NotRequired[int]
    rate_limit_minutes: NotRequired[int]


async def get_tools(
    config: "Config",
    is_private: bool,
    **_,
) -> list[FirecrawlBaseTool]:
    """Get all Firecrawl tools.

    Args:
        config: The configuration for Firecrawl tools.
        is_private: Whether to include private tools.

    Returns:
        A list of Firecrawl tools.
    """
    available_tools = []

    # Include tools based on their state
    for tool_name, state in config["states"].items():
        if state == "disabled":
            continue
        elif state == "public" or (state == "private" and is_private):
            available_tools.append(tool_name)

    # Get each tool using the cached getter
    return [s for name in available_tools if (s := get_firecrawl_tool(name))]


def get_firecrawl_tool(
    name: str,
) -> FirecrawlBaseTool | None:
    """Get a Firecrawl tool by name."""
    if name == "firecrawl_scrape":
        if name not in _cache:
            _cache[name] = FirecrawlScrape()
        return _cache[name]
    elif name == "firecrawl_crawl":
        if name not in _cache:
            _cache[name] = FirecrawlCrawl()
        return _cache[name]
    elif name == "firecrawl_query_indexed_content":
        if name not in _cache:
            _cache[name] = FirecrawlQueryIndexedContent()
        return _cache[name]
    elif name == "firecrawl_clear_indexed_content":
        if name not in _cache:
            _cache[name] = FirecrawlClearIndexedContent()
        return _cache[name]
    else:
        logger.warning("Unknown Firecrawl tool: %s", name)
        return None


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return bool(system_config.firecrawl_api_key)
