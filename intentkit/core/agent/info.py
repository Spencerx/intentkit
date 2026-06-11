"""Redis-backed cache of agent display info for read-time enrichment.

Content entities (posts, activities, autonomous tasks, ...) store only the
agent id; name/picture/slug are resolved here when building API responses.
Entries live in Redis for a day and are deleted when an agent is updated, so
every process sees renames immediately.
"""

import asyncio
import json
import logging
from collections.abc import Iterable, Sequence
from typing import Annotated, Protocol

from pydantic import BaseModel
from pydantic import Field as PydanticField

from intentkit.config.redis import get_redis
from intentkit.core.agent.queries import get_agent

logger = logging.getLogger(__name__)


class AgentInfo(BaseModel):
    """Basic display info of an agent."""

    id: Annotated[str, PydanticField(description="ID of the agent")]
    name: Annotated[
        str | None, PydanticField(default=None, description="Display name")
    ] = None
    picture: Annotated[
        str | None, PydanticField(default=None, description="Avatar URL")
    ] = None
    slug: Annotated[str | None, PydanticField(default=None, description="URL slug")] = (
        None
    )


_AGENT_INFO_TTL = 24 * 60 * 60
# Cold-cache fetches each open a DB session; cap them so one large list
# request cannot drain the connection pool.
_FETCH_CONCURRENCY = 10


def _cache_key(agent_id: str) -> str:
    return f"intentkit:agent_info:{agent_id}"


async def invalidate_agent_info(agent_id: str) -> None:
    """Drop one agent from the cache so all processes resolve fresh info."""
    try:
        _ = await get_redis().delete(_cache_key(agent_id))
    except Exception as e:
        # Best effort: an unavailable cache must not fail the agent update.
        logger.warning("Failed to invalidate agent info for %s: %s", agent_id, e)


async def _fetch(agent_id: str) -> AgentInfo | None:
    # get_agent applies template rendering, which can supply name/picture.
    agent = await get_agent(agent_id)
    if agent is None:
        return None
    return AgentInfo(
        id=agent.id, name=agent.name, picture=agent.picture, slug=agent.slug
    )


async def get_agent_infos(agent_ids: Iterable[str]) -> dict[str, AgentInfo]:
    """Resolve display info for many agents; unknown agents are omitted."""
    wanted = list(dict.fromkeys(agent_ids))
    if not wanted:
        return {}

    redis = get_redis()
    result: dict[str, AgentInfo] = {}
    missing: list[str] = []
    cached = await redis.mget([_cache_key(agent_id) for agent_id in wanted])
    for agent_id, raw in zip(wanted, cached):
        if raw is None:
            missing.append(agent_id)
            continue
        data = json.loads(raw)
        # JSON null marks a cached miss, so deleted agents don't trigger a
        # query per read.
        if data is not None:
            result[agent_id] = AgentInfo.model_validate(data)

    if missing:
        semaphore = asyncio.Semaphore(_FETCH_CONCURRENCY)

        async def fetch_limited(agent_id: str) -> AgentInfo | None:
            async with semaphore:
                return await _fetch(agent_id)

        fetched = await asyncio.gather(*(fetch_limited(a) for a in missing))
        writes = []
        for agent_id, info in zip(missing, fetched):
            payload = info.model_dump_json() if info is not None else "null"
            writes.append(redis.set(_cache_key(agent_id), payload, ex=_AGENT_INFO_TTL))
            if info is not None:
                result[agent_id] = info
        _ = await asyncio.gather(*writes)

    return result


async def get_agent_info(agent_id: str) -> AgentInfo | None:
    """Resolve display info for one agent, or None if it doesn't exist."""
    infos = await get_agent_infos([agent_id])
    return infos.get(agent_id)


class _HasAgentInfo(Protocol):
    agent_id: str
    agent_name: str | None
    agent_picture: str | None


async def attach_agent_info(items: Sequence[_HasAgentInfo]) -> None:
    """Fill agent_name/agent_picture on items that reference an agent_id.

    Fields are overwritten unconditionally, so stale snapshots carried by
    older cached payloads are cleared when the agent no longer exists.
    """
    if not items:
        return
    infos = await get_agent_infos(item.agent_id for item in items)
    for item in items:
        info = infos.get(item.agent_id)
        item.agent_name = info.name if info else None
        item.agent_picture = info.picture if info else None
