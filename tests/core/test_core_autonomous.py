"""Unit tests for the team-scoped autonomous core service."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from intentkit.core.autonomous import (
    add_autonomous_task,
    delete_autonomous_task,
    list_team_autonomous_tasks,
    update_autonomous_task,
    update_autonomous_task_status,
)
from intentkit.models.autonomous import (
    AutonomousCreateRequest,
    AutonomousTaskStatus,
    AutonomousUpdateRequest,
)
from intentkit.utils.error import IntentKitAPIError


def _fake_row(**overrides):
    base = dict(
        id="task-1",
        team_id="team-1",
        target_agent_id=None,
        created_by=None,
        name=None,
        description=None,
        cron="*/5 * * * *",
        prompt="p",
        enabled=True,
        has_memory=False,
        status="waiting",
        next_run_time=None,
        created_at=None,
        updated_at=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _patch_session():
    """Return (patcher, mock_session) wiring get_session as an async context manager."""
    patcher = patch("intentkit.core.autonomous.get_session")
    mock_get_session = patcher.start()
    mock_session = MagicMock()
    mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)
    mock_session.add = MagicMock()
    mock_session.delete = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()
    return patcher, mock_session


@pytest.mark.asyncio
async def test_add_task_belongs_to_team():
    patcher, session = _patch_session()
    try:
        req = AutonomousCreateRequest(cron="*/5 * * * *", prompt="do work")
        result = await add_autonomous_task("team-1", req)

        assert result.team_id == "team-1"
        assert result.target_agent_id is None
        assert result.status == AutonomousTaskStatus.WAITING
        assert result.id
        session.add.assert_called_once()
        # The created row carries the caller's id (here: none).
        assert session.add.call_args.args[0].created_by is None
        session.commit.assert_called_once()
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_add_task_records_creator():
    patcher, session = _patch_session()
    try:
        req = AutonomousCreateRequest(cron="*/5 * * * *", prompt="do work")
        result = await add_autonomous_task("team-1", req, created_by="user-42")
        assert result.created_by == "user-42"
        assert session.add.call_args.args[0].created_by == "user-42"
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_add_task_rejects_invalid_cron():
    # Validation happens before any DB work.
    with pytest.raises(IntentKitAPIError):
        await add_autonomous_task(
            "team-1", AutonomousCreateRequest(cron="* * * * *", prompt="p")
        )


@pytest.mark.asyncio
async def test_add_task_rejects_target_agent_not_in_team():
    patcher, session = _patch_session()
    try:
        # Agent lookup returns None -> not in team.
        session.get = AsyncMock(return_value=None)
        with pytest.raises(IntentKitAPIError):
            await add_autonomous_task(
                "team-1",
                AutonomousCreateRequest(
                    cron="*/5 * * * *", prompt="p", target_agent_id="agent-x"
                ),
            )
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_add_task_accepts_target_agent_in_team():
    patcher, session = _patch_session()
    try:
        session.get = AsyncMock(
            return_value=SimpleNamespace(
                id="agent-x", team_id="team-1", archived_at=None
            )
        )
        result = await add_autonomous_task(
            "team-1",
            AutonomousCreateRequest(
                cron="*/5 * * * *", prompt="p", target_agent_id="agent-x"
            ),
        )
        assert result.target_agent_id == "agent-x"
        session.add.assert_called_once()
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_update_task_not_found_raises():
    patcher, session = _patch_session()
    try:
        session.get = AsyncMock(return_value=None)
        with pytest.raises(IntentKitAPIError):
            await update_autonomous_task(
                "team-1", "task-1", AutonomousUpdateRequest(prompt="new")
            )
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_update_task_rejects_foreign_team():
    patcher, session = _patch_session()
    try:
        session.get = AsyncMock(return_value=_fake_row(team_id="other-team"))
        with pytest.raises(IntentKitAPIError):
            await update_autonomous_task(
                "team-1", "task-1", AutonomousUpdateRequest(prompt="new")
            )
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_update_task_applies_partial_change():
    patcher, session = _patch_session()
    try:
        row = _fake_row(team_id="team-1", prompt="old")
        session.get = AsyncMock(return_value=row)
        result = await update_autonomous_task(
            "team-1", "task-1", AutonomousUpdateRequest(prompt="new")
        )
        assert result.prompt == "new"
        assert row.prompt == "new"
        session.commit.assert_called_once()
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_update_unpins_target_agent():
    patcher, session = _patch_session()
    try:
        row = _fake_row(team_id="team-1", target_agent_id="agent-x")
        session.get = AsyncMock(return_value=row)
        # Explicit None must clear the pinned agent (un-pin → lead-orchestrated).
        result = await update_autonomous_task(
            "team-1", "task-1", AutonomousUpdateRequest(target_agent_id=None)
        )
        assert row.target_agent_id is None
        assert result.target_agent_id is None
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_delete_task():
    patcher, session = _patch_session()
    try:
        row = _fake_row(team_id="team-1")
        session.get = AsyncMock(return_value=row)
        await delete_autonomous_task("team-1", "task-1")
        session.delete.assert_awaited_once_with(row)
        session.commit.assert_called_once()
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_update_status_single_row():
    patcher, session = _patch_session()
    try:
        row = _fake_row(team_id="team-1")
        session.get = AsyncMock(return_value=row)
        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        result = await update_autonomous_task_status(
            "team-1", "task-1", AutonomousTaskStatus.RUNNING, ts
        )
        assert row.status == "running"
        assert row.next_run_time == ts
        assert result.status == AutonomousTaskStatus.RUNNING
        session.commit.assert_called_once()
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_list_team_tasks_maps_rows():
    patcher, session = _patch_session()
    try:
        session.scalars = AsyncMock(return_value=[_fake_row(id="a"), _fake_row(id="b")])
        tasks = await list_team_autonomous_tasks("team-1")
        assert [t.id for t in tasks] == ["a", "b"]
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_update_status_clears_when_disabled():
    patcher, session = _patch_session()
    try:
        row = _fake_row(team_id="team-1", enabled=False)
        session.get = AsyncMock(return_value=row)
        result = await update_autonomous_task_status(
            "team-1", "task-1", AutonomousTaskStatus.RUNNING, None
        )
        # Disabled tasks always have runtime state cleared.
        assert row.status is None
        assert result.status is None
    finally:
        patcher.stop()
