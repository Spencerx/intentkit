"""Team API autonomous task endpoints."""

import logging

from fastapi import APIRouter, Body, Depends, Path, Response

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
from app.team.auth import verify_team_member

team_autonomous_router = APIRouter()

logger = logging.getLogger(__name__)


@team_autonomous_router.get(
    "/teams/{team_id}/autonomous",
    tags=["Autonomous"],
    operation_id="team_list_autonomous",
    summary="List Autonomous Tasks (Team)",
)
async def list_autonomous(
    auth: tuple[str, str] = Depends(verify_team_member),
) -> list[AutonomousResponse]:
    """List all autonomous tasks of a team."""
    _user_id, team_id = auth
    tasks = await list_team_autonomous_tasks(team_id)
    return [AutonomousResponse.from_model(task) for task in tasks]


@team_autonomous_router.post(
    "/teams/{team_id}/autonomous",
    tags=["Autonomous"],
    status_code=201,
    operation_id="team_add_autonomous",
    summary="Add Autonomous Task (Team)",
)
async def add_autonomous(
    task_request: AutonomousCreateRequest = Body(
        ..., description="Autonomous task configuration"
    ),
    auth: tuple[str, str] = Depends(verify_team_member),
) -> AutonomousResponse:
    """Add a new autonomous task to a team."""
    user_id, team_id = auth
    added_task = await add_autonomous_task(team_id, task_request, created_by=user_id)
    return AutonomousResponse.from_model(added_task)


@team_autonomous_router.patch(
    "/teams/{team_id}/autonomous/{task_id}",
    tags=["Autonomous"],
    operation_id="team_update_autonomous",
    summary="Update Autonomous Task (Team)",
)
async def update_autonomous(
    task_id: str = Path(..., description="Autonomous task ID"),
    task_update: AutonomousUpdateRequest = Body(
        ..., description="Task update configuration"
    ),
    auth: tuple[str, str] = Depends(verify_team_member),
) -> AutonomousResponse:
    """Update a specific autonomous task of a team."""
    _user_id, team_id = auth
    updated_task = await update_autonomous_task(team_id, task_id, task_update)
    return AutonomousResponse.from_model(updated_task)


@team_autonomous_router.delete(
    "/teams/{team_id}/autonomous/{task_id}",
    tags=["Autonomous"],
    status_code=204,
    operation_id="team_delete_autonomous",
    summary="Delete Autonomous Task (Team)",
)
async def delete_autonomous(
    task_id: str = Path(..., description="Autonomous task ID"),
    auth: tuple[str, str] = Depends(verify_team_member),
) -> Response:
    """Delete a specific autonomous task of a team."""
    _user_id, team_id = auth
    await delete_autonomous_task(team_id, task_id)
    return Response(status_code=204)
