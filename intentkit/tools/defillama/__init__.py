"""DeFi Llama tools."""

import logging
from typing import TypedDict

from intentkit.tools.base import ToolsetConfig, ToolState
from intentkit.tools.defillama.base import DefiLlamaBaseTool
from intentkit.tools.defillama.coins.fetch_batch_historical_prices import (
    DefiLlamaFetchBatchHistoricalPrices,
)
from intentkit.tools.defillama.coins.fetch_block import DefiLlamaFetchBlock

# Coins Tools
from intentkit.tools.defillama.coins.fetch_current_prices import (
    DefiLlamaFetchCurrentPrices,
)
from intentkit.tools.defillama.coins.fetch_first_price import DefiLlamaFetchFirstPrice
from intentkit.tools.defillama.coins.fetch_historical_prices import (
    DefiLlamaFetchHistoricalPrices,
)
from intentkit.tools.defillama.coins.fetch_price_chart import DefiLlamaFetchPriceChart
from intentkit.tools.defillama.coins.fetch_price_percentage import (
    DefiLlamaFetchPricePercentage,
)

# Fees Tools
from intentkit.tools.defillama.fees.fetch_fees_overview import (
    DefiLlamaFetchFeesOverview,
)
from intentkit.tools.defillama.stablecoins.fetch_stablecoin_chains import (
    DefiLlamaFetchStablecoinChains,
)
from intentkit.tools.defillama.stablecoins.fetch_stablecoin_charts import (
    DefiLlamaFetchStablecoinCharts,
)
from intentkit.tools.defillama.stablecoins.fetch_stablecoin_prices import (
    DefiLlamaFetchStablecoinPrices,
)

# Stablecoins Tools
from intentkit.tools.defillama.stablecoins.fetch_stablecoins import (
    DefiLlamaFetchStablecoins,
)
from intentkit.tools.defillama.tvl.fetch_chain_historical_tvl import (
    DefiLlamaFetchChainHistoricalTvl,
)
from intentkit.tools.defillama.tvl.fetch_chains import DefiLlamaFetchChains
from intentkit.tools.defillama.tvl.fetch_historical_tvl import (
    DefiLlamaFetchHistoricalTvl,
)
from intentkit.tools.defillama.tvl.fetch_protocol import DefiLlamaFetchProtocol
from intentkit.tools.defillama.tvl.fetch_protocol_current_tvl import (
    DefiLlamaFetchProtocolCurrentTvl,
)

# TVL Tools
from intentkit.tools.defillama.tvl.fetch_protocols import DefiLlamaFetchProtocols

# Volumes Tools
from intentkit.tools.defillama.volumes.fetch_dex_overview import (
    DefiLlamaFetchDexOverview,
)
from intentkit.tools.defillama.volumes.fetch_dex_summary import (
    DefiLlamaFetchDexSummary,
)
from intentkit.tools.defillama.volumes.fetch_options_overview import (
    DefiLlamaFetchOptionsOverview,
)
from intentkit.tools.defillama.yields.fetch_pool_chart import DefiLlamaFetchPoolChart

# Yields Tools
from intentkit.tools.defillama.yields.fetch_pools import DefiLlamaFetchPools

# we cache tools in system level, because they are stateless
_cache: dict[str, DefiLlamaBaseTool] = {}

logger = logging.getLogger(__name__)


class ToolStates(TypedDict):
    # TVL Tools
    fetch_protocols: ToolState
    fetch_protocol: ToolState
    fetch_historical_tvl: ToolState
    fetch_chain_historical_tvl: ToolState
    fetch_protocol_current_tvl: ToolState
    fetch_chains: ToolState

    # Coins Tools
    fetch_current_prices: ToolState
    fetch_historical_prices: ToolState
    fetch_batch_historical_prices: ToolState
    fetch_price_chart: ToolState
    fetch_price_percentage: ToolState
    fetch_first_price: ToolState
    fetch_block: ToolState

    # Stablecoins Tools
    fetch_stablecoins: ToolState
    fetch_stablecoin_charts: ToolState
    fetch_stablecoin_chains: ToolState
    fetch_stablecoin_prices: ToolState

    # Yields Tools
    fetch_pools: ToolState
    fetch_pool_chart: ToolState

    # Volumes Tools
    fetch_dex_overview: ToolState
    fetch_dex_summary: ToolState
    fetch_options_overview: ToolState

    # Fees Tools
    fetch_fees_overview: ToolState


class Config(ToolsetConfig):
    """Configuration for DeFi Llama tools."""

    states: ToolStates


