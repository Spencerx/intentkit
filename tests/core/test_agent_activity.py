import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

import intentkit.core.agent_activity as agent_activity_module
from intentkit.core.agent.info import AgentInfo
from intentkit.core.agent_activity import (
    _format_activity_push,
    create_agent_activity,
    get_agent_activities,
    get_agent_activity,
)
from intentkit.models.agent_activity import (
    AgentActivity,
    AgentActivityCreate,
    AgentActivityTable,
)


def _patch_agent_info(monkeypatch, infos: dict[str, AgentInfo]):
    """Route read-time enrichment to a canned agent info map."""

    async def fake_get_agent_infos(agent_ids):
        return {aid: infos[aid] for aid in agent_ids if aid in infos}

    monkeypatch.setattr(
        "intentkit.core.agent.info.get_agent_infos", fake_get_agent_infos
    )


@pytest.mark.asyncio
async def test_create_agent_activity(monkeypatch):
    # Mock session
    mock_session = AsyncMock()
    mock_session.add = MagicMock()

    async def mock_refresh(obj):
        obj.id = "activity-123"
        obj.created_at = datetime.now()

    mock_session.refresh.side_effect = mock_refresh

    mock_session_cls = MagicMock()
    mock_session_cls.__aenter__.return_value = mock_session
    mock_session_cls.__aexit__.return_value = None

    monkeypatch.setattr(agent_activity_module, "get_session", lambda: mock_session_cls)

    activity_create = AgentActivityCreate(
        agent_id="agent-1",
        text="Test Activity",
        images=["img1.jpg"],
        video="video.mp4",
        post_id="post-1",
    )

    result = await create_agent_activity(activity_create)

    # Verify session usage
    assert mock_session.add.called
    assert mock_session.commit.called
    assert mock_session.refresh.called

    # Verify result
    assert isinstance(result, AgentActivity)
    assert result.agent_id == "agent-1"
    assert result.text == "Test Activity"
    assert result.images == ["img1.jpg"]
    assert result.video == "video.mp4"
    assert result.post_id == "post-1"
    assert result.id == "activity-123"


@pytest.mark.asyncio
async def test_get_agent_activity_cache_hit(monkeypatch):
    activity_id = "activity-123"
    cached_data = {
        "id": activity_id,
        "agent_id": "agent-1",
        "text": "Cached Activity",
        "images": [],
        "video": None,
        "post_id": None,
        "created_at": datetime.now().isoformat(),
    }

    # Mock Redis
    mock_redis = AsyncMock()
    mock_redis.get.return_value = json.dumps(cached_data)

    monkeypatch.setattr(agent_activity_module, "get_redis", lambda: mock_redis)

    _patch_agent_info(
        monkeypatch,
        {"agent-1": AgentInfo(id="agent-1", name="Fresh Name", picture="pic.png")},
    )

    result = await get_agent_activity(activity_id)

    # Verify usage
    mock_redis.get.assert_called_with(f"intentkit:agent_activity:{activity_id}")

    assert isinstance(result, AgentActivity)
    assert result.id == activity_id
    assert result.text == "Cached Activity"
    # Agent display info is resolved at read time, even on a cache hit.
    assert result.agent_name == "Fresh Name"
    assert result.agent_picture == "pic.png"


@pytest.mark.asyncio
async def test_get_agent_activity_cache_miss_db_hit(monkeypatch):
    activity_id = "activity-123"

    # Mock Redis (Miss then Set)
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    monkeypatch.setattr(agent_activity_module, "get_redis", lambda: mock_redis)

    # Mock DB Result
    db_activity = AgentActivityTable(
        id=activity_id,
        agent_id="agent-1",
        text="DB Activity",
        images=None,
        video=None,
        post_id=None,
        created_at=datetime.now(),
    )

    # Mock Session
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = db_activity
    mock_session.execute.return_value = mock_result

    mock_session_ctx = MagicMock()
    mock_session_ctx.__aenter__.return_value = mock_session
    mock_session_ctx.__aexit__.return_value = None
    monkeypatch.setattr(agent_activity_module, "get_session", lambda: mock_session_ctx)

    _patch_agent_info(
        monkeypatch, {"agent-1": AgentInfo(id="agent-1", name="DB Agent")}
    )

    result = await get_agent_activity(activity_id)

    # Verify
    mock_redis.get.assert_called_once()
    mock_session.execute.assert_called_once()
    mock_redis.set.assert_called_once()

    # The redis payload stays lean: agent info is attached after caching.
    cached_payload = json.loads(mock_redis.set.call_args.args[1])
    assert cached_payload["agent_name"] is None

    assert isinstance(result, AgentActivity)
    assert result.text == "DB Activity"
    assert result.agent_name == "DB Agent"


