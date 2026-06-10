from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Annotated, Any, ClassVar

from cron_validator import CronValidator
from epyxid import XID
from pydantic import BaseModel, ConfigDict, field_serializer, field_validator
from pydantic import Field as PydanticField
from sqlalchemy import Boolean, DateTime, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from intentkit.config.base import Base
from intentkit.utils.error import IntentKitAPIError


class AutonomousTaskStatus(str, Enum):
    """Autonomous task execution status."""

    WAITING = "waiting"
    RUNNING = "running"
    ERROR = "error"


def minutes_to_cron(minutes: int) -> str:
    """Convert minutes interval to a cron expression.

    This is a simple conversion that creates a cron expression like `*/n * * * *`
    where n is the number of minutes.

    Args:
        minutes: Interval in minutes (should be >= 1)

    Returns:
        A cron expression string
    """
    if minutes <= 0:
        minutes = 5  # Default to 5 minutes if invalid
    if minutes >= 60:
        # For intervals >= 60 minutes, use hourly scheduling
        hours = minutes // 60
        if hours >= 24:
            # Run once a day at midnight
            return "0 0 * * *"
        return f"0 */{hours} * * *"
    return f"*/{minutes} * * * *"


def validate_cron_schedule(cron: str | None) -> None:
    """Validate a cron expression for an autonomous task.

    Ensures the cron expression is well-formed and the resulting interval is at
    least 5 minutes. Raises :class:`IntentKitAPIError` on any violation.
    """
    if not cron:
        raise IntentKitAPIError(
            status_code=400,
            key="InvalidAutonomousConfig",
            message="cron must have a value",
        )

    try:
        _ = CronValidator.parse(cron)
    except ValueError:
        raise IntentKitAPIError(
            status_code=400,
            key="InvalidCronExpression",
            message=f"Invalid cron expression format: {cron}",
        )

    parts = cron.split()
    if len(parts) < 5:
        raise IntentKitAPIError(
            status_code=400,
            key="InvalidCronExpression",
            message="Invalid cron expression format",
        )

    minute, hour, *_ = parts[:5]

    # A bare "*" minute runs every minute, which is below the 5-minute minimum.
    if minute == "*":
        raise IntentKitAPIError(
            status_code=400,
            key="InvalidAutonomousInterval",
            message="The shortest execution interval is 5 minutes",
        )

    if "/" in minute:
        # Check step value in minute field (e.g., */15)
        step = int(minute.split("/")[1])
        if step < 5 and hour == "*":
            raise IntentKitAPIError(
                status_code=400,
                key="InvalidAutonomousInterval",
                message="The shortest execution interval is 5 minutes",
            )

    # Comma-separated values or ranges with a wildcard hour run multiple times/hour
    if ("," in minute or "-" in minute) and hour == "*":
        raise IntentKitAPIError(
            status_code=400,
            key="InvalidAutonomousInterval",
            message="The shortest execution interval is 5 minutes",
        )


class AutonomousCreateRequest(BaseModel):
    """Request model for creating a new team autonomous task."""

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

    name: str | None = PydanticField(
        default=None,
        description="Display name of the autonomous configuration",
        max_length=50,
    )
    description: str | None = PydanticField(
        default=None,
        description="Description of the autonomous configuration",
        max_length=200,
    )
    cron: str = PydanticField(
        ...,
        description="Cron expression for scheduling operations",
    )
    prompt: str = PydanticField(
        ...,
        description="Special prompt used during autonomous operation",
        max_length=20000,
    )
    enabled: bool = PydanticField(
        default=True,
        description="Whether the autonomous configuration is enabled",
    )
    has_memory: bool = PydanticField(
        default=False,
        description="Whether to retain conversation memory between autonomous runs.",
    )
    target_agent_id: str | None = PydanticField(
        default=None,
        description=(
            "Optional target agent. When set, the task runs directly on that "
            "agent; when omitted, the task runs through the team lead, which "
            "decides delegation from the prompt."
        ),
    )


class AutonomousUpdateRequest(BaseModel):
    """Request model for modifying a team autonomous task."""

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

    name: str | None = PydanticField(
        default=None,
        description="Display name of the autonomous configuration",
        max_length=50,
    )
    description: str | None = PydanticField(
        default=None,
        description="Description of the autonomous configuration",
        max_length=200,
    )
    cron: str | None = PydanticField(
        default=None,
        description="Cron expression for scheduling operations",
    )
    prompt: str | None = PydanticField(
        default=None,
        description="Special prompt used during autonomous operation",
        max_length=20000,
    )
    enabled: bool | None = PydanticField(
        default=None,
        description="Whether the autonomous configuration is enabled",
    )
    has_memory: bool | None = PydanticField(
        default=None,
        description="Whether to retain conversation memory between autonomous runs.",
    )
    target_agent_id: str | None = PydanticField(
        default=None,
        description="Optional target agent to run the task on directly.",
    )


