"""Filter unavailable skill categories out of manager-facing listings.

The single-agent manager and the team agent-manager both rely on these helpers
to advertise skills to the LLM. Categories whose system config (API keys, etc.)
is not configured should never appear, otherwise the LLM picks skills that
will never run.
"""

from __future__ import annotations

import importlib
from typing import Any

import pytest

from intentkit.core.manager import service as manager_service


def _category_in_schema(schema: dict[str, Any], category: str) -> bool:
    skills = schema.get("properties", {}).get("skills", {})
    return category in skills.get("properties", {})


def test_unavailable_category_excluded_from_draft_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Categories whose available() returns False are dropped from the schema."""
    firecrawl_module = importlib.import_module("intentkit.skills.firecrawl")
    monkeypatch.setattr(firecrawl_module, "available", lambda: False)

    schema = manager_service.agent_draft_json_schema()
    assert not _category_in_schema(schema, "firecrawl")


def test_unavailable_category_excluded_from_hierarchical_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Categories whose available() returns False are dropped from the listing."""
    firecrawl_module = importlib.import_module("intentkit.skills.firecrawl")
    monkeypatch.setattr(firecrawl_module, "available", lambda: False)

    text = manager_service.get_skills_hierarchical_text()
    assert "**firecrawl**" not in text


def test_available_category_still_included(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sanity-check: forcing available() to True keeps the category in."""
    firecrawl_module = importlib.import_module("intentkit.skills.firecrawl")
    monkeypatch.setattr(firecrawl_module, "available", lambda: True)

    schema = manager_service.agent_draft_json_schema()
    assert _category_in_schema(schema, "firecrawl")


def test_ui_category_always_present() -> None:
    """The UI category has no system-config gate, so it must always appear."""
    schema = manager_service.agent_draft_json_schema()
    assert _category_in_schema(schema, "ui")

    text = manager_service.get_skills_hierarchical_text()
    assert "**ui**" in text
