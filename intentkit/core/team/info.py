"""Redis-backed cache of team display info for read-time enrichment.

Mirrors ``intentkit.core.agent.info``: content, activity, and trace records
carry only a team id; name/avatar are resolved here when building responses or
enriching observability traces. Entries live in Redis for a day and are dropped
when a team is updated (via ``_invalidate_team_cache``), so every process sees
renames immediately.

This is a lightweight display-info layer, distinct from the full-team object
cache in ``membership.get_team`` (shorter TTL, whole ``Team`` payload).
"""

import asyncio
import json
import logging
from collections.abc import Iterable
from typing import Annotated

from pydantic import BaseModel
from pydantic import Field as PydanticField

from intentkit.config.redis import get_redis
from intentkit.models.team import Team

logger = logging.getLogger(__name__)


class TeamInfo(BaseModel):
    """Basic display info of a team."""

    id: Annotated[str, PydanticField(description="ID of the team")]
    name: Annotated[
        str | None, PydanticField(default=None, description="Display name")
    ] = None
    avatar: Annotated[
        str | None, PydanticField(default=None, description="Avatar URL")
    ] = None


_TEAM_INFO_TTL = 24 * 60 * 60
# Cold-cache fetches each open a DB session; cap them so one large list
# request cannot drain the connection pool.
_FETCH_CONCURRENCY = 10


def _cache_key(team_id: str) -> str:
    return f"intentkit:team_info:{team_id}"


async def invalidate_team_info(team_id: str) -> None:
    """Drop one team from the cache so all processes resolve fresh info."""
    try:
        _ = await get_redis().delete(_cache_key(team_id))
    except Exception as e:
        # Best effort: an unavailable cache must not fail the team update.
        logger.warning("Failed to invalidate team info for %s: %s", team_id, e)


async def _fetch(team_id: str) -> TeamInfo | None:
    team = await Team.get(team_id)
    if team is None:
        return None
    return TeamInfo(id=team.id, name=team.name, avatar=team.avatar)


async def get_team_infos(team_ids: Iterable[str]) -> dict[str, TeamInfo]:
    """Resolve display info for many teams; unknown teams are omitted."""
    wanted = list(dict.fromkeys(team_ids))
    if not wanted:
        return {}

    redis = get_redis()
    result: dict[str, TeamInfo] = {}
    missing: list[str] = []
    cached = await redis.mget([_cache_key(team_id) for team_id in wanted])
    for team_id, raw in zip(wanted, cached):
        if raw is None:
            missing.append(team_id)
            continue
        data = json.loads(raw)
        # JSON null marks a cached miss, so deleted teams don't trigger a
        # query per read.
        if data is not None:
            result[team_id] = TeamInfo.model_validate(data)

    if missing:
        semaphore = asyncio.Semaphore(_FETCH_CONCURRENCY)

        async def fetch_limited(team_id: str) -> TeamInfo | None:
            async with semaphore:
                return await _fetch(team_id)

        fetched = await asyncio.gather(*(fetch_limited(t) for t in missing))
        writes = []
        for team_id, info in zip(missing, fetched):
            payload = info.model_dump_json() if info is not None else "null"
            writes.append(redis.set(_cache_key(team_id), payload, ex=_TEAM_INFO_TTL))
            if info is not None:
                result[team_id] = info
        _ = await asyncio.gather(*writes)

    return result


async def get_team_info(team_id: str) -> TeamInfo | None:
    """Resolve display info for one team, or None if it doesn't exist."""
    infos = await get_team_infos([team_id])
    return infos.get(team_id)
