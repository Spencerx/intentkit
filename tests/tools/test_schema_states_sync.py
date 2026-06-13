"""Guard against drift between each toolset's ToolStates and its schema.json.

The schema.json `states` properties drive the config UI, while the module's
`Config.states` TypedDict drives the runtime filtering in get_tools. A key
mismatch means a tool can never be enabled from the UI (e.g. the historical
`image_enchance` typo in venice_image), so the two key sets must stay equal.

MCP-backed categories discover their tools from the live server at runtime;
their schema.json snapshot is maintained by scripts/sync_mcp_schemas.py and
cannot be checked statically, so they are skipped here.
"""

import importlib
import json
from pathlib import Path

import pytest

from intentkit.tools.base import ToolsetConfig

TOOLS_DIR = Path(__file__).resolve().parents[2] / "intentkit" / "tools"


def _toolset_names():
    return sorted(
        p.name
        for p in TOOLS_DIR.iterdir()
        if p.is_dir() and (p / "schema.json").exists()
    )


def _static_states_keys(module) -> set[str] | None:
    """Keys of the Config.states TypedDict, or None for dynamic toolsets."""
    config_cls = getattr(module, "Config", None)
    if config_cls is None:
        return None
    states_type = getattr(config_cls, "__annotations__", {}).get("states")
    annotations = getattr(states_type, "__annotations__", None)
    if not annotations:
        return None
    return set(annotations)


@pytest.mark.parametrize("name", _toolset_names())
def test_states_keys_match_schema(name):
    module = importlib.import_module(f"intentkit.tools.{name}")
    if getattr(module, "Config", None) is ToolsetConfig:
        # MCP-backed categories alias the base ToolsetConfig and discover
        # their states dynamically — nothing static to compare.
        pytest.skip("toolset discovers states dynamically")
    code_keys = _static_states_keys(module)
    if code_keys is None:
        pytest.fail(
            f"intentkit.tools.{name} must declare Config with a ToolStates "
            f"TypedDict for its states (see agent_docs/tool_development.md)"
        )

    schema = json.loads((TOOLS_DIR / name / "schema.json").read_text())
    schema_keys = set(
        schema.get("properties", {}).get("states", {}).get("properties", {})
    )

    assert code_keys == schema_keys, (
        f"{name}: states keys diverged between code and schema.json\n"
        f"  only in code:   {sorted(code_keys - schema_keys)}\n"
        f"  only in schema: {sorted(schema_keys - code_keys)}\n"
        f"Update the ToolStates TypedDict and schema.json together "
        f"(scripts/sync_states_schema.py can regenerate descriptions)."
    )
