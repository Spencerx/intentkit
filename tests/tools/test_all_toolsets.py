"""Smoke coverage across every toolset plugin (cheap net for the skill->tool rename).

Imports each toolset under intentkit/tools/ and asserts it still exposes the
renamed `get_tools` entrypoint (was `get_skills`), plus that its schema.json
parses. One parametrized test covers all ~52 plugins, including the many that
have no dedicated test file.
"""

import importlib
import json
from pathlib import Path

import pytest

TOOLS_DIR = Path(__file__).resolve().parents[2] / "intentkit" / "tools"

# MCP-driven toolsets expose their tools dynamically (no module-level get_tools).
NO_GET_TOOLS = {"mcp_coingecko"}


def _toolset_names():
    names = []
    for p in sorted(TOOLS_DIR.iterdir()):
        if p.is_dir() and p.name != "__pycache__" and (p / "__init__.py").exists():
            names.append(p.name)
    return names


TOOLSETS = _toolset_names()


def test_toolsets_discovered():
    # Guard against an empty parametrization silently passing.
    assert len(TOOLSETS) >= 40, f"only found {len(TOOLSETS)} toolsets"


@pytest.mark.parametrize("name", TOOLSETS)
def test_toolset_imports_and_exposes_get_tools(name):
    mod = importlib.import_module(f"intentkit.tools.{name}")
    if name in NO_GET_TOOLS:
        return
    assert hasattr(mod, "get_tools"), (
        f"intentkit.tools.{name} is missing get_tools "
        f"(the get_skills->get_tools rename must reach every plugin)"
    )
    assert callable(mod.get_tools)


@pytest.mark.parametrize("name", TOOLSETS)
def test_toolset_schema_parses(name):
    schema = TOOLS_DIR / name / "schema.json"
    if not schema.exists():
        pytest.skip(f"{name} has no schema.json")
    data = json.loads(schema.read_text())
    props = data.get("properties", {})
    assert "states" in props or "enabled" in props, (
        f"{name}/schema.json missing the states/enabled config sub-shape"
    )
