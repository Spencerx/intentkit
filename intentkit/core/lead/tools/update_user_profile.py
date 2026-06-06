"""Tool to update the current user's profile."""

from __future__ import annotations

import logging
from typing import Any, override
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.config.redis import get_redis
from intentkit.core.lead.tools.base import LeadTool
from intentkit.models.user import UserUpdate

logger = logging.getLogger(__name__)

# Must stay in sync with USER_CACHE_PREFIX in app/team/user.py — we duplicate
# the constant because core/ cannot import from app/.
_USER_CACHE_PREFIX = "intentkit:user:"


class UpdateUserProfileInput(BaseModel):
    """Input model for lead_update_user_profile tool."""

    name: str | None = Field(
        default=None,
        description="New display name (max 50 chars). Omit to keep unchanged.",
    )
    timezone: str | None = Field(
        default=None,
        description=(
            "IANA timezone identifier (e.g. 'Asia/Shanghai', 'America/New_York'). "
            "Convert offsets like 'GMT+8' to the corresponding IANA name first. "
            "Omit to keep unchanged. Pass an empty string to clear."
        ),
    )
    language: str | None = Field(
        default=None,
        description=(
            "Preferred language as a BCP 47 tag (e.g. 'zh-CN', 'en', 'ja'). "
            "Omit to keep unchanged. Pass an empty string to clear."
        ),
    )


class UpdateUserProfileOutput(BaseModel):
    """Output model for lead_update_user_profile tool."""

    message: str = Field(description="Success message")
    updated_fields: list[str] = Field(description="List of fields that were updated")


class LeadUpdateUserProfile(LeadTool):
    """Tool to update the current user's profile (name, timezone, language).

    Writes go through `UserUpdate.patch`, so a row is created if the user does
    not yet exist. The user's API-side Redis cache is invalidated so the next
    GET reflects the change.
    """

    name: str = "lead_update_user_profile"
    description: str = (
        "Update the current user's profile. Supported fields: name, timezone, "
        "language. Only provide the fields you want to change. The user is "
        "always taken from the current conversation context — never accept a "
        "user id as input."
    )
    args_schema: ArgsSchema | None = UpdateUserProfileInput

    @override
    async def _arun(
        self,
        name: str | None = None,
        timezone: str | None = None,
        language: str | None = None,
        **kwargs: Any,
    ) -> UpdateUserProfileOutput:
        context = self.get_context()
        user_id = context.user_id
        if not user_id:
            raise ToolException("No user_id in context")

        updates: dict[str, Any] = {}
        updated_fields: list[str] = []

        if name is not None:
            trimmed = name.strip()
            if trimmed:
                updates["name"] = trimmed[:50]
                updated_fields.append("name")

        if timezone is not None:
            tz = timezone.strip()
            if tz:
                try:
                    ZoneInfo(tz)
                except (ZoneInfoNotFoundError, ValueError) as exc:
                    raise ToolException(
                        f"Invalid IANA timezone: {timezone!r}. "
                        "Use a name like 'Asia/Shanghai' or 'America/New_York'."
                    ) from exc
                updates["timezone"] = tz
            else:
                updates["timezone"] = None
            updated_fields.append("timezone")

        if language is not None:
            lang = language.strip()
            updates["language"] = lang[:32] if lang else None
            updated_fields.append("language")

        if not updates:
            return UpdateUserProfileOutput(
                message="No fields provided to update.",
                updated_fields=[],
            )

        await UserUpdate.model_validate(updates).patch(user_id)

        try:
            redis = get_redis()
            await redis.delete(f"{_USER_CACHE_PREFIX}{user_id}")
        except Exception as exc:
            logger.warning("Failed to invalidate user cache for %s: %s", user_id, exc)

        return UpdateUserProfileOutput(
            message=f"User profile updated: {', '.join(updated_fields)}.",
            updated_fields=updated_fields,
        )


lead_update_user_profile_tool = LeadUpdateUserProfile()
