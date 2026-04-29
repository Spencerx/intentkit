"""Agent Manager sub-agent: agent CRUD plus autonomous tasks scheduled on those agents."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

from langchain_core.tools import BaseTool

from intentkit.core.lead.skills.add_autonomous_task import (
    lead_add_autonomous_task_skill,
)
from intentkit.core.lead.skills.create_team_agent import create_team_agent_skill
from intentkit.core.lead.skills.delete_autonomous_task import (
    lead_delete_autonomous_task_skill,
)
from intentkit.core.lead.skills.edit_autonomous_task import (
    lead_edit_autonomous_task_skill,
)
from intentkit.core.lead.skills.get_team_agent import get_team_agent_skill
from intentkit.core.lead.skills.get_team_info import get_team_info_skill
from intentkit.core.lead.skills.list_autonomous_tasks import (
    lead_list_autonomous_tasks_skill,
)
from intentkit.core.lead.skills.list_skills import lead_list_available_skills_skill
from intentkit.core.lead.skills.list_team_agents import list_team_agents_skill
from intentkit.core.lead.skills.llm import lead_get_available_llms_skill
from intentkit.core.lead.skills.update_team_agent import update_team_agent_skill
from intentkit.models.agent import Agent
from intentkit.models.llm_picker import pick_default_model


def get_agent_manager_skills() -> Sequence[BaseTool]:
    """Return skills for the agent manager sub-agent."""
    return [
        get_team_info_skill,
        list_team_agents_skill,
        create_team_agent_skill,
        get_team_agent_skill,
        update_team_agent_skill,
        lead_get_available_llms_skill,
        lead_list_available_skills_skill,
        lead_list_autonomous_tasks_skill,
        lead_add_autonomous_task_skill,
        lead_edit_autonomous_task_skill,
        lead_delete_autonomous_task_skill,
    ]


def build_agent_manager(team_id: str) -> Agent:
    """Build an in-memory Agent Manager sub-agent."""
    now = datetime.now(timezone.utc)

    prompt = (
        "### Workflow\n\n"
        "- Call `lead_list_team_agents` first when asked about existing agents.\n"
        "- Call `lead_get_team_agent` before updating to see current config.\n\n"
        "### Agent Creation\n\n"
        "Guide user through:\n"
        "1. Name, slug, and purpose\n"
        "2. Model — `lead_get_available_llms` for options. "
        "High intelligence for complex reasoning, high speed for simple tasks.\n"
        "3. Skills — ALWAYS call `lead_list_available_skills` first to see all "
        "available categories and individual skills. Pick only the skills the "
        "agent needs based on its purpose. Keep under 20.\n"
        "4. Additional settings as needed\n\n"
        "### Skill Configuration (IMPORTANT)\n\n"
        "You MUST call `lead_list_available_skills` before configuring skills. "
        "Only use skill names from that list.\n\n"
        "Format:\n"
        "```json\n"
        "{\n"
        '  "category_name": {\n'
        '    "enabled": true,\n'
        '    "states": {\n'
        '      "skill_name_1": "public",\n'
        '      "skill_name_2": "public"\n'
        "    }\n"
        "  }\n"
        "}\n"
        "```\n\n"
        "Example — enable two image skills and one twitter skill:\n"
        "```json\n"
        "{\n"
        '  "image": {"enabled": true, "states": {"image_gpt": "public", "image_gemini_flash": "public"}},\n'
        '  "twitter": {"enabled": true, "states": {"post_tweet": "public"}}\n'
        "}\n"
        "```\n\n"
        "Rules:\n"
        "- `enabled`: category-level toggle (must be `true` to activate)\n"
        "- `states`: map of individual skill names to their access level\n"
        "- Access levels: `public` (all users), `private` (owner only)\n"
        "- Only include skills you want to enable — omitted skills stay disabled\n"
        "- The backend will reject unknown categories or skill names with an error\n\n"
        "### Internet Search\n\n"
        "To give an agent web search ability, set the agent field "
        "`search_internet` to `true`. That switch enables the LLM provider's "
        "native web search and is the correct way to add general-purpose "
        "search. Do NOT add categories like `tavily`, `firecrawl`, "
        "`web_scraper`, etc. just to grant search — those are backups for "
        "specialised scraping/extraction needs and only belong in `skills` "
        "when the agent really needs them.\n\n"
        "### Autonomous Tasks\n\n"
        "Tasks belong to an agent and run on a cron schedule. Use these tools:\n"
        "- `lead_list_autonomous_tasks` — list tasks on an agent (call before "
        "edit/delete to discover task IDs).\n"
        "- `lead_add_autonomous_task` — schedule a new task.\n"
        "- `lead_edit_autonomous_task` — update fields on an existing task.\n"
        "- `lead_delete_autonomous_task` — remove a task.\n\n"
        "Workflow:\n"
        "1. If the user did not name an agent, call `lead_list_team_agents`.\n"
        "2. Call `lead_list_autonomous_tasks` to see existing tasks before "
        "adding/editing/deleting.\n"
        "3. Apply the change.\n\n"
        "Cron expressions (5 fields: min hour day month weekday):\n"
        "- `*/5 * * * *` — every 5 min\n"
        "- `0 */2 * * *` — every 2 hours\n"
        "- `0 9 * * *` — daily 9:00 UTC\n"
        "- `0 9 * * 1-5` — weekdays 9:00 UTC\n\n"
        "Conditional tasks: for condition-based work, schedule a polling "
        "task (e.g. every 5 min). Unless the user wants it to run forever, "
        "tell the task to delete itself once the condition is met.\n\n"
        "Tips:\n"
        "- Set `has_memory=True` only when the task needs context between runs.\n"
        "- Prefer disabling (`enabled=False`) over deleting for temporary pauses.\n\n"
        "### Agent Fields Reference\n\n"
        "- `name`: Display name (max 50 chars)\n"
        "- `purpose`, `personality`, `principles`: Agent character\n"
        "- `model`: LLM model ID\n"
        "- `prompt`: Base system prompt\n"
        "- `prompt_append`: Additional system prompt (higher priority)\n"
        "- `temperature`: Randomness (0.0~2.0, lower for rigorous tasks)\n"
        "- `skills`: Skill configurations dict (see format above)\n"
        "- `slug`: URL-friendly slug (immutable once set)\n"
        "- `sub_agents`: List of sub-agent IDs or slugs\n"
        "- `sub_agent_prompt`: Instructions for how to use sub-agents\n"
        "- `enable_todo`, `enable_activity`, `enable_post`: Feature toggles\n"
        "- `enable_long_term_memory`: Enable long-term memory\n"
        "- `super_mode`: Higher recursion limit\n"
        "- `search_internet`: LLM native internet search\n"
        "- `visibility`: PRIVATE(0), TEAM(10), PUBLIC(20)\n"
    )

    agent_data = {
        "id": f"team-{team_id}-agent-manager",
        "owner": "system",
        "team_id": team_id,
        "name": "Agent Manager",
        "purpose": (
            "Create, configure, and update team agents, including the "
            "autonomous tasks scheduled on those agents."
        ),
        "principles": (
            "1. Speak to users in their language, but use English in agent and task configuration.\n"
            "2. All changes are directly deployed (no draft flow).\n"
            "3. Update is override — provide complete field values, not just changes."
        ),
        "model": pick_default_model(),
        "prompt": prompt,
        "temperature": 0.2,
        "search_internet": False,
        "super_mode": False,
        "enable_todo": False,
        "enable_activity": False,
        "enable_post": False,
        "enable_long_term_memory": False,
        "sub_agents": None,
        "skills": {
            "ui": {
                "enabled": True,
                "states": {
                    "ui_show_card": "private",
                    "ui_ask_user": "private",
                },
            },
        },
        "created_at": now,
        "updated_at": now,
    }

    return Agent.model_validate(agent_data)
