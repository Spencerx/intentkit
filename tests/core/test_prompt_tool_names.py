"""Guard the prompt<->tool-name lockstep for the skill->tool rename.

The system prompt hardcodes tool names (e.g. "- create_post:", the `call_agent`
tool). If a rename changes a tool's `.name` but not the prompt that calls it (or
vice-versa), the agent calls a dead name and silently breaks. This test asserts
every tool name referenced in prompt.py resolves to a real registered system tool.
"""

import inspect
import re

from intentkit.core import prompt as prompt_mod
from intentkit.core import system_tools as st
from intentkit.core.system_tools.base import SystemTool


def _system_tool_names():
    names = set()
    for _, obj in inspect.getmembers(st):
        nm = None
        if isinstance(obj, SystemTool):
            nm = obj.name
        elif (
            inspect.isclass(obj)
            and issubclass(obj, SystemTool)
            and obj is not SystemTool
        ):
            field = getattr(obj, "model_fields", {}).get("name")
            nm = field.default if field is not None else getattr(obj, "name", None)
        if isinstance(nm, str):
            names.add(nm)
    return names


def test_system_tools_guide_names_exist():
    real = _system_tool_names()
    assert real, "no system tools discovered"
    section_src = inspect.getsource(prompt_mod.build_system_tools_section)
    referenced = set(re.findall(r"- (\w+):", section_src))
    assert referenced, "no tool names parsed from the System Tools Guide section"
    missing = {n for n in referenced if n not in real}
    assert not missing, (
        f"prompt.py System Tools Guide references tools that do not exist: "
        f"{sorted(missing)}; real system tools: {sorted(real)}"
    )


def test_call_agent_tool_exists():
    # build_sub_agents_section instructs the LLM to use the `call_agent` tool.
    assert "call_agent" in _system_tool_names()
