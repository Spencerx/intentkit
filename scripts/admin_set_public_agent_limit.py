#!/usr/bin/env python3
"""Admin tool to set a team's public_agent_limit.

Usage:
    python scripts/admin_set_public_agent_limit.py <team_id> <limit>

Example:
    python scripts/admin_set_public_agent_limit.py acme 5

The command prints the previous value before updating so the operator can
verify the change.
"""

import argparse
import asyncio
import logging
import sys

from sqlalchemy import select, update

from intentkit.config.config import config
from intentkit.config.db import get_session, init_db
from intentkit.models.team import TeamTable

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def set_public_agent_limit(team_id: str, limit: int) -> None:
    await init_db(**config.db)
    async with get_session() as db:
        previous = await db.scalar(
            select(TeamTable.public_agent_limit).where(TeamTable.id == team_id)
        )
        if previous is None:
            logger.error("Team %s not found", team_id)
            sys.exit(1)

        if previous == limit:
            logger.info(
                "Team %s already has public_agent_limit=%d, nothing to do",
                team_id,
                limit,
            )
            return

        await db.execute(
            update(TeamTable)
            .where(TeamTable.id == team_id)
            .values(public_agent_limit=limit)
        )
        await db.commit()
        logger.info(
            "Team %s public_agent_limit updated: %d -> %d", team_id, previous, limit
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("team_id", help="Team identifier")
    parser.add_argument(
        "limit", type=int, help="New maximum number of public agents (>= 0)"
    )
    args = parser.parse_args()

    if args.limit < 0:
        parser.error("limit must be a non-negative integer")

    asyncio.run(set_public_agent_limit(args.team_id, args.limit))


if __name__ == "__main__":
    main()
