import pytest

from intentkit.core.manager.service import sanitize_tools, validate_tools
from intentkit.utils.error import IntentKitAPIError


def test_validate_tools_accepts_valid_config():
    tools = {
        "ui": {
            "enabled": True,
            "states": {"ui_show_card": "public", "ui_ask_user": "private"},
        }
    }
    validate_tools(tools)  # Should not raise


def test_validate_tools_rejects_unknown_category():
    tools = {
        "nonexistent_category": {
            "enabled": True,
            "states": {"some_tool": "public"},
        }
    }
    with pytest.raises(IntentKitAPIError, match="nonexistent_category"):
        validate_tools(tools)


def test_validate_tools_rejects_unknown_tool_name():
    tools = {"ui": {"enabled": True, "states": {"fake_tool": "public"}}}
    with pytest.raises(IntentKitAPIError, match="fake_tool"):
        validate_tools(tools)


def test_validate_tools_rejects_invalid_state_value():
    tools = {"ui": {"enabled": True, "states": {"ui_show_card": "enabled"}}}
    with pytest.raises(IntentKitAPIError, match="ui_show_card"):
        validate_tools(tools)


def test_validate_tools_rejects_non_dict_category_config():
    tools = {"ui": "bad"}
    with pytest.raises(IntentKitAPIError, match="must be a dict"):
        validate_tools(tools)


def test_validate_tools_rejects_non_dict_states():
    tools = {"ui": {"enabled": True, "states": "bad"}}
    with pytest.raises(IntentKitAPIError, match="must be a dict"):
        validate_tools(tools)


def test_validate_tools_allows_none():
    validate_tools(None)


def test_validate_tools_allows_empty():
    validate_tools({})


def test_sanitize_tools_removes_unknown_category():
    tools = {
        "ui": {"enabled": True, "states": {"ui_show_card": "public"}},
        "nonexistent": {"enabled": True, "states": {"x": "public"}},
    }
    result = sanitize_tools(tools)
    assert result is not None
    assert "ui" in result
    assert "nonexistent" not in result


def test_sanitize_tools_removes_unknown_tool():
    tools = {
        "ui": {
            "enabled": True,
            "states": {"ui_show_card": "public", "deleted_tool": "public"},
        }
    }
    result = sanitize_tools(tools)
    assert result is not None
    assert "ui_show_card" in result["ui"]["states"]
    assert "deleted_tool" not in result["ui"]["states"]


def test_sanitize_tools_removes_category_if_all_tools_gone():
    tools = {
        "ui": {
            "enabled": True,
            "states": {"deleted_tool_1": "public", "deleted_tool_2": "public"},
        }
    }
    result = sanitize_tools(tools)
    assert "ui" not in (result or {})


def test_sanitize_tools_preserves_non_dict_config():
    """Sanitize should not silently wipe malformed configs."""
    tools = {
        "ui": "bad",
        "nonexistent": {"enabled": True, "states": {"x": "public"}},
    }
    result = sanitize_tools(tools)
    # ui is a valid category, so it's preserved even though config is malformed
    assert result is not None
    assert "ui" in result
    assert result["ui"] == "bad"
    # nonexistent category still dropped
    assert "nonexistent" not in result


def test_sanitize_tools_returns_none_for_none():
    assert sanitize_tools(None) is None


def test_sanitize_tools_returns_none_for_empty():
    assert sanitize_tools({}) is None
