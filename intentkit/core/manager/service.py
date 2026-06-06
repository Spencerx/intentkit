"""Services for agent manager utilities."""

from __future__ import annotations

import json
import logging
from importlib import resources
from pathlib import Path
from typing import Any, cast

import jsonref
from fastapi import status

from intentkit.core.agent import get_agent
from intentkit.models.agent import AgentPublicInfo, AgentUserInput
from intentkit.tools.availability import (
    filter_unavailable_states,
    import_toolset,
    is_individual_tool_available,
    is_toolset_available,
)
from intentkit.utils.error import IntentKitAPIError

logger = logging.getLogger(__name__)


def agent_draft_json_schema() -> dict[str, object]:
    """Return AgentUserInput schema tailored for LLM draft generation."""
    schema: dict[str, Any] = AgentUserInput.model_json_schema()
    properties: dict[str, object] = schema.get("properties", {})

    fields_to_remove = {"autonomous", "frequency_penalty", "presence_penalty"}
    for field in fields_to_remove:
        _ = properties.pop(field, None)

    if "required" in schema and isinstance(schema["required"], list):
        schema["required"] = [
            field for field in schema["required"] if field not in fields_to_remove
        ]

    tools_property = properties.get("tools")
    if not isinstance(tools_property, dict):
        return schema

    tools_property = cast(dict[str, Any], tools_property)

    tools_properties: dict[str, object] = {}
    try:
        traversable = resources.files("intentkit.tools")
        with resources.as_file(traversable) as tools_root:
            for entry in tools_root.iterdir():
                if not entry.is_dir():
                    continue

                schema_path = entry / "schema.json"
                if not schema_path.is_file():
                    continue

                category = entry.name

                module = import_toolset(category)
                if module is None or not is_toolset_available(module):
                    logger.info(
                        "Skipped toolset '%s' for manager schema: not available",
                        category,
                    )
                    continue

                try:
                    tool_schema = _load_tool_schema(schema_path)
                except (
                    OSError,
                    ValueError,
                    json.JSONDecodeError,
                    jsonref.JsonRefError,
                ) as exc:
                    logger.warning(
                        "Failed to load schema for tool '%s': %s", category, exc
                    )
                    continue

                schema_props = tool_schema.get("properties")
                if isinstance(schema_props, dict):
                    states = schema_props.get("states")
                    if isinstance(states, dict):
                        schema_props["states"] = filter_unavailable_states(
                            module, category, states
                        )

                tools_properties[category] = tool_schema
    except (AttributeError, ModuleNotFoundError, ImportError):
        logger.warning("intentkit tools package not found when building schema")
        return schema

    if tools_properties:
        _ = tools_property.setdefault("type", "object")
        tools_property["properties"] = tools_properties

    return schema


