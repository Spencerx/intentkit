import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from fastapi import Path as PathParam
from fastapi.responses import FileResponse, JSONResponse

from intentkit.models.agent import AGENT_TAG_CATEGORIES, Agent, AgentPublicInfo
from intentkit.tools.availability import (
    filter_unavailable_states,
    import_toolset,
    is_toolset_available,
)
from intentkit.utils.error import IntentKitAPIError

_AGENT_PUBLIC_TAGS_PAYLOAD = [
    {"value": tag.value, "category": category}
    for category, tags in AGENT_TAG_CATEGORIES.items()
    for tag in tags
]

logger = logging.getLogger(__name__)

# Create readonly router
schema_router = APIRouter()

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent


def _simplify_tool_schema(tool_schema: dict[str, Any]) -> dict[str, Any]:
    """Simplify tool schema to only keep enabled and states fields.

    Args:
        tool_schema: The original tool schema

    Returns:
        Simplified schema with only enabled, states, title, description, and type
    """
    simplified: dict[str, Any] = {}

    # Keep basic metadata
    for key in ["title", "description", "type", "x-icon"]:
        if key in tool_schema:
            simplified[key] = tool_schema[key]

    # Keep only enabled and states in properties
    original_properties = tool_schema.get("properties", {})
    if original_properties:
        simplified_properties: dict[str, Any] = {}
        if "enabled" in original_properties:
            simplified_properties["enabled"] = original_properties["enabled"]
        if "states" in original_properties:
            simplified_properties["states"] = original_properties["states"]
        if simplified_properties:
            simplified["properties"] = simplified_properties

    return simplified


@schema_router.get("/schema/agent", tags=["Metadata"], operation_id="get_agent_schema")
async def get_agent_schema() -> JSONResponse:
    """Get the JSON schema for Agent model with all $ref references resolved.

    This function applies additional adaptations:
    - Populates the model enum from the in-memory LLM catalog (enabled models only)
    - Filters out toolsets where available() returns False
    - Simplifies tool schemas to only keep enabled and states fields
    - Removes telegram-related fields

    **Returns:**
    * `JSONResponse` - The complete JSON schema for the Agent model with application/json content type
    """
    schema = await Agent.get_json_schema()
    properties = schema.get("properties", {})

    # Remove telegram-related fields
    properties.pop("telegram_entrypoint_enabled", None)
    properties.pop("telegram_entrypoint_prompt", None)
    properties.pop("telegram_config", None)

    # Filter and simplify tools
    tools_property = properties.get("tools", {})
    if tools_property and "properties" in tools_property:
        original_tools = tools_property["properties"]
        filtered_tools: dict[str, Any] = {}

        for category, tool_schema in original_tools.items():
            module = import_toolset(category)
            if module is None or not is_toolset_available(module):
                logger.info(
                    "Filtered out tool '%s': not available in current config",
                    category,
                )
                continue

            simplified = _simplify_tool_schema(tool_schema)

            states = simplified.get("properties", {}).get("states")
            if states:
                simplified["properties"]["states"] = filter_unavailable_states(
                    module, category, states
                )

            filtered_tools[category] = simplified

        tools_property["properties"] = filtered_tools

    return JSONResponse(
        content=schema,
        media_type="application/json",
    )


@schema_router.get(
    "/schema/agent-public-info",
    tags=["Metadata"],
    operation_id="get_agent_public_info_schema",
)
async def get_agent_public_info_schema() -> JSONResponse:
    """Get the JSON schema for the AgentPublicInfo model.

    Used by team frontends when collecting public info as part of publishing
    an agent.
    """
    return JSONResponse(
        content=AgentPublicInfo.model_json_schema(),
        media_type="application/json",
    )


@schema_router.get(
    "/schema/agent-public-tags",
    tags=["Metadata"],
    operation_id="get_agent_public_tags",
)
async def get_agent_public_tags() -> JSONResponse:
    """List the predefined tag values usable when publishing an agent.

    Returned as a flat list of ``{value, category}`` entries in display order;
    the team frontend renders the labels client-side (capitalisation/i18n).
    """
    return JSONResponse(
        content=_AGENT_PUBLIC_TAGS_PAYLOAD,
        media_type="application/json",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@schema_router.get(
    "/tools/{tool}/schema.json",
    tags=["Metadata"],
    operation_id="get_tool_schema",
    responses={
        200: {"description": "Success"},
        404: {"description": "Tool not found"},
        400: {"description": "Invalid tool name"},
    },
)
async def get_tool_schema(
    tool: str = PathParam(..., description="Tool name", pattern="^[a-zA-Z0-9_-]+$"),
) -> JSONResponse:
    """Get the JSON schema for a specific tool.

    **Path Parameters:**
    * `tool` - Tool name

    **Returns:**
    * `JSONResponse` - The complete JSON schema for the tool with application/json content type

    **Raises:**
    * `IntentKitAPIError` - If the tool is not found or name is invalid
    """
    base_path = PROJECT_ROOT / "intentkit" / "tools"
    schema_path = base_path / tool / "schema.json"
    normalized_path = schema_path.resolve()

    if not normalized_path.is_relative_to(base_path):
        raise IntentKitAPIError(400, "BadRequest", "Invalid tool name")

    try:
        with open(normalized_path) as f:
            schema = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        raise IntentKitAPIError(404, "NotFound", "Tool schema not found")

    return JSONResponse(content=schema, media_type="application/json")


@schema_router.get(
    "/tools/{tool}/{icon_name}.{ext}",
    tags=["Metadata"],
    operation_id="get_tool_icon",
    responses={
        200: {"description": "Success"},
        404: {"description": "Tool icon not found"},
        400: {"description": "Invalid tool name or extension"},
    },
)
async def get_tool_icon(
    tool: str = PathParam(..., description="Tool name", pattern="^[a-zA-Z0-9_-]+$"),
    icon_name: str = PathParam(..., description="Icon name"),
    ext: str = PathParam(
        ..., description="Icon file extension", pattern="^(png|svg|jpg|jpeg|webp)$"
    ),
) -> FileResponse:
    """Get the icon for a specific tool.

    **Path Parameters:**
    * `tool` - Tool name
    * `icon_name` - Icon name
    * `ext` - Icon file extension (png or svg)

    **Returns:**
    * `FileResponse` - The icon file with appropriate content type

    **Raises:**
    * `IntentKitAPIError` - If the tool or icon is not found or name is invalid
    """
    base_path = PROJECT_ROOT / "intentkit" / "tools"
    icon_path = base_path / tool / f"{icon_name}.{ext}"
    normalized_path = icon_path.resolve()

    if not normalized_path.is_relative_to(base_path):
        raise IntentKitAPIError(400, "BadRequest", "Invalid tool name")

    if not normalized_path.exists():
        raise IntentKitAPIError(404, "NotFound", "Tool icon not found")

    content_type = (
        "image/svg+xml"
        if ext == "svg"
        else "image/png"
        if ext in ["png"]
        else "image/webp"
        if ext in ["webp"]
        else "image/jpeg"
    )
    return FileResponse(normalized_path, media_type=content_type)
