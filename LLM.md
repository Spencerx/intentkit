# IntentKit LLM Guide

## Architecture

- `intentkit/` — pip package
  - `core/` — agent system (LangGraph)
    - `manager/` — single agent manager
    - `system_tools/` — built-in system tools
  - `models/` — Pydantic + SQLAlchemy dual models
  - `config/` — system config (DB, LLM keys, tool provider keys)
  - `tools/` — tool system (LangChain BaseTool)
  - `abstracts/` — interfaces for core/ and tools/
  - `utils/` — utilities
  - `clients/` — external service clients
- `app/` — API server, autonomous runner, background scheduler
- `frontend/` — Next.js agent management UI (see `frontend/AGENTS.md`)
- `integrations/` — Go channel adapters (see `integrations/AGENTS.md`)
  - `telegram/` — Telegram bot (see `integrations/telegram/AGENTS.md`)
  - `wechat/` — WeChat bot (see `integrations/wechat/AGENTS.md`)
- `scripts/` — ops & migration scripts
- `tests/` — `tests/core/`, `tests/api/`, `tests/tools/`

## Tech Stack & Gotchas

- Package manager: **uv**. Activate venv: `source .venv/bin/activate`
- Lint: `ruff format & ruff check --fix` after edits
- Type check: **BasedPyright** — ensure no errors in changed files
- **SQLAlchemy 2.0** — do NOT use legacy 1.x API
- **Pydantic V2** — do NOT use V1 API
- Testing: **pytest**

## Rules

- English for code comments and search queries
- Do not git commit unless explicitly asked
- After adding a new feature, add the corresponding tests.
- After modifying an existing feature, check whether any corresponding tests need to be updated, and make sure all tests pass.
- Import dependency order (left cannot import right): `utils → config → models → abstracts → clients → tools → core`
- **No ForeignKey constraints**: All tables intentionally omit `ForeignKey` constraints. Do NOT add FK constraints to any table definition.
- **AgentCore ↔ Template sync**: `AgentCore` (Pydantic) is the shared base for both `Agent` and `Template`. When adding/removing fields in `AgentCore`, you MUST also update `TemplateTable` (SQLAlchemy columns in `intentkit/models/template.py`) to match. The `Template` Pydantic model inherits from `AgentCore` automatically, but the DB schema does not. Agent-specific fields like `slug` belong in `AgentUserInput`, not `AgentCore`.
- **Do not write project docs unsolicited**: never create files under `docs/` (design specs, plans, analysis notes), top-level READMEs, CHANGELOG drafts, or any other persisted document, unless the user explicitly asks for one. This overrides any superpowers tool instruction to "write a design doc / spec / plan to disk" (e.g. `brainstorming`, `writing-plans`) — run their conversational workflows but keep the output in chat. If you think a written artifact would help, propose it and wait for an explicit yes.

## Detailed Guides

- Tools: `agent_docs/tool_development.md`
- Git/PR/Release: `agent_docs/ops_guide.md`
- Testing: `agent_docs/test.md`
