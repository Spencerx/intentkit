"""Tests for the Redis-backed agent display info cache."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import intentkit.core.agent.info as info_module
from intentkit.core.agent.info import (
    AgentInfo,
    attach_agent_info,
    get_agent_info,
    get_agent_infos,
    invalidate_agent_info,
)


class FakeRedis:
    """Minimal async Redis stand-in for the mget/set/delete calls used here."""

    def __init__(self):
        self.store: dict[str, str] = {}
        self.ttls: dict[str, int | None] = {}

    async def mget(self, keys):
        return [self.store.get(k) for k in keys]

    async def set(self, key, value, ex=None):
        self.store[key] = value
        self.ttls[key] = ex

    async def delete(self, key):
        _ = self.store.pop(key, None)
        _ = self.ttls.pop(key, None)


@pytest.fixture
def fake_redis(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setattr(info_module, "get_redis", lambda: redis)
    return redis


def _agent(agent_id: str, name: str = "Name", picture: str | None = None):
    return SimpleNamespace(id=agent_id, name=name, picture=picture, slug=None)


@pytest.mark.asyncio
async def test_batch_fetch_and_cache(monkeypatch, fake_redis):
    mock_get_agent = AsyncMock(side_effect=lambda aid: _agent(aid, name=f"N-{aid}"))
    monkeypatch.setattr(info_module, "get_agent", mock_get_agent)

    infos = await get_agent_infos(["a1", "a2", "a1"])

    assert set(infos) == {"a1", "a2"}
    assert infos["a1"].name == "N-a1"
    # Duplicate ids are fetched once
    assert mock_get_agent.await_count == 2
    # Entries are cached in Redis with the one-day TTL
    assert fake_redis.ttls["intentkit:agent_info:a1"] == 24 * 60 * 60

    # Second call is served entirely from the cache
    infos = await get_agent_infos(["a1", "a2"])
    assert set(infos) == {"a1", "a2"}
    assert mock_get_agent.await_count == 2


@pytest.mark.asyncio
async def test_missing_agent_negative_cached(monkeypatch, fake_redis):
    mock_get_agent = AsyncMock(return_value=None)
    monkeypatch.setattr(info_module, "get_agent", mock_get_agent)

    assert await get_agent_info("gone") is None
    assert await get_agent_info("gone") is None
    # The miss is cached as JSON null: only one lookup
    assert mock_get_agent.await_count == 1
    assert fake_redis.store["intentkit:agent_info:gone"] == "null"


@pytest.mark.asyncio
async def test_invalidate(monkeypatch, fake_redis):
    mock_get_agent = AsyncMock(side_effect=lambda aid: _agent(aid))
    monkeypatch.setattr(info_module, "get_agent", mock_get_agent)

    _ = await get_agent_info("a1")
    await invalidate_agent_info("a1")
    assert "intentkit:agent_info:a1" not in fake_redis.store

    _ = await get_agent_info("a1")
    assert mock_get_agent.await_count == 2


@pytest.mark.asyncio
async def test_invalidate_survives_redis_failure(monkeypatch):
    """A broken cache must not fail the agent update calling invalidate."""

    def broken_redis():
        raise RuntimeError("redis down")

    monkeypatch.setattr(info_module, "get_redis", broken_redis)

    await invalidate_agent_info("a1")


@pytest.mark.asyncio
async def test_attach_agent_info(monkeypatch, fake_redis):
    mock_get_agent = AsyncMock(
        side_effect=lambda aid: (
            _agent(aid, name=f"N-{aid}", picture=f"{aid}.png")
            if aid != "gone"
            else None
        )
    )
    monkeypatch.setattr(info_module, "get_agent", mock_get_agent)

    items = [
        SimpleNamespace(agent_id="a1", agent_name=None, agent_picture=None),
        # Stale snapshot from an older cached payload
        SimpleNamespace(agent_id="gone", agent_name="Stale", agent_picture="s.png"),
    ]
    await attach_agent_info(items)

    assert items[0].agent_name == "N-a1"
    assert items[0].agent_picture == "a1.png"
    # Unknown agents get their stale display info cleared
    assert items[1].agent_name is None
    assert items[1].agent_picture is None


@pytest.mark.asyncio
async def test_attach_agent_info_empty_list():
    # Must not touch Redis or the resolver at all
    await attach_agent_info([])


@pytest.mark.asyncio
async def test_agent_info_includes_slug(monkeypatch, fake_redis):
    agent = SimpleNamespace(id="a1", name="Alice", picture="p.png", slug="alice")
    monkeypatch.setattr(info_module, "get_agent", AsyncMock(return_value=agent))

    info = await get_agent_info("a1")
    assert info == AgentInfo(id="a1", name="Alice", picture="p.png", slug="alice")

    # Round-trips through the Redis payload on the next read
    info = await get_agent_info("a1")
    assert info == AgentInfo(id="a1", name="Alice", picture="p.png", slug="alice")
