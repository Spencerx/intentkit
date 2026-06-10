import logging

from fastapi import APIRouter, Body, Path, Response

from intentkit.core.autonomous import (
    add_autonomous_task,
    delete_autonomous_task,
    list_team_autonomous_tasks,
    update_autonomous_task,
)
from intentkit.models.autonomous import (
    AutonomousCreateRequest,
    AutonomousUpdateRequest,
)

from app.common.autonomous import AutonomousResponse
from app.local.lead import LEAD_TEAM_ID, LEAD_USER_ID

autonomous_router = APIRouter()

logger = logging.getLogger(__name__)


@autonomous_router.get(
    "/autonomous",
    tags=["Autonomous"],
    operation_id="list_all_autonomous",
    summary="List Autonomous Tasks",
)
async def list_all_autonomous() -> list[AutonomousResponse]:
    """List all autonomous tasks of the team."""
    tasks = await list_team_autonomous_tasks(LEAD_TEAM_ID)
    return [AutonomousResponse.from_model(task) for task in tasks]


@autonomous_router.post(
    "/autonomous",
    tags=["Autonomous"],
    status_code=201,
    operation_id="add_autonomous",
    summary="Add Autonomous Task",
)
async def add_autonomous(
    task_request: AutonomousCreateRequest = Body(
        ..., description="Autonomous task configuration"
    ),
) -> AutonomousResponse:
    """Add a new autonomous task to the team."""
    added_task = await add_autonomous_task(
        LEAD_TEAM_ID, task_request, created_by=LEAD_USER_ID
    )
    return AutonomousResponse.from_model(added_task)


@autonomous_router.patch(
    "/autonomous/{task_id}",
    tags=["Autonomous"],
    operation_id="update_autonomous",
    summary="Update Autonomous Task",
)
async def update_autonomous(
    task_id: str = Path(..., description="ID of the autonomous task"),
    task_update: AutonomousUpdateRequest = Body(
        ..., description="Task update configuration"
    ),
) -> AutonomousResponse:
    """Update a specific autonomous task."""
    updated_task = await update_autonomous_task(LEAD_TEAM_ID, task_id, task_update)
    return AutonomousResponse.from_model(updated_task)


@autonomous_router.delete(
    "/autonomous/{task_id}",
    tags=["Autonomous"],
    status_code=204,
    operation_id="delete_autonomous",
    summary="Delete Autonomous Task",
)
async def delete_autonomous(
    task_id: str = Path(..., description="ID of the autonomous task"),
) -> Response:
    """Delete a specific autonomous task."""
    await delete_autonomous_task(LEAD_TEAM_ID, task_id)
    return Response(status_code=204)
