"""Unit tests for the DeFi Llama API wrappers (fully mocked, no network).

Each fetch_* function is checked against the URL and query params it sends,
plus the shared error path (_get raises ToolException on non-200).
"""

from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.tools.base import ToolException

from intentkit.tools.defillama import api

FIXED_TIMESTAMP = 1677648000


class DummyResponse:
    def __init__(self, status_code, json_data):
        self.status_code = status_code
        self._json_data = json_data

    def json(self):
        return self._json_data


async def call_with_dummy(func, args, response):
    """Call func with httpx.AsyncClient mocked; return (result, get_mock)."""
    with patch("intentkit.tools.defillama.api.httpx.AsyncClient") as mock_client:
        client = AsyncMock()
        client.get.return_value = response
        mock_client.return_value.__aenter__.return_value = client
        with patch("intentkit.tools.defillama.api.datetime") as mock_datetime:
            mock_datetime.now.return_value.timestamp.return_value = FIXED_TIMESTAMP
            result = await func(*args)
    return result, client.get


# (function, args, expected_url, expected_params)
CASES = [
    (api.fetch_protocols, (), "https://api.llama.fi/protocols", None),
    (api.fetch_protocol, ("aave",), "https://api.llama.fi/protocol/aave", None),
    (
        api.fetch_historical_tvl,
        (),
        "https://api.llama.fi/v2/historicalChainTvl",
        None,
    ),
    (
        api.fetch_chain_historical_tvl,
        ("ethereum",),
        "https://api.llama.fi/v2/historicalChainTvl/ethereum",
        None,
    ),
    (
        api.fetch_protocol_current_tvl,
        ("aave",),
        "https://api.llama.fi/tvl/aave",
        None,
    ),
    (api.fetch_chains, (), "https://api.llama.fi/v2/chains", None),
    (
        api.fetch_current_prices,
        (["coingecko:ethereum", "coingecko:bitcoin"],),
        "https://coins.llama.fi/prices/current/coingecko:ethereum,coingecko:bitcoin?searchWidth=4h",
        None,
    ),
    (
        api.fetch_historical_prices,
        (
            1648680149,
            ["coingecko:ethereum"],
        ),
        "https://coins.llama.fi/prices/historical/1648680149/coingecko:ethereum?searchWidth=4h",
        None,
    ),
    (
        api.fetch_batch_historical_prices,
        ({"coingecko:ethereum": [1648680149]},),
        "https://coins.llama.fi/batchHistorical",
        {"coins": {"coingecko:ethereum": [1648680149]}, "searchWidth": "600"},
    ),
    (
        api.fetch_price_chart,
        (["coingecko:ethereum"],),
        "https://coins.llama.fi/chart/coingecko:ethereum",
        {
            "start": FIXED_TIMESTAMP - 86400,
            "span": 12,
            "period": "2h",
            "searchWidth": "600",
        },
    ),
    (
        api.fetch_price_percentage,
        (["coingecko:ethereum"],),
        "https://coins.llama.fi/percentage/coingecko:ethereum",
        {
            "timestamp": FIXED_TIMESTAMP,
            "lookForward": "false",
            "period": "24h",
        },
    ),
    (
        api.fetch_first_price,
        (["coingecko:ethereum"],),
        "https://coins.llama.fi/prices/first/coingecko:ethereum",
        None,
    ),
    (
        api.fetch_block,
        ("ethereum",),
        f"https://coins.llama.fi/block/ethereum/{FIXED_TIMESTAMP}",
        None,
    ),
    (
        api.fetch_stablecoins,
        (),
        "https://stablecoins.llama.fi/stablecoins",
        {"includePrices": "true"},
    ),
    (
        api.fetch_stablecoin_charts,
        ("1",),
        "https://stablecoins.llama.fi/stablecoincharts/all?stablecoin=1",
        None,
    ),
    (
        api.fetch_stablecoin_charts,
        ("1", "ethereum"),
        "https://stablecoins.llama.fi/stablecoincharts/ethereum?stablecoin=1",
        None,
    ),
    (
        api.fetch_stablecoin_chains,
        (),
        "https://stablecoins.llama.fi/stablecoinchains",
        None,
    ),
    (
        api.fetch_stablecoin_prices,
        (),
        "https://stablecoins.llama.fi/stablecoinprices",
        None,
    ),
    (api.fetch_pools, (), "https://yields.llama.fi/pools", None),
    (
        api.fetch_pool_chart,
        ("pool-id",),
        "https://yields.llama.fi/chart/pool-id",
        None,
    ),
    (
        api.fetch_dex_overview,
        (),
        "https://api.llama.fi/overview/dexs",
        {
            "excludeTotalDataChart": "true",
            "excludeTotalDataChartBreakdown": "true",
            "dataType": "dailyVolume",
        },
    ),
    (
        api.fetch_dex_summary,
        ("uniswap",),
        "https://api.llama.fi/summary/dexs/uniswap",
        {
            "excludeTotalDataChart": "true",
            "excludeTotalDataChartBreakdown": "true",
            "dataType": "dailyVolume",
        },
    ),
    (
        api.fetch_options_overview,
        (),
        "https://api.llama.fi/overview/options",
        {
            "excludeTotalDataChart": "true",
            "excludeTotalDataChartBreakdown": "true",
            "dataType": "dailyPremiumVolume",
        },
    ),
    (
        api.fetch_fees_overview,
        (),
        "https://api.llama.fi/overview/fees",
        {
            "excludeTotalDataChart": "true",
            "excludeTotalDataChartBreakdown": "true",
            "dataType": "dailyFees",
        },
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "func,args,expected_url,expected_params",
    CASES,
    ids=lambda v: v.__name__ if callable(v) else None,
)
async def test_fetch_sends_expected_request(func, args, expected_url, expected_params):
    payload = {"data": "ok"}
    result, get_mock = await call_with_dummy(func, args, DummyResponse(200, payload))
    assert result == payload
    get_mock.assert_called_once_with(expected_url, params=expected_params)


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [404, 500])
async def test_non_200_raises_tool_exception(status_code):
    with pytest.raises(ToolException, match=str(status_code)):
        await call_with_dummy(api.fetch_protocols, (), DummyResponse(status_code, None))
