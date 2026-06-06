-- Migration: rename the legacy "skill" concept to "tool" / "toolset".
--
-- This project has NO Alembic. The rename now runs AUTOMATICALLY at app startup
-- (intentkit/config/db_mig.py::_migrate_skill_to_tool, executed by safe_migrate
-- BEFORE create_all), so a normal deploy is self-migrating and you usually do NOT
-- need to run this file by hand.
--
-- This script is the manual psql equivalent (mirrors the runtime SQL) for ops /
-- emergency use. Idempotent and guarded by information_schema, so re-running and
-- running on a fresh DB are both safe. Run inside a single transaction:
--   psql -1 -f scripts/migrate_skill_to_tool.sql

DO $$
BEGIN
    -- ===== table renames (per-agent / per-chat tool data stores) =====
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'agent_skill_data')
       AND NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'agent_tool_data') THEN
        ALTER TABLE agent_skill_data RENAME TO agent_tool_data;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'chat_skill_data')
       AND NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'chat_tool_data') THEN
        ALTER TABLE chat_skill_data RENAME TO chat_tool_data;
    END IF;

    -- ===== column renames =====
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

    -- ===== persisted enum value flips (guarded per-column: missing column = no skill rows) =====
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
    -- system-message overrides live as nested JSON keys inside the single key='errors' row
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='app_settings' AND column_name='value') THEN
        UPDATE app_settings
        SET value = (value - 'skill_interrupted') || jsonb_build_object('tool_interrupted', value -> 'skill_interrupted')
        WHERE key = 'errors' AND jsonb_exists(value, 'skill_interrupted');
    END IF;
END $$;
