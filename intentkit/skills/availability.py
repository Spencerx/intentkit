"""Helpers for inspecting which skills are usable in the current deployment.

A skill category exposes a module-level ``available()`` callable that checks
its system config (API keys, env vars, etc.). Individual skills inside a
category may also expose ``available()`` on the instance for finer-grained
gating (e.g. wallet/scope checks). These helpers wrap both layers so callers
that build user-facing skill listings (``app/common/schema.py``,
``intentkit/core/manager/service.py``) can drop everything that wouldn't
actually run.
"""

from __future__ import annotations

import importlib
import logging
from types import ModuleType
from typing import Any, Callable

logger = logging.getLogger(__name__)


def import_skill_category(category: str) -> ModuleType | None:
    """Import a skill category module, returning None on failure."""
    try:
        return importlib.import_module(f"intentkit.skills.{category}")
    except Exception as exc:
        logger.warning("Could not import skill category '%s': %s", category, exc)
        return None


def is_skill_category_available(module: ModuleType) -> bool:
    """Whether the category module reports itself available.

    Missing ``available()`` defaults to True; a raising ``available()``
    defaults to False so a misconfigured skill never blocks the listing.
    """
    available_fn = getattr(module, "available", None)
    if available_fn is None:
        return True
    try:
        return bool(available_fn())
    except Exception as exc:
        logger.debug(
            "available() raised for category module %r: %s", module.__name__, exc
        )
        return False


def find_skill_getter(module: ModuleType, category: str) -> Callable[..., Any] | None:
    """Locate the ``get_<name>_skill`` accessor for a category module.

    Convention is ``get_{category}_skill``; falls back to any ``get_*_skill``
    attribute (e.g. ``moralis`` exposes ``get_wallet_skill``).
    """
    getter = getattr(module, f"get_{category}_skill", None)
    if getter is not None:
        return getter
    for attr_name in dir(module):
        if attr_name.startswith("get_") and attr_name.endswith("_skill"):
            return getattr(module, attr_name)
    return None


def is_individual_skill_available(
    module: ModuleType, category: str, skill_name: str
) -> bool:
    """Whether a specific skill within a category reports itself available.

    Defaults to True when the module has no getter, the getter raises, the
    skill instance is None, or the skill exposes no ``available()``.
    """
    getter = find_skill_getter(module, category)
    if getter is None:
        return True
    try:
        skill = getter(skill_name)
    except Exception as exc:
        logger.debug("Skill getter raised for '%s/%s': %s", category, skill_name, exc)
        return True
    if skill is None:
        return True
    available_fn = getattr(skill, "available", None)
    if available_fn is None:
        return True
    try:
        return bool(available_fn())
    except Exception as exc:
        logger.debug(
            "available() raised for skill '%s/%s': %s", category, skill_name, exc
        )
        return False


def filter_unavailable_states(
    module: ModuleType, category: str, states_schema: dict[str, Any]
) -> dict[str, Any]:
    """Drop unavailable individual skills from a JSON-schema ``states`` block.

    Returns a new dict with ``properties`` (and ``required``, if present)
    pruned. The input is not mutated.
    """
    properties = states_schema.get("properties")
    if not isinstance(properties, dict):
        return states_schema

    filtered_properties: dict[str, Any] = {}
    for skill_name, skill_schema in properties.items():
        if not is_individual_skill_available(module, category, skill_name):
            logger.info(
                "Filtered out skill '%s/%s': not available", category, skill_name
            )
            continue
        filtered_properties[skill_name] = skill_schema

    result = {**states_schema, "properties": filtered_properties}
    if "required" in result and isinstance(result["required"], list):
        result["required"] = [r for r in result["required"] if r in filtered_properties]
    return result
