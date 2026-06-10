from __future__ import annotations

from datetime import datetime

from epyxid import XID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from intentkit.config.db import get_session
from intentkit.models.agent.db import AgentTable
from intentkit.models.autonomous import (
    AutonomousCreateRequest,
    AutonomousTask,
    AutonomousTaskStatus,
    AutonomousTaskTable,
    AutonomousUpdateRequest,
    validate_cron_schedule,
)
from intentkit.utils.error import IntentKitAPIError


def _task_not_found_error(task_id: str) -> IntentKitAPIError:
    return IntentKitAPIError(
        404,
        "TaskNotFound",
        f"Autonomous task with ID {task_id} not found.",
    )


def _invalid_target_agent_error(agent_id: str) -> IntentKitAPIError:
    return IntentKitAPIError(
        400,
        "InvalidTargetAgent",
        f"Target agent {agent_id} is not an active agent of this team.",
    )


async def _validate_target_agent(
    session: AsyncSession, team_id: str, agent_id: str
) -> None:
    """Ensure the target agent exists, belongs to the team, and is not archived."""
    agent = await session.get(AgentTable, agent_id)
    if agent is None or agent.team_id != team_id or agent.archived_at is not None:
        raise _invalid_target_agent_error(agent_id)


def _to_row(task: AutonomousTask) -> AutonomousTaskTable:
    return AutonomousTaskTable(
        id=task.id,
        team_id=task.team_id,
        target_agent_id=task.target_agent_id,
        created_by=task.created_by,
        name=task.name,
        description=task.description,
        cron=task.cron,
        prompt=task.prompt,
        enabled=task.enabled,
        has_memory=task.has_memory,
        status=task.status.value if task.status else None,
        next_run_time=task.next_run_time,
    )


async def list_team_autonomous_tasks(team_id: str) -> list[AutonomousTask]:
    """List all autonomous tasks owned by a team, oldest first."""
    async with get_session() as session:
        rows = await session.scalars(
            select(AutonomousTaskTable)
            .where(AutonomousTaskTable.team_id == team_id)
            .order_by(AutonomousTaskTable.created_at)
        )
        return [AutonomousTask.model_validate(row) for row in rows]


async def get_autonomous_task(team_id: str, task_id: str) -> AutonomousTask:
    """Get a single autonomous task, verifying it belongs to the team."""
    async with get_session() as session:
        row = await session.get(AutonomousTaskTable, task_id)
        if row is None or row.team_id != team_id:
            raise _task_not_found_error(task_id)
        return AutonomousTask.model_validate(row)


async def add_autonomous_task(
    team_id: str,
    task_request: AutonomousCreateRequest,
    created_by: str | None = None,
) -> AutonomousTask:
    """Create a new autonomous task for a team.

    ``created_by`` is the user the task is attributed to (the authenticated
    caller); it is never taken from the request body.
    """
    validate_cron_schedule(task_request.cron)

    async with get_session() as session:
        if task_request.target_agent_id:
            await _validate_target_agent(session, team_id, task_request.target_agent_id)

        task = AutonomousTask(
            id=str(XID()),
            team_id=team_id,
            target_agent_id=task_request.target_agent_id,
            created_by=created_by,
            cron=task_request.cron,
            prompt=task_request.prompt,
            name=task_request.name,
            description=task_request.description,
            enabled=task_request.enabled,
            has_memory=task_request.has_memory,
        ).normalize_status_defaults()

        row = _to_row(task)
        session.add(row)
        await session.commit()
        # Reload so server-generated created_at/updated_at are returned (and to
        # avoid touching expired attributes after commit).
        await session.refresh(row)
        return AutonomousTask.model_validate(row)


async def update_autonomous_task(
    team_id: str, task_id: str, task_update: AutonomousUpdateRequest
) -> AutonomousTask:
    """Update fields of an existing autonomous task."""
    update_data = task_update.model_dump(exclude_unset=True)

    if update_data.get("cron") is not None:
        validate_cron_schedule(update_data["cron"])

    async with get_session() as session:
        row = await session.get(AutonomousTaskTable, task_id)
        if row is None or row.team_id != team_id:
            raise _task_not_found_error(task_id)

        if update_data.get("target_agent_id"):
            await _validate_target_agent(
                session, team_id, update_data["target_agent_id"]
            )

        merged = (
            AutonomousTask.model_validate(row)
            .model_copy(update=update_data)
            .normalize_status_defaults()
        )

        row.target_agent_id = merged.target_agent_id
        row.name = merged.name
        row.description = merged.description
        row.cron = merged.cron
        row.prompt = merged.prompt
        row.enabled = merged.enabled
        row.has_memory = merged.has_memory
        row.status = merged.status.value if merged.status else None
        row.next_run_time = merged.next_run_time

        await session.commit()
        await session.refresh(row)
        return AutonomousTask.model_validate(row)


async def delete_autonomous_task(team_id: str, task_id: str) -> None:
    """Delete an autonomous task owned by the team."""
    async with get_session() as session:
        row = await session.get(AutonomousTaskTable, task_id)
        if row is None or row.team_id != team_id:
            raise _task_not_found_error(task_id)
        await session.delete(row)
        await session.commit()


async def update_autonomous_task_status(
    team_id: str,
    task_id: str,
    status: AutonomousTaskStatus | None,
    next_run_time: datetime | None,
) -> AutonomousTask:
    """Update only the runtime status/next_run_time of a task (single-row write).

    A disabled task always has its runtime state cleared, regardless of the
    requested status, so callers don't need to special-case it.
    """
    async with get_session() as session:
        row = await session.get(AutonomousTaskTable, task_id)
        if row is None or row.team_id != team_id:
            raise _task_not_found_error(task_id)

        if not row.enabled:
            status = None
            next_run_time = None

        row.status = status.value if status else None
        row.next_run_time = next_run_time
        # Snapshot before commit: expire_on_commit would expire row attributes,
        # and re-reading them after commit triggers an async lazy-load error.
        result = AutonomousTask.model_validate(row)
        await session.commit()
        return result