class AutonomousTask(BaseModel):
    """A team-owned autonomous task configuration."""

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

    id: Annotated[
        str,
        PydanticField(
            description="Unique identifier for the autonomous configuration",
            default_factory=lambda: str(XID()),
            min_length=1,
            max_length=20,
            pattern=r"^[a-z0-9-]+$",
        ),
    ]
    team_id: Annotated[
        str,
        PydanticField(description="Team that owns this autonomous task"),
    ]
    target_agent_id: Annotated[
        str | None,
        PydanticField(
            default=None,
            description=(
                "Optional target agent. When set, the task runs directly on "
                "that agent; when omitted, the team lead orchestrates execution."
            ),
        ),
    ] = None
    name: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Display name of the autonomous configuration",
            max_length=50,
        ),
    ] = None
    description: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Description of the autonomous configuration",
            max_length=200,
        ),
    ] = None
    cron: Annotated[
        str,
        PydanticField(description="Cron expression for scheduling operations"),
    ]
    prompt: Annotated[
        str,
        PydanticField(
            description="Special prompt used during autonomous operation",
            max_length=20000,
        ),
    ]
    enabled: Annotated[
        bool,
        PydanticField(
            default=True,
            description="Whether the autonomous configuration is enabled",
        ),
    ] = True
    has_memory: Annotated[
        bool,
        PydanticField(
            default=False,
            description=(
                "Whether to retain conversation memory between autonomous runs. "
                "If False, thread memory is cleared before each run."
            ),
        ),
    ] = False
    status: Annotated[
        AutonomousTaskStatus | None,
        PydanticField(
            default=None,
            description="Current execution status for the autonomous task.",
        ),
    ] = None
    next_run_time: Annotated[
        datetime | None,
        PydanticField(
            default=None,
            description="Next scheduled run time for the autonomous task.",
        ),
    ] = None
    created_at: Annotated[
        datetime | None,
        PydanticField(default=None, description="Creation timestamp."),
    ] = None
    updated_at: Annotated[
        datetime | None,
        PydanticField(default=None, description="Last update timestamp."),
    ] = None

    @field_serializer("next_run_time")
    @classmethod
    def serialize_next_run_time(cls, v: datetime | None) -> str | None:
        """Serialize datetime to ISO format string for JSON compatibility."""
        if v is None:
            return None
        return v.isoformat()

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        if not v:
            raise ValueError("id cannot be empty")
        if len(v.encode()) > 20:
            raise ValueError("id must be at most 20 bytes")
        if not re.match(r"^[a-z0-9-]+$", v):
            raise ValueError(
                "id must contain only lowercase letters, numbers, and dashes"
            )
        return v

    def normalize_status_defaults(self) -> "AutonomousTask":
        """Normalize runtime status fields.

        Clears status/next_run_time when the task is disabled, and defaults the
        status to WAITING when the task is enabled but has no status yet.
        """
        updates: dict[str, object] = {}

        if not self.enabled:
            if self.status is not None or self.next_run_time is not None:
                updates["status"] = None
                updates["next_run_time"] = None
        elif self.status is None:
            updates["status"] = AutonomousTaskStatus.WAITING

        if updates:
            return self.model_copy(update=updates)
        return self


class AutonomousTaskTable(Base):
    """Database table for team-owned autonomous tasks."""

    __tablename__: str = "autonomous_tasks"
    __table_args__: Any = (Index("ix_autonomous_tasks_enabled", "enabled"),)

    id: Mapped[str] = mapped_column(
        String(20),
        primary_key=True,
    )
    team_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
        index=True,
        comment="Team that owns this autonomous task",
    )
    target_agent_id: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="Optional agent to run directly; null means lead-orchestrated",
    )
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    cron: Mapped[str] = mapped_column(
        String,
        nullable=False,
        comment="Cron expression for scheduling operations",
    )
    prompt: Mapped[str] = mapped_column(
        String,
        nullable=False,
        comment="Special prompt used during autonomous operation",
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )
    has_memory: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    status: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="Runtime status: waiting/running/error (scheduler-managed)",
    )
    next_run_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Next scheduled run time (scheduler-managed)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
