"""Test the runtime auto-migration path (intentkit/config/db_mig.py).

This is the path that actually runs on app startup in the cloud container: the
skill->tool/toolset rename executes BEFORE create_all, so the additive migration
cannot strand data in an old `skills` column. Proves rename-then-create_all keeps
the data under the new column, and that the rename is idempotent on a fresh DB.
"""

import json

import asyncpg
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine

from intentkit.config.base import Base
from intentkit.config.db_mig import _migrate_skill_to_tool

OLD = """
CREATE TABLE agents (id varchar PRIMARY KEY, skills jsonb);
CREATE TABLE templates (id varchar PRIMARY KEY, skills jsonb);
CREATE TABLE agent_skill_data (agent_id varchar, skill varchar, key varchar, data jsonb, PRIMARY KEY (agent_id, skill, key));
CREATE TABLE chat_messages (id varchar PRIMARY KEY, author_type varchar, thread_type varchar, skill_calls jsonb);
CREATE TABLE credit_events (id varchar PRIMARY KEY, event_type varchar, skill_call_id varchar, skill_name varchar, base_skill_amount numeric);
CREATE TABLE credit_prices (id varchar PRIMARY KEY, price_entity varchar);
CREATE TABLE credit_transactions (id varchar PRIMARY KEY, tx_type varchar);
CREATE TABLE credit_accounts (id varchar PRIMARY KEY, owner_id varchar);
CREATE TABLE x402_orders (id varchar PRIMARY KEY, skill_name varchar);
CREATE TABLE app_settings (key varchar PRIMARY KEY, value jsonb);
"""

SEED = """
INSERT INTO agents (id, skills) VALUES ('a1', '{"ui": {"enabled": true}}');
INSERT INTO agent_skill_data (agent_id, skill, key, data) VALUES ('a1', 'twitter', 'k', '{}');
INSERT INTO chat_messages (id, author_type, thread_type, skill_calls) VALUES ('m1', 'skill', 'skill', '[]');
INSERT INTO credit_events (id, event_type, skill_name) VALUES ('e1', 'skill_call', 'twitter_post');
INSERT INTO credit_accounts (id, owner_id) VALUES ('ac1', 'platform_skill');
INSERT INTO app_settings (key, value) VALUES ('errors', '{"skill_interrupted": "msg"}');
"""


def _statements(block):
    return [s.strip() for s in block.split(";") if s.strip()]


@pytest_asyncio.fixture
async def mig_engine(postgresql_server):
    base_url = postgresql_server.url()
    admin = await asyncpg.connect(base_url)
    await admin.execute("DROP DATABASE IF EXISTS migruntime")
    await admin.execute("CREATE DATABASE migruntime")
    await admin.close()
    sa_url = (
        base_url.rsplit("/", 1)[0].replace("postgresql://", "postgresql+asyncpg://", 1)
        + "/migruntime"
    )
    engine = create_async_engine(sa_url)
    try:
        yield engine
    finally:
        await engine.dispose()
        admin = await asyncpg.connect(base_url)
        await admin.execute("DROP DATABASE IF EXISTS migruntime")
        await admin.close()


async def _scalar(conn, sql):
    return (await conn.exec_driver_sql(sql)).scalar()


@pytest.mark.asyncio
async def test_rename_runs_before_create_all_without_stranding_data(mig_engine):
    async with mig_engine.begin() as conn:
        for stmt in _statements(OLD) + _statements(SEED):
            await conn.exec_driver_sql(stmt)

    # the exact sequence safe_migrate runs at startup
    async with mig_engine.begin() as conn:
        await _migrate_skill_to_tool(conn)
        await conn.run_sync(Base.metadata.create_all)

    async with mig_engine.connect() as conn:
        tools = await _scalar(conn, "SELECT tools FROM agents WHERE id='a1'")
        tools = json.loads(tools) if isinstance(tools, str) else tools
        assert tools == {"ui": {"enabled": True}}  # data preserved under the new column
        assert (
            await _scalar(conn, "SELECT tool FROM agent_tool_data WHERE agent_id='a1'")
            == "twitter"
        )
        assert (
            await _scalar(conn, "SELECT author_type FROM chat_messages WHERE id='m1'")
            == "tool"
        )
        assert (
            await _scalar(conn, "SELECT event_type FROM credit_events WHERE id='e1'")
            == "tool_call"
        )
        assert (
            await _scalar(conn, "SELECT owner_id FROM credit_accounts WHERE id='ac1'")
            == "platform_tool"
        )
        errs = await _scalar(conn, "SELECT value FROM app_settings WHERE key='errors'")
        errs = json.loads(errs) if isinstance(errs, str) else errs
        assert errs == {"tool_interrupted": "msg"}
        cols = [
            r[0]
            for r in (
                await conn.exec_driver_sql(
                    "SELECT column_name FROM information_schema.columns WHERE table_name='agents'"
                )
            ).fetchall()
        ]
        assert "tools" in cols and "skills" not in cols  # no stranded old column


@pytest.mark.asyncio
async def test_rename_is_noop_on_fresh_db(mig_engine):
    # Fresh DB (no legacy skill schema): the rename must be a harmless no-op, twice.
    async with mig_engine.begin() as conn:
        await _migrate_skill_to_tool(conn)
        await _migrate_skill_to_tool(conn)


@pytest.mark.asyncio
async def test_rename_tolerates_missing_columns(mig_engine):
    # An old DB predating additive columns (e.g. chat_messages without thread_type,
    # which safe_migrate's add-column step only fills in AFTER this rename runs): the
    # per-column guard must skip the flip rather than crash on a missing column.
    async with mig_engine.begin() as conn:
        await conn.exec_driver_sql(
            "CREATE TABLE chat_messages (id varchar PRIMARY KEY, author_type varchar)"
        )
        await conn.exec_driver_sql(
            "INSERT INTO chat_messages (id, author_type) VALUES ('m1', 'skill')"
        )
        await _migrate_skill_to_tool(conn)  # must not raise on the absent thread_type
    async with mig_engine.connect() as conn:
        assert (
            await _scalar(conn, "SELECT author_type FROM chat_messages WHERE id='m1'")
            == "tool"
        )
