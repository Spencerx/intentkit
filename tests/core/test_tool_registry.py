"""Tests for get_valid_tools_registry utility."""

from intentkit.core.agent.tool_registry import get_valid_tools_registry


def test_get_valid_tools_registry_returns_categories():
    """Registry must return a dict keyed by category with tool dicts inside."""
    registry = get_valid_tools_registry()
    assert isinstance(registry, dict)
    assert "ui" in registry
    assert "ui_show_card" in registry["ui"]
    assert "ui_ask_user" in registry["ui"]
    assert isinstance(registry["ui"]["ui_show_card"], str)
    assert len(registry["ui"]["ui_show_card"]) > 0


def test_get_valid_tools_registry_has_no_empty_categories():
    """Every category must have at least one tool."""
    registry = get_valid_tools_registry()
    for category, tools in registry.items():
        assert len(tools) > 0, f"Category '{category}' has no tools"
