import pytest

from intentkit.models.agent import Agent


@pytest.mark.asyncio
async def test_agent_get_json_schema_includes_toolsets():
    """Test that Agent.get_json_schema includes toolsets from schema.json files."""
    schema = await Agent.get_json_schema()

    tools_schema = schema["properties"]["tools"]["properties"]
    # erc20 should be present since it has a schema.json
    assert "erc20" in tools_schema
    states = tools_schema["erc20"]["properties"]["states"]["properties"]
    assert "erc20_get_balance" in states
    assert "erc20_transfer" in states
