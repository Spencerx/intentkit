from pydantic import BaseModel, Field

from intentkit.models.autonomous import AutonomousExecution, AutonomousTask


class AutonomousResponse(AutonomousTask):
    """Response model for an autonomous task with additional computed fields."""

    chat_id: str = Field(
        description="The chat ID associated with this autonomous task",
    )

    @classmethod
    def from_model(cls, model: AutonomousTask) -> "AutonomousResponse":
        """Convert from AutonomousTask model to AutonomousResponse."""
        data = model.model_dump()
        data["chat_id"] = f"autonomous-{model.id}"
        return cls.model_validate(data)


class AutonomousExecutionsResponse(BaseModel):
    """Cursor-paginated list of autonomous task executions."""

    data: list[AutonomousExecution] = Field(
        description="Executions, newest first",
    )
    has_more: bool = Field(
        description="Whether more executions exist beyond this page",
    )
    next_cursor: str | None = Field(
        default=None,
        description="Cursor for the next page (an execution id)",
    )