def get_tools_hierarchical_text() -> str:
    """Extract tools organized by category and return as hierarchical text."""
    try:
        traversable = resources.files("intentkit.tools")
        with resources.as_file(traversable) as tools_root:
            # Group tools by category (x-tags)
            categories: dict[str, list[Any]] = {}
            for entry in tools_root.iterdir():
                if not entry.is_dir():
                    continue

                schema_path = entry / "schema.json"
                if not schema_path.is_file():
                    continue

                category = entry.name

                module = import_toolset(category)
                if module is None or not is_toolset_available(module):
                    logger.info(
                        "Skipped toolset '%s' for hierarchical text: not available",
                        category,
                    )
                    continue

                try:
                    tool_schema = _load_tool_schema(schema_path)
                    tool_title = tool_schema.get(
                        "title", category.replace("_", " ").title()
                    )
                    tool_description = tool_schema.get(
                        "description", "No description available"
                    )
                    tool_tags = cast(list[str], tool_schema.get("x-tags", ["Other"]))

                    # Use the first tag as the primary group
                    primary_category = tool_tags[0] if tool_tags else "Other"

                    individual_tools: list[dict[str, str]] = []
                    states_props = _get_states_properties(tool_schema)
                    if states_props:
                        for ind_name, ind_def in states_props.items():
                            if not is_individual_tool_available(
                                module, category, ind_name
                            ):
                                continue
                            ind_desc = (
                                ind_def.get("description", "No description available")
                                if isinstance(ind_def, dict)
                                else "No description available"
                            )
                            individual_tools.append(
                                {"name": ind_name, "description": ind_desc}
                            )

                    # Drop the category entirely if every tool was filtered;
                    # surfacing an empty group would just be noise to the LLM.
                    if states_props and not individual_tools:
                        continue

                    if primary_category not in categories:
                        categories[primary_category] = []

                    categories[primary_category].append(
                        {
                            "name": category,
                            "title": tool_title,
                            "description": tool_description,
                            "individual_tools": individual_tools,
                        }
                    )

                except (
                    OSError,
                    ValueError,
                    json.JSONDecodeError,
                    jsonref.JsonRefError,
                ) as exc:
                    logger.warning(
                        "Failed to load schema for tool '%s': %s", category, exc
                    )
                    continue
    except (AttributeError, ModuleNotFoundError, ImportError):
        logger.warning("intentkit tools package not found when building tools text")
        return "No tools available"

    # Build hierarchical text
    text_lines = []
    text_lines.append("Available Tools by Category:")
    text_lines.append("")

    # Sort categories alphabetically
    for category in sorted(categories.keys()):
        text_lines.append(f"#### {category}")
        text_lines.append("")

        # Sort tools within category alphabetically by name
        for tool in sorted(categories[category], key=lambda x: x["name"]):
            text_lines.append(
                f"- **{tool['name']}** ({tool['title']}): {tool['description']}"
            )
            # Add individual tools indented under the category tool
            for ind_tool in sorted(
                tool.get("individual_tools", []), key=lambda x: x["name"]
            ):
                text_lines.append(
                    f"  - `{ind_tool['name']}`: {ind_tool['description']}"
                )

        text_lines.append("")

    return "\n".join(text_lines)


def _load_tool_schema(schema_path: Path) -> dict[str, object]:
    base_uri = f"file://{schema_path}"
    with schema_path.open("r", encoding="utf-8") as schema_file:
        embedded_schema: dict[str, object] = cast(
            dict[str, object],
            jsonref.load(
                schema_file, base_uri=base_uri, proxies=False, lazy_load=False
            ),
        )

    schema_copy = dict(embedded_schema)
    _ = schema_copy.setdefault(
        "title", schema_path.parent.name.replace("_", " ").title()
    )
    return schema_copy


def _get_states_properties(tool_schema: dict[str, object]) -> dict[str, Any] | None:
    """Extract states.properties from a tool schema, or None if invalid."""
    properties = tool_schema.get("properties", {})
    if not isinstance(properties, dict):
        return None
    states = properties.get("states", {})
    if not isinstance(states, dict):
        return None
    state_props = states.get("properties", {})
    return cast(dict[str, Any], state_props) if isinstance(state_props, dict) else None


def get_valid_tools_registry() -> dict[str, dict[str, str]]:
    """Load all tool schemas and return a registry of valid tools.

    Returns a nested dict mapping category name to a dict of tool names
    and their descriptions: ``{category: {tool_name: description}}``.

    Broken or unreadable schemas are silently skipped.
    """
    registry: dict[str, dict[str, str]] = {}
    try:
        traversable = resources.files("intentkit.tools")
        with resources.as_file(traversable) as tools_root:
            for entry in sorted(tools_root.iterdir(), key=lambda p: p.name):
                if not entry.is_dir():
                    continue

                schema_path = entry / "schema.json"
                if not schema_path.is_file():
                    continue

                try:
                    tool_schema = _load_tool_schema(schema_path)
                except (
                    OSError,
                    ValueError,
                    json.JSONDecodeError,
                    jsonref.JsonRefError,
                ) as exc:
                    logger.warning(
                        "Failed to load schema for tool '%s': %s", entry.name, exc
                    )
                    continue

                state_props = _get_states_properties(tool_schema)
                if not state_props:
                    continue

                category_name = entry.name
                tools: dict[str, str] = {}
                for tool_name, tool_def in state_props.items():
                    if isinstance(tool_def, dict):
                        description = tool_def.get("description", "")
                        if isinstance(description, str) and description:
                            tools[tool_name] = description

                if tools:
                    registry[category_name] = tools

    except (AttributeError, ModuleNotFoundError, ImportError):
        logger.warning("intentkit tools package not found when building tools registry")

    return registry


