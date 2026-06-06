"""OpenSea NFT marketplace tools."""

import logging
from typing import TypedDict

from intentkit.config.config import config as system_config
from intentkit.tools.base import IntentKitTool, ToolsetConfig, ToolState
from intentkit.tools.opensea.buy_nft import OpenSeaBuyNft
from intentkit.tools.opensea.cancel_listing import OpenSeaCancelListing
from intentkit.tools.opensea.create_listing import OpenSeaCreateListing
from intentkit.tools.opensea.get_collection import OpenSeaGetCollection
from intentkit.tools.opensea.get_collection_stats import OpenSeaGetCollectionStats
from intentkit.tools.opensea.get_events import OpenSeaGetEvents
from intentkit.tools.opensea.get_listings import OpenSeaGetListings
from intentkit.tools.opensea.get_nft import OpenSeaGetNft
from intentkit.tools.opensea.get_nfts_by_account import OpenSeaGetNftsByAccount
from intentkit.tools.opensea.get_offers import OpenSeaGetOffers
from intentkit.tools.opensea.update_listing import OpenSeaUpdateListing

# Cache tools at the system level, because they are stateless
_cache: dict[str, IntentKitTool] = {}

logger = logging.getLogger(__name__)


class ToolStates(TypedDict):
    opensea_get_collection: ToolState
    opensea_get_collection_stats: ToolState
    opensea_get_nft: ToolState
    opensea_get_listings: ToolState
    opensea_get_offers: ToolState
    opensea_get_events: ToolState
    opensea_get_nfts_by_account: ToolState
    opensea_create_listing: ToolState
    opensea_buy_nft: ToolState
    opensea_cancel_listing: ToolState
    opensea_update_listing: ToolState


_TOOL_NAME_TO_CLASS_MAP: dict[str, type[IntentKitTool]] = {
    "opensea_get_collection": OpenSeaGetCollection,
    "opensea_get_collection_stats": OpenSeaGetCollectionStats,
    "opensea_get_nft": OpenSeaGetNft,
    "opensea_get_listings": OpenSeaGetListings,
    "opensea_get_offers": OpenSeaGetOffers,
    "opensea_get_events": OpenSeaGetEvents,
    "opensea_get_nfts_by_account": OpenSeaGetNftsByAccount,
    "opensea_create_listing": OpenSeaCreateListing,
    "opensea_buy_nft": OpenSeaBuyNft,
    "opensea_cancel_listing": OpenSeaCancelListing,
    "opensea_update_listing": OpenSeaUpdateListing,
}


class Config(ToolsetConfig):
    """Configuration for OpenSea tools."""

    enabled: bool
    states: ToolStates


async def get_tools(
    config: "Config",
    is_private: bool,
    **_,
) -> list[IntentKitTool]:
    """Get all OpenSea tools based on config states.

    Args:
        config: The configuration for OpenSea tools.
        is_private: Whether to include private tools.

    Returns:
        A list of OpenSea tools.
    """
    available_tools = []

    for tool_name, state in config["states"].items():
        if state == "disabled":
            continue
        elif state == "public" or (state == "private" and is_private):
            available_tools.append(tool_name)

    logger.debug("Available OpenSea tools: %s", available_tools)

    result = []
    for name in available_tools:
        tool = _get_tool(name)
        if tool:
            result.append(tool)
    return result


def _get_tool(name: str) -> IntentKitTool | None:
    """Get an OpenSea tool by name, using cache."""
    if name in _cache:
        return _cache[name]

    tool_class = _TOOL_NAME_TO_CLASS_MAP.get(name)
    if not tool_class:
        logger.warning("Unknown OpenSea tool: %s", name)
        return None

    _cache[name] = tool_class()  # pyright: ignore[reportCallIssue]
    return _cache[name]


def available() -> bool:
    """Check if OpenSea tools are available (API key configured)."""
    return bool(system_config.opensea_api_key)
