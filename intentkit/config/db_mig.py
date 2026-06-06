"""Database migration utilities."""

import logging
from collections.abc import Callable
from typing import Any

from sqlalchemy import Column, MetaData, inspect, text

from intentkit.config.base import Base

logger = logging.getLogger(__name__)


async def add_column_if_not_exists(
    conn, dialect, table_name: str, column: Column[Any]
) -> None:
    """Add a column to a table if it doesn't exist.

    Args:
        conn: SQLAlchemy conn
        table_name: Name of the table
        column: Column to add
    """

    # Use run_sync to perform inspection on the connection
    def _get_columns(connection):
        inspector = inspect(connection)
        return [c["name"] for c in inspector.get_columns(table_name)]

    columns = await conn.run_sync(_get_columns)

    if column.name not in columns:
        # Build column definition
        column_def = f"{column.name} {column.type.compile(dialect)}"

        # Add DEFAULT if specified
        if column.default is not None:
            if hasattr(column.default, "arg"):
                default_value = column.default.arg  # pyright: ignore[reportAttributeAccessIssue]
                if not isinstance(default_value, Callable):
                    if isinstance(default_value, bool):
                        default_value = str(default_value).lower()
                    elif isinstance(default_value, str):
                        default_value = f"'{default_value}'"
                    elif isinstance(default_value, list | dict):
                        default_value = "'{}'"
                    column_def += f" DEFAULT {default_value}"

        # Execute ALTER TABLE
        await conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_def}"))
        logger.info("Added column %s to table %s", column.name, table_name)


async def update_table_schema(conn, dialect, model_cls) -> None:
    """Update table schema by adding missing columns from the model.

    Args:
        conn: SQLAlchemy conn
        dialect: SQLAlchemy dialect
        model_cls: SQLAlchemy model class to check for new columns
    """
    if not hasattr(model_cls, "__table__"):
        return

    table_name = model_cls.__tablename__
    for name, column in model_cls.__table__.columns.items():
        if name != "id":  # Skip primary key
            await add_column_if_not_exists(conn, dialect, table_name, column)


# Legacy one-time, idempotent rename of the "skill" concept to "tool"/"toolset".
# Guarded by information_schema so it is a no-op once applied (safe on every startup).
# Mirrors scripts/migrate_skill_to_tool.sql (the manual psql equivalent).
_SKILL_TO_TOOL_DDL = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'agent_skill_data')
       AND NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'agent_tool_data') THEN
        ALTER TABLE agent_skill_data RENAME TO agent_tool_data;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'chat_skill_data')
       AND NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'chat_tool_data') THEN
        ALTER TABLE chat_skill_data RENAME TO chat_tool_data;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='agent_tool_data' AND column_name='skill')
       AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='agent_tool_data' AND column_name='tool') THEN
        ALTER TABLE agent_tool_data RENAME COLUMN skill TO tool;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='chat_tool_data' AND column_name='skill')
       AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='chat_tool_data' AND column_name='tool') THEN
        ALTER TABLE chat_tool_data RENAME COLUMN skill TO tool;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='agents' AND column_name='skills')
       AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='agents' AND column_name='tools') THEN
        ALTER TABLE agents RENAME COLUMN skills TO tools;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='templates' AND column_name='skills')
       AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='templates' AND column_name='tools') THEN
        ALTER TABLE templates RENAME COLUMN skills TO tools;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='chat_messages' AND column_name='skill_calls')
       AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='chat_messages' AND column_name='tool_calls') THEN
        ALTER TABLE chat_messages RENAME COLUMN skill_calls TO tool_calls;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='credit_events' AND column_name='skill_call_id')
       AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='credit_events' AND column_name='tool_call_id') THEN
        ALTER TABLE credit_events RENAME COLUMN skill_call_id TO tool_call_id;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='credit_events' AND column_name='skill_name')
       AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='credit_events' AND column_name='tool_name') THEN
        ALTER TABLE credit_events RENAME COLUMN skill_name TO tool_name;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='credit_events' AND column_name='base_skill_amount')
       AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='credit_events' AND column_name='base_tool_amount') THEN
        ALTER TABLE credit_events RENAME COLUMN base_skill_amount TO base_tool_amount;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='x402_orders' AND column_name='skill_name')
       AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='x402_orders' AND column_name='tool_name') THEN
        ALTER TABLE x402_orders RENAME COLUMN skill_name TO tool_name;
    END IF;

    -- persisted enum value flips (guarded per-column: a missing column has no skill rows)
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='chat_messages' AND column_name='author_type') THEN
        UPDATE chat_messages SET author_type = 'tool' WHERE author_type = 'skill';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='chat_messages' AND column_name='thread_type') THEN
        UPDATE chat_messages SET thread_type = 'tool' WHERE thread_type = 'skill';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='credit_events' AND column_name='event_type') THEN
        UPDATE credit_events SET event_type = 'tool_call' WHERE event_type = 'skill_call';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='credit_prices' AND column_name='price_entity') THEN
        UPDATE credit_prices SET price_entity = 'tool_call' WHERE price_entity = 'skill_call';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='credit_transactions' AND column_name='tx_type') THEN
        UPDATE credit_transactions SET tx_type = 'receive_base_tool' WHERE tx_type = 'receive_base_skill';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='credit_accounts' AND column_name='owner_id') THEN
        UPDATE credit_accounts SET owner_id = 'platform_tool' WHERE owner_id = 'platform_skill';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='app_settings' AND column_name='value') THEN
        UPDATE app_settings SET value = (value - 'skill_interrupted') || jsonb_build_object('tool_interrupted', value -> 'skill_interrupted') WHERE key = 'errors' AND jsonb_exists(value, 'skill_interrupted');
    END IF;
END $$;
"""


async def _migrate_skill_to_tool(conn) -> None:
    """Apply the idempotent skill -> tool/toolset rename + value flips (one guarded block).

    Runs raw DDL/DML via the driver (no bind params). Safe to call repeatedly and on a
    fresh DB -- every statement is guarded by information_schema.
    """
    await conn.exec_driver_sql(_SKILL_TO_TOOL_DDL)


async def safe_migrate(engine) -> None:
    """Safely migrate all SQLAlchemy models by adding new columns.

    Args:
        engine: SQLAlchemy engine
    """
    logger.info("Starting database schema migration")
    dialect = engine.dialect

    async with engine.begin() as conn:
        try:
            # Legacy skill -> tool/toolset rename. MUST run before create_all so the
            # additive auto-migration cannot create empty new-named columns/tables
            # alongside the old data. Idempotent / guarded -> no-op once applied.
            await _migrate_skill_to_tool(conn)

            # Create tables if they don't exist
            await conn.run_sync(Base.metadata.create_all)

            # Get existing table metadata
            metadata = MetaData()
            await conn.run_sync(metadata.reflect)

            # Update schema for all model classes
            for mapper in Base.registry.mappers:
                model_cls = mapper.class_
                if hasattr(model_cls, "__tablename__"):
                    table_name = model_cls.__tablename__
                    if table_name in metadata.tables:
                        # We need a sync wrapper for the async update_table_schema
                        async def update_table_wrapper():
                            await update_table_schema(conn, dialect, model_cls)

                        await update_table_wrapper()

            # Checkpoint tables are managed by AsyncPostgresSaver.setup()
            # in init_db, no need to migrate them here.
        except Exception as e:
            logger.error("Error updating database schema: %s", e)
            raise

    logger.info("Database schema updated successfully")
