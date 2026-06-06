import pytest

from intentkit.core.agent.management import create_agent
from intentkit.models.agent import AgentCreate
from intentkit.utils.error import IntentKitAPIError

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.mark.bdd
async def test_create_agent_rejects_invalid_toolset():
    agent = AgentCreate(
        id="test-tool-val-1",
        name="Tool Test",
        model="gpt-4o-mini",
        tools={"nonexistent": {"enabled": True, "states": {"x": "public"}}},
    )
    with pytest.raises(IntentKitAPIError, match="nonexistent"):
        await create_agent(agent)


@pytest.mark.bdd
async def test_create_agent_rejects_invalid_tool_name():
    agent = AgentCreate(
        id="test-tool-val-2",
        name="Tool Test",
        model="gpt-4o-mini",
        tools={"ui": {"enabled": True, "states": {"fake_tool": "public"}}},
    )
    with pytest.raises(IntentKitAPIError, match="fake_tool"):
        await create_agent(agent)


@pytest.mark.bdd
async def test_create_agent_accepts_valid_tools():
    agent = AgentCreate(
        id="test-tool-val-3",
        name="Tool Test Valid",
        model="gpt-4o-mini",
        tools={"ui": {"enabled": True, "states": {"ui_show_card": "public"}}},
    )
    created, _ = await create_agent(agent)
    assert created.tools is not None
    assert created.tools["ui"]["states"]["ui_show_card"] == "public"
