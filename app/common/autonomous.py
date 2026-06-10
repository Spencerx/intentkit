from pydantic import Field

from intentkit.models.autonomous import AutonomousTask


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