@pytest.mark.asyncio
async def test_get_agent_activity_db_miss(monkeypatch):
    activity_id = "activity-missing"

    # Mock Redis
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    monkeypatch.setattr(agent_activity_module, "get_redis", lambda: mock_redis)

    # Mock Session
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    mock_session_ctx = MagicMock()
    mock_session_ctx.__aenter__.return_value = mock_session
    mock_session_ctx.__aexit__.return_value = None
    monkeypatch.setattr(agent_activity_module, "get_session", lambda: mock_session_ctx)

    result = await get_agent_activity(activity_id)

    assert result is None
    assert not mock_redis.set.called


@pytest.mark.asyncio
async def test_get_agent_activities(monkeypatch):
    agent_id = "agent-1"

    # Create mock db activities
    db_activities = [
        AgentActivityTable(
            id=f"activity-{i}",
            agent_id=agent_id,
            text=f"Activity {i}",
            images=None,
            video=None,
            post_id=None,
            created_at=datetime.now(),
        )
        for i in range(3)
    ]

    # Mock Session
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = db_activities
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute.return_value = mock_result

    mock_session_ctx = MagicMock()
    mock_session_ctx.__aenter__.return_value = mock_session
    mock_session_ctx.__aexit__.return_value = None
    monkeypatch.setattr(agent_activity_module, "get_session", lambda: mock_session_ctx)

    _patch_agent_info(
        monkeypatch,
        {agent_id: AgentInfo(id=agent_id, name="Agent One", picture="one.png")},
    )

    result = await get_agent_activities(agent_id, limit=10)

    # Verify
    mock_session.execute.assert_called_once()
    assert len(result) == 3
    for i, activity in enumerate(result):
        assert isinstance(activity, AgentActivity)
        assert activity.id == f"activity-{i}"
        assert activity.text == f"Activity {i}"
        assert activity.agent_name == "Agent One"
        assert activity.agent_picture == "one.png"


@pytest.mark.asyncio
async def test_get_agent_activities_empty(monkeypatch):
    agent_id = "agent-no-activities"

    # Mock Session with empty result
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute.return_value = mock_result

    mock_session_ctx = MagicMock()
    mock_session_ctx.__aenter__.return_value = mock_session
    mock_session_ctx.__aexit__.return_value = None
    monkeypatch.setattr(agent_activity_module, "get_session", lambda: mock_session_ctx)

    result = await get_agent_activities(agent_id)

    assert result == []


def _make_activity(**overrides) -> AgentActivity:
    base = {
        "id": "activity-1",
        "agent_id": "agent-1",
        "text": "hello world",
        "images": None,
        "video": None,
        "link": None,
        "link_meta": None,
        "post_id": None,
        "created_at": datetime.now(),
    }
    base.update(overrides)
    return AgentActivity.model_validate(base)


# The caller (_push_activity_to_teams) enriches the activity before formatting.


@pytest.mark.asyncio
async def test_format_activity_push_plain():
    activity = _make_activity(agent_name="Alice")
    assert await _format_activity_push(activity) == "[Alice] hello world"


@pytest.mark.asyncio
async def test_format_activity_push_agent_gone():
    """Falls back to the agent id when the agent no longer exists."""
    activity = _make_activity()
    assert await _format_activity_push(activity) == "[agent-1] hello world"


@pytest.mark.asyncio
async def test_format_activity_push_with_link():
    activity = _make_activity(agent_name="Alice", link="https://example.com/x")
    assert await _format_activity_push(activity) == (
        "[Alice] hello world\nhttps://example.com/x"
    )


@pytest.mark.asyncio
async def test_format_activity_push_with_post_id(monkeypatch):
    from intentkit.config.config import config
    from intentkit.models.share_link import ShareLink, ShareLinkTargetType

    monkeypatch.setattr(config, "app_base_url", "https://app.example.com")

    async def fake_create_share_link(target_type, target_id, agent_id, **kwargs):
        assert target_type == ShareLinkTargetType.POST
        assert target_id == "post-42"
        assert agent_id == "agent-1"
        # Agent-initiated pushes must not carry a user or team
        assert kwargs.get("user_id") is None
        assert kwargs.get("team_id") is None
        return ShareLink(
            id="share-xid",
            target_type=target_type,
            target_id=target_id,
            agent_id=agent_id,
            expires_at=datetime.now(),
            created_at=datetime.now(),
        )

    monkeypatch.setattr(
        agent_activity_module, "create_share_link", fake_create_share_link
    )

    activity = _make_activity(
        agent_name="Alice", text="Published a new post: hi", post_id="post-42"
    )
    assert await _format_activity_push(activity) == (
        "[Alice] Published a new post: hi\nhttps://app.example.com/share/share-xid"
    )


@pytest.mark.asyncio
async def test_format_activity_push_post_fallback_on_error(monkeypatch):
    from intentkit.config.config import config

    monkeypatch.setattr(config, "app_base_url", "https://app.example.com")

    async def broken_create_share_link(*_args, **_kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr(
        agent_activity_module, "create_share_link", broken_create_share_link
    )

    activity = _make_activity(
        agent_name="Alice", text="Published a new post: hi", post_id="post-42"
    )
    assert await _format_activity_push(activity) == (
        "[Alice] Published a new post: hi\nhttps://app.example.com/post/post-42"
    )
