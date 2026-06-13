"""Coarse-visibility behavior of the MCP toolset wrapper.

An MCP category exposes a single server-level visibility toggle (keyed by the
server name); when it permits the caller, every live-discovered tool is exposed.
There are no per-tool toggles, so a remote tool-list change can't leave the
config stale. These tests mock discovery, so they never touch the network.
"""

from unittest.mock import AsyncMock, patch

import pytest

from intentkit.tools.mcp.wrapper import McpCategoryModule

_FAKE_INSTANCES = {
    "mcp_coingecko_execute": object(),
    "mcp_coingecko_search_docs": object(),
}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "visibility,is_private,expect_count",
    [
        ("disabled", False, 0),
        ("disabled", True, 0),
        ("public", False, 2),
        ("public", True, 2),
        ("private", False, 0),  # private toolset hidden from non-owner
        ("private", True, 2),  # owner sees it
        (None, False, 0),  # unset
    ],
)
async def test_visibility_gating(visibility, is_private, expect_count):
    module = McpCategoryModule("mcp_coingecko")
    states = {"mcp_coingecko": visibility} if visibility is not None else {}
    with patch(
        "intentkit.tools.mcp.wrapper._get_mcp_tool_instances",
        new=AsyncMock(return_value=dict(_FAKE_INSTANCES)),
    ) as mock_discover:
        tools = await module.get_tools({"states": states}, is_private)

    assert len(tools) == expect_count
    if expect_count == 0:
        # Gated off before any network discovery.
        mock_discover.assert_not_called()


@pytest.mark.asyncio
async def test_stale_per_tool_keys_resolve_to_nothing():
    """Pre-coarse configs keyed by individual tool names must not silently
    expose the whole server."""
    module = McpCategoryModule("mcp_coingecko")
    states = {"mcp_coingecko_get_price": "public"}  # stale snapshot key
    with patch(
        "intentkit.tools.mcp.wrapper._get_mcp_tool_instances",
        new=AsyncMock(return_value=dict(_FAKE_INSTANCES)),
    ) as mock_discover:
        tools = await module.get_tools({"states": states}, True)

    assert tools == []
    mock_discover.assert_not_called()
