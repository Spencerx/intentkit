#!/usr/bin/env python3
"""
Migration script to add 'timezone' and 'language' columns to the users table.

Run once after deploying the model changes. Safe to re-run (uses IF NOT EXISTS).
"""

import asyncio
import logging

from sqlalchemy import text

from intentkit.config.config import config
from intentkit.config.db import get_session, init_db

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def migrate():
    await init_db(**config.db)

    async with get_session() as db:
        await db.execute(
            text("ALTER TABLE users ADD COLUMN IF NOT EXISTS timezone VARCHAR NULL")
        )
        await db.execute(
            text("ALTER TABLE users ADD COLUMN IF NOT EXISTS language VARCHAR NULL")
        )
        await db.commit()
        logger.info(
            "Successfully added 'timezone' and 'language' columns to users table."
        )


if __name__ == "__main__":
    asyncio.run(migrate())
