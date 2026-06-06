"""Round-trip test for scripts/migrate_skill_to_tool.sql (+ rollback).

Seeds an OLD-shape (skill) schema in a throwaway database, applies the migration
twice (idempotency), and asserts every table/column rename and persisted enum
value flip, with no row loss. Then verifies the rollback restores the old shape.
"""

import json
from pathlib import Path

import asyncpg
import pytest
import pytest_asyncio

REPO = Path(__file__).resolve().parents[2]
MIGRATION = (REPO / "scripts" / "migrate_skill_to_tool.sql").read_text()
ROLLBACK = (REPO / "scripts" / "migrate_skill_to_tool_rollback.sql").read_text()

OLD_SCHEMA = """
CREATE TABLE agents (id varchar PRIMARY KEY, skills jsonb);
CREATE TABLE templates (id varchar PRIMARY KEY, skills jsonb);
CREATE TABLE agent_skill_data (agent_id varchar, skill varchar, key varchar, data jsonb, PRIMARY KEY (agent_id, skill, key));
CREATE TABLE chat_skill_data (chat_id varchar, skill varchar, key varchar, PRIMARY KEY (chat_id, skill, key));
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
INSERT INTO templates (id, skills) VALUES ('tpl1', '{"twitter": {"enabled": true}}');
INSERT INTO agent_skill_data (agent_id, skill, key, data) VALUES ('a1', 'twitter', 'k', '{}');
INSERT INTO chat_skill_data (chat_id, skill, key) VALUES ('c1', 'twitter', 'k');
INSERT INTO chat_messages (id, author_type, thread_type, skill_calls) VALUES ('m1', 'skill', 'skill', '[]');
INSERT INTO chat_messages (id, author_type, thread_type, skill_calls) VALUES ('m2', 'agent', NULL, '[]');
INSERT INTO credit_events (id, event_type, skill_call_id, skill_name, base_skill_amount) VALUES ('e1', 'skill_call', 'x', 'twitter_post', 1);
INSERT INTO credit_prices (id, price_entity) VALUES ('p1', 'skill_call');
INSERT INTO credit_transactions (id, tx_type) VALUES ('t1', 'receive_base_skill');
INSERT INTO credit_accounts (id, owner_id) VALUES ('ac1', 'platform_skill');
INSERT INTO x402_orders (id, skill_name) VALUES ('o1', 'x402_pay');
INSERT INTO app_settings (key, value) VALUES ('errors', '{"skill_interrupted": "custom interrupt msg", "other": "x"}');
"""


@pytest_asyncio.fixture
async def mig_conn(postgresql_server):
    base_url = postgresql_server.url()
    admin = await asyncpg.connect(base_url)
    await admin.execute("DROP DATABASE IF EXISTS migtest")
    await admin.execute("CREATE DATABASE migtest")
    await admin.close()
    conn = await asyncpg.connect(base_url.rsplit("/", 1)[0] + "/migtest")
    try:
        yield conn
    finally:
        await conn.close()
        admin = await asyncpg.connect(base_url)
        await admin.execute("DROP DATABASE IF EXISTS migtest")
        await admin.close()


async def _tables(conn):
    rows = await conn.fetch(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
    )
    return {r["table_name"] for r in rows}


async def _cols(conn, table):
    rows = await conn.fetch(
        "SELECT column_name FROM information_schema.columns WHERE table_name=$1", table
    )
    return {r["column_name"] for r in rows}


@pytest.mark.asyncio
async def test_migrate_skill_to_tool_round_trip(mig_conn):
    conn = mig_conn
    await conn.execute(OLD_SCHEMA)
    await conn.execute(SEED)

    # apply twice -> must be idempotent
    await conn.execute(MIGRATION)
    await conn.execute(MIGRATION)

    tables = await _tables(conn)
    assert "agent_tool_data" in tables and "agent_skill_data" not in tables
    assert "chat_tool_data" in tables and "chat_skill_data" not in tables

    assert "tool" in await _cols(conn, "agent_tool_data")
    assert "skill" not in await _cols(conn, "agent_tool_data")
    assert "tools" in await _cols(conn, "agents")
    assert "skills" not in await _cols(conn, "agents")
    assert "tools" in await _cols(conn, "templates")
    assert "tool_calls" in await _cols(conn, "chat_messages")
    assert {"tool_call_id", "tool_name", "base_tool_amount"} <= await _cols(
        conn, "credit_events"
    )
    assert "tool_name" in await _cols(conn, "x402_orders")

    # value flips
    assert (
        await conn.fetchval("SELECT author_type FROM chat_messages WHERE id='m1'")
        == "tool"
    )
    assert (
        await conn.fetchval("SELECT thread_type FROM chat_messages WHERE id='m1'")
        == "tool"
    )
    assert (
        await conn.fetchval("SELECT author_type FROM chat_messages WHERE id='m2'")
        == "agent"
    )
    assert (
        await conn.fetchval("SELECT event_type FROM credit_events WHERE id='e1'")
        == "tool_call"
    )
    assert (
        await conn.fetchval("SELECT price_entity FROM credit_prices WHERE id='p1'")
        == "tool_call"
    )
    assert (
        await conn.fetchval("SELECT tx_type FROM credit_transactions WHERE id='t1'")
        == "receive_base_tool"
    )
    assert (
        await conn.fetchval("SELECT owner_id FROM credit_accounts WHERE id='ac1'")
        == "platform_tool"
    )
    errs_raw = await conn.fetchval("SELECT value FROM app_settings WHERE key='errors'")
    errs = json.loads(errs_raw) if isinstance(errs_raw, str) else errs_raw
    assert "tool_interrupted" in errs and "skill_interrupted" not in errs
    assert errs["tool_interrupted"] == "custom interrupt msg"
    assert errs["other"] == "x"

    # no row loss + data preserved on the renamed PK column
    assert await conn.fetchval("SELECT count(*) FROM chat_messages") == 2
    assert await conn.fetchval("SELECT count(*) FROM agent_tool_data") == 1
    assert (
        await conn.fetchval("SELECT tool FROM agent_tool_data WHERE agent_id='a1'")
        == "twitter"
    )


@pytest.mark.asyncio
async def test_migrate_rollback_restores_old_shape(mig_conn):
    conn = mig_conn
    await conn.execute(OLD_SCHEMA)
    await conn.execute(SEED)
    await conn.execute(MIGRATION)
    await conn.execute(ROLLBACK)

    tables = await _tables(conn)
    assert "agent_skill_data" in tables and "agent_tool_data" not in tables
    assert "skills" in await _cols(conn, "agents")
    assert (
        await conn.fetchval("SELECT author_type FROM chat_messages WHERE id='m1'")
        == "skill"
    )
    assert (
        await conn.fetchval("SELECT event_type FROM credit_events WHERE id='e1'")
        == "skill_call"
    )
