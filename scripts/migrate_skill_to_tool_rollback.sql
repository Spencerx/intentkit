-- Rollback for migrate_skill_to_tool.sql: revert tool/toolset back to skill.
-- Idempotent + guarded. Run inside a single transaction:
--   psql -1 -f scripts/migrate_skill_to_tool_rollback.sql
-- NOTE: the runtime auto-migration (db_mig.py) re-applies skill->tool on the next
-- app start, so disable DB_AUTO_MIGRATE (or revert the code) before relying on this.

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'agent_tool_data')
       AND NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'agent_skill_data') THEN
        ALTER TABLE agent_tool_data RENAME TO agent_skill_data;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'chat_tool_data')
       AND NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'chat_skill_data') THEN
        ALTER TABLE chat_tool_data RENAME TO chat_skill_data;
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='agent_skill_data' AND column_name='tool')
       AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='agent_skill_data' AND column_name='skill') THEN
        ALTER TABLE agent_skill_data RENAME COLUMN tool TO skill;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='chat_skill_data' AND column_name='tool')
       AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='chat_skill_data' AND column_name='skill') THEN
        ALTER TABLE chat_skill_data RENAME COLUMN tool TO skill;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='agents' AND column_name='tools')
       AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='agents' AND column_name='skills') THEN
        ALTER TABLE agents RENAME COLUMN tools TO skills;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='templates' AND column_name='tools')
       AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='templates' AND column_name='skills') THEN
        ALTER TABLE templates RENAME COLUMN tools TO skills;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='chat_messages' AND column_name='tool_calls')
       AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='chat_messages' AND column_name='skill_calls') THEN
        ALTER TABLE chat_messages RENAME COLUMN tool_calls TO skill_calls;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='credit_events' AND column_name='tool_call_id')
       AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='credit_events' AND column_name='skill_call_id') THEN
        ALTER TABLE credit_events RENAME COLUMN tool_call_id TO skill_call_id;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='credit_events' AND column_name='tool_name')
       AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='credit_events' AND column_name='skill_name') THEN
        ALTER TABLE credit_events RENAME COLUMN tool_name TO skill_name;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='credit_events' AND column_name='base_tool_amount')
       AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='credit_events' AND column_name='base_skill_amount') THEN
        ALTER TABLE credit_events RENAME COLUMN base_tool_amount TO base_skill_amount;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='x402_orders' AND column_name='tool_name')
       AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='x402_orders' AND column_name='skill_name') THEN
        ALTER TABLE x402_orders RENAME COLUMN tool_name TO skill_name;
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='chat_messages' AND column_name='author_type') THEN
        UPDATE chat_messages SET author_type = 'skill' WHERE author_type = 'tool';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='chat_messages' AND column_name='thread_type') THEN
        UPDATE chat_messages SET thread_type = 'skill' WHERE thread_type = 'tool';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='credit_events' AND column_name='event_type') THEN
        UPDATE credit_events SET event_type = 'skill_call' WHERE event_type = 'tool_call';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='credit_prices' AND column_name='price_entity') THEN
        UPDATE credit_prices SET price_entity = 'skill_call' WHERE price_entity = 'tool_call';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='credit_transactions' AND column_name='tx_type') THEN
        UPDATE credit_transactions SET tx_type = 'receive_base_skill' WHERE tx_type = 'receive_base_tool';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='credit_accounts' AND column_name='owner_id') THEN
        UPDATE credit_accounts SET owner_id = 'platform_skill' WHERE owner_id = 'platform_tool';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='app_settings' AND column_name='value') THEN
        UPDATE app_settings
        SET value = (value - 'tool_interrupted') || jsonb_build_object('skill_interrupted', value -> 'tool_interrupted')
        WHERE key = 'errors' AND jsonb_exists(value, 'tool_interrupted');
    END IF;
END $$;
