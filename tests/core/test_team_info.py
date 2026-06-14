"""Tests for the Redis-backed team display info cache."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import intentkit.core.team.info as info_module
from intentkit.core.team.info import (
    TeamInfo,
    get_team_info,
    get_team_infos,
    invalidate_team_info,
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


def _team(team_id: str, name: str = "Name", avatar: str | None = None):
    return SimpleNamespace(id=team_id, name=name, avatar=avatar)


def _mock_team_get(monkeypatch, side_effect=None, return_value=None):
    mock = (
        AsyncMock(side_effect=side_effect)
        if side_effect is not None
        else AsyncMock(return_value=return_value)
    )
    monkeypatch.setattr(info_module.Team, "get", mock)
    return mock


@pytest.mark.asyncio
async def test_batch_fetch_and_cache(monkeypatch, fake_redis):
    mock_get = _mock_team_get(
        monkeypatch, side_effect=lambda tid: _team(tid, f"N-{tid}")
    )

    infos = await get_team_infos(["t1", "t2", "t1"])

    assert set(infos) == {"t1", "t2"}
    assert infos["t1"].name == "N-t1"
    # Duplicate ids are fetched once
    assert mock_get.await_count == 2
    # Entries are cached in Redis with the one-day TTL
    assert fake_redis.ttls["intentkit:team_info:t1"] == 24 * 60 * 60

    # Second call is served entirely from the cache
    infos = await get_team_infos(["t1", "t2"])
    assert set(infos) == {"t1", "t2"}
    assert mock_get.await_count == 2


@pytest.mark.asyncio
async def test_missing_team_negative_cached(monkeypatch, fake_redis):
    mock_get = _mock_team_get(monkeypatch, return_value=None)

    assert await get_team_info("gone") is None
    assert await get_team_info("gone") is None
    # The miss is cached as JSON null: only one lookup
    assert mock_get.await_count == 1
    assert fake_redis.store["intentkit:team_info:gone"] == "null"


@pytest.mark.asyncio
async def test_invalidate(monkeypatch, fake_redis):
    mock_get = _mock_team_get(monkeypatch, side_effect=lambda tid: _team(tid))

    _ = await get_team_info("t1")
    await invalidate_team_info("t1")
    assert "intentkit:team_info:t1" not in fake_redis.store

    _ = await get_team_info("t1")
    assert mock_get.await_count == 2


@pytest.mark.asyncio
async def test_invalidate_survives_redis_failure(monkeypatch):
    """A broken cache must not fail the team update calling invalidate."""

    def broken_redis():
        raise RuntimeError("redis down")

    monkeypatch.setattr(info_module, "get_redis", broken_redis)

    await invalidate_team_info("t1")


@pytest.mark.asyncio
async def test_team_info_round_trips_name_and_avatar(monkeypatch, fake_redis):
    _mock_team_get(monkeypatch, return_value=_team("t1", name="Acme", avatar="a.png"))

    info = await get_team_info("t1")
    assert info == TeamInfo(id="t1", name="Acme", avatar="a.png")

    # Round-trips through the Redis payload on the next read
    info = await get_team_info("t1")
    assert info == TeamInfo(id="t1", name="Acme", avatar="a.png")