_VALID_TOOL_STATES = {"disabled", "public", "private"}


def validate_tools(tools: dict[str, Any] | None) -> None:
    """Validate tools config. Raises IntentKitAPIError(400) on invalid entries."""
    if not tools:
        return

    registry = get_valid_tools_registry()
    valid_categories = sorted(registry.keys())

    for category, config in tools.items():
        if category not in registry:
            raise IntentKitAPIError(
                400,
                "InvalidToolset",
                f"Unknown toolset '{category}'. Valid categories: {valid_categories}",
            )

        if not isinstance(config, dict):
            raise IntentKitAPIError(
                400,
                "InvalidToolFormat",
                f"Toolset '{category}' config must be a dict, got {type(config).__name__}",
            )

        states = config.get("states")
        if states is not None and not isinstance(states, dict):
            raise IntentKitAPIError(
                400,
                "InvalidToolFormat",
                f"'states' in category '{category}' must be a dict, got {type(states).__name__}",
            )

        if not isinstance(states, dict):
            states = {}
        valid_tool_names = sorted(registry[category].keys())

        for tool_name, state_value in states.items():
            if tool_name not in registry[category]:
                raise IntentKitAPIError(
                    400,
                    "InvalidToolName",
                    f"Unknown tool '{tool_name}' in category '{category}'. Valid tools: {valid_tool_names}",
                )
            if state_value not in _VALID_TOOL_STATES:
                raise IntentKitAPIError(
                    400,
                    "InvalidToolState",
                    f"Invalid state '{state_value}' for tool '{tool_name}'. Valid states: {sorted(_VALID_TOOL_STATES)}",
                )


def sanitize_tools(tools: dict[str, Any] | None) -> dict[str, Any] | None:
    """Remove tools/categories not in schema. Returns cleaned dict or None if empty."""
    if not tools:
        return None

    registry = get_valid_tools_registry()
    cleaned: dict[str, Any] = {}

    for category, config in tools.items():
        if category not in registry:
            continue

        # Preserve non-dict configs as-is (don't silently drop)
        if not isinstance(config, dict):
            cleaned[category] = config
            continue

        states = config.get("states")
        # Preserve non-dict states as-is
        if not isinstance(states, dict):
            cleaned[category] = config
            continue

        cleaned_states = {
            tool_name: state_value
            for tool_name, state_value in states.items()
            if tool_name in registry[category]
        }

        if cleaned_states:
            cleaned_config = dict(config)
            cleaned_config["states"] = cleaned_states
            cleaned[category] = cleaned_config

    return cleaned if cleaned else None


async def get_latest_public_info(*, agent_id: str, user_id: str) -> AgentPublicInfo:
    """Return the latest public information for a specific agent."""

    agent = await get_agent(agent_id)
    if not agent:
        raise IntentKitAPIError(
            status.HTTP_404_NOT_FOUND, "AgentNotFound", "Agent not found"
        )

    if agent.owner != user_id:
        raise IntentKitAPIError(
            status.HTTP_403_FORBIDDEN,
            "AgentForbidden",
            "Not authorized to access this agent",
        )

    return AgentPublicInfo.model_validate(agent)