async def get_tools(
    config: "Config",
    is_private: bool,
    **_,
) -> list[DefiLlamaBaseTool]:
    """Get all DeFi Llama tools."""
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
        tool = get_defillama_tool(name)
        if tool:
            result.append(tool)
    return result


def get_defillama_tool(
    name: str,
) -> DefiLlamaBaseTool | None:
    """Get a DeFi Llama tool by name.

    Args:
        name: The name of the tool to get

    Returns:
        The requested DeFi Llama tool

    Notes:
        Each tool maps to a specific DeFi Llama API endpoint. Some tools handle both
        base and chain-specific endpoints through optional parameters rather than
        separate implementations.
    """
    # TVL Tools
    if name == "fetch_protocols":
        if name not in _cache:
            _cache[name] = DefiLlamaFetchProtocols()
        return _cache[name]
    elif name == "fetch_protocol":
        if name not in _cache:
            _cache[name] = DefiLlamaFetchProtocol()
        return _cache[name]
    elif name == "fetch_historical_tvl":
        if name not in _cache:
            _cache[name] = DefiLlamaFetchHistoricalTvl()
        return _cache[name]
    elif name == "fetch_chain_historical_tvl":
        if name not in _cache:
            _cache[name] = DefiLlamaFetchChainHistoricalTvl()
        return _cache[name]
    elif name == "fetch_protocol_current_tvl":
        if name not in _cache:
            _cache[name] = DefiLlamaFetchProtocolCurrentTvl()
        return _cache[name]
    elif name == "fetch_chains":
        if name not in _cache:
            _cache[name] = DefiLlamaFetchChains()
        return _cache[name]

    # Coins Tools
    elif name == "fetch_current_prices":
        if name not in _cache:
            _cache[name] = DefiLlamaFetchCurrentPrices()
        return _cache[name]
    elif name == "fetch_historical_prices":
        if name not in _cache:
            _cache[name] = DefiLlamaFetchHistoricalPrices()
        return _cache[name]
    elif name == "fetch_batch_historical_prices":
        if name not in _cache:
            _cache[name] = DefiLlamaFetchBatchHistoricalPrices()
        return _cache[name]
    elif name == "fetch_price_chart":
        if name not in _cache:
            _cache[name] = DefiLlamaFetchPriceChart()
        return _cache[name]
    elif name == "fetch_price_percentage":
        if name not in _cache:
            _cache[name] = DefiLlamaFetchPricePercentage()
        return _cache[name]
    elif name == "fetch_first_price":
        if name not in _cache:
            _cache[name] = DefiLlamaFetchFirstPrice()
        return _cache[name]
    elif name == "fetch_block":
        if name not in _cache:
            _cache[name] = DefiLlamaFetchBlock()
        return _cache[name]

    # Stablecoins Tools
    elif name == "fetch_stablecoins":
        if name not in _cache:
            _cache[name] = DefiLlamaFetchStablecoins()
        return _cache[name]
    elif name == "fetch_stablecoin_charts":
        if name not in _cache:
            _cache[name] = DefiLlamaFetchStablecoinCharts()
        return _cache[name]
    elif name == "fetch_stablecoin_chains":
        if name not in _cache:
            _cache[name] = DefiLlamaFetchStablecoinChains()
        return _cache[name]
    elif name == "fetch_stablecoin_prices":
        if name not in _cache:
            _cache[name] = DefiLlamaFetchStablecoinPrices()
        return _cache[name]

    # Yields Tools
    elif name == "fetch_pools":
        if name not in _cache:
            _cache[name] = DefiLlamaFetchPools()
        return _cache[name]
    elif name == "fetch_pool_chart":
        if name not in _cache:
            _cache[name] = DefiLlamaFetchPoolChart()
        return _cache[name]

    # Volumes Tools
    elif name == "fetch_dex_overview":  # Handles both base and chain-specific overviews
        if name not in _cache:
            _cache[name] = DefiLlamaFetchDexOverview()
        return _cache[name]
    elif name == "fetch_dex_summary":
        if name not in _cache:
            _cache[name] = DefiLlamaFetchDexSummary()
        return _cache[name]
    elif (
        name == "fetch_options_overview"
    ):  # Handles both base and chain-specific overviews
        if name not in _cache:
            _cache[name] = DefiLlamaFetchOptionsOverview()
        return _cache[name]

    # Fees Tools
    elif (
        name == "fetch_fees_overview"
    ):  # Handles both base and chain-specific overviews
        if name not in _cache:
            _cache[name] = DefiLlamaFetchFeesOverview()
        return _cache[name]

    else:
        logger.warning("Unknown DeFi Llama tool: %s", name)
        return None


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return True
