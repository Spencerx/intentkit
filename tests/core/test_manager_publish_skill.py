"""Tests for the manager-agent publish_agent skill."""

from __future__ import annotations

import json
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from intentkit.abstracts.graph import AgentContext
from intentkit.models.agent import AgentPublicInfo, AgentTag
from intentkit.utils.error import IntentKitAPIError

SKILL_MODULE = "intentkit.core.manager.skills.publish"


@pytest.fixture
def manager_runtime():
    """Mock the AgentContext seen by manager skills."""
    mock_context = MagicMock(spec=AgentContext)
    mock_context.agent_id = "agent-1"
    mock_context.user_id = "user-1"
    mock_context.team_id = "team-1"
    with patch("intentkit.skills.base.get_runtime") as mock_get_runtime:
        mock_get_runtime.return_value.context = mock_context
        yield mock_get_runtime, mock_context


def _publish_payload(**overrides):
    payload = {
        "description": "An assistant",
        "example_intro": "Try one of these:",
        "examples": [{"name": "n", "description": "d", "prompt": "p"}],
        "tags": ["music", "movies"],
    }
    payload.update(overrides)
    return payload


def _stub_published_agent() -> AgentPublicInfo:
    """Return an AgentPublicInfo-shaped object the skill's serialiser can read."""
    return AgentPublicInfo(
        description="An assistant",
        example_intro="Try one of these:",
        examples=[],
        tags=["music"],
        fee_percentage=Decimal("1"),
    )


@pytest.mark.asyncio
async def test_publish_skill_forces_fee_one_and_passes_fields(manager_runtime):
    from intentkit.core.manager.skills.publish import publish_agent_skill

    with (
        patch(
            f"{SKILL_MODULE}.get_latest_public_info",
            new=AsyncMock(return_value=MagicMock()),
        ),
        patch(
            f"{SKILL_MODULE}.publish_agent",
            new=AsyncMock(return_value=_stub_published_agent()),
        ) as mock_publish,
    ):
        result = await publish_agent_skill._arun(  # pyright: ignore[reportPrivateUsage]
            publish_input=_publish_payload()
        )

    # Returns JSON-serialised public info from the updated agent.
    parsed = json.loads(result)
    assert isinstance(parsed, dict)

    # Verify the AgentPublicInfo handed to publish_agent has fee=1 and the
    # four explicit fields, with all other fields left unset so existing
    # values on the agent are preserved.
    assert mock_publish.await_count == 1
    assert mock_publish.await_args is not None
    public_info: AgentPublicInfo = mock_publish.await_args.kwargs["public_info"]
    assert public_info.description == "An assistant"
    assert public_info.example_intro == "Try one of these:"
    assert len(public_info.examples or []) == 1
    assert public_info.tags == ["music", "movies"]
    assert public_info.fee_percentage == Decimal("1")
    for skipped in (
        "ticker",
        "token_address",
        "token_pool",
        "external_website",
        "x402_price",
        "public_extra",
    ):
        assert skipped not in public_info.model_fields_set


@pytest.mark.asyncio
async def test_publish_skill_omits_tags_when_none(manager_runtime):
    from intentkit.core.manager.skills.publish import publish_agent_skill

    with (
        patch(
            f"{SKILL_MODULE}.get_latest_public_info",
            new=AsyncMock(return_value=MagicMock()),
        ),
        patch(
            f"{SKILL_MODULE}.publish_agent",
            new=AsyncMock(return_value=_stub_published_agent()),
        ) as mock_publish,
    ):
        await publish_agent_skill._arun(  # pyright: ignore[reportPrivateUsage]
            publish_input=_publish_payload(tags=None)
        )

    assert mock_publish.await_args is not None
    public_info: AgentPublicInfo = mock_publish.await_args.kwargs["public_info"]
    assert public_info.tags is None
    assert public_info.fee_percentage == Decimal("1")


@pytest.mark.asyncio
async def test_publish_skill_rejects_unknown_tag(manager_runtime):
    """Pydantic validates the enum so the LLM can't fabricate tag values."""
    from intentkit.core.manager.skills.publish import publish_agent_skill

    with (
        patch(
            f"{SKILL_MODULE}.get_latest_public_info",
            new=AsyncMock(return_value=MagicMock()),
        ),
        patch(f"{SKILL_MODULE}.publish_agent", new=AsyncMock()),
    ):
        with pytest.raises(Exception):
            await publish_agent_skill._arun(  # pyright: ignore[reportPrivateUsage]
                publish_input=_publish_payload(tags=["not-a-real-tag"])
            )


@pytest.mark.asyncio
async def test_publish_skill_handles_quota_reached(manager_runtime):
    from intentkit.core.manager.skills.publish import publish_agent_skill

    with (
        patch(
            f"{SKILL_MODULE}.get_latest_public_info",
            new=AsyncMock(return_value=MagicMock()),
        ),
        patch(
            f"{SKILL_MODULE}.publish_agent",
            new=AsyncMock(
                side_effect=IntentKitAPIError(403, "PublicAgentLimitReached", "limit")
            ),
        ),
    ):
        result = await publish_agent_skill._arun(  # pyright: ignore[reportPrivateUsage]
            publish_input=_publish_payload()
        )

    assert "public-agent limit" in result.lower()


@pytest.mark.asyncio
async def test_publish_skill_handles_agent_not_found(manager_runtime):
    from intentkit.core.manager.skills.publish import publish_agent_skill

    with patch(
        f"{SKILL_MODULE}.get_latest_public_info",
        new=AsyncMock(side_effect=IntentKitAPIError(404, "AgentNotFound", "missing")),
    ):
        result = await publish_agent_skill._arun(  # pyright: ignore[reportPrivateUsage]
            publish_input=_publish_payload()
        )

    assert "Agent not found" in result


@pytest.mark.asyncio
async def test_publish_skill_uses_agent_tag_enum_values():
    """Sanity check: our test payload tag values are real AgentTag values."""
    valid = {t.value for t in AgentTag}
    payload = _publish_payload()
    assert payload["tags"] is not None
    for t in payload["tags"]:
        assert t in valid
