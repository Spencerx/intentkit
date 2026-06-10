"""Tests for the autonomous task runner's execution branching."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from intentkit.models.chat import AuthorType

MODULE = "app.entrypoints.autonomous"


def _ok_response():
    return [SimpleNamespace(author_type=AuthorType.AGENT, message="done")]


@pytest.mark.asyncio
async def test_runner_direct_path_when_target_agent_set():
    from app.entrypoints.autonomous import run_autonomous_task

    with (
        patch(f"{MODULE}.clear_thread_memory", new=AsyncMock()),
        patch(f"{MODULE}.create_agent_activity", new=AsyncMock()),
        patch(
            f"{MODULE}.get_agent",
            new=AsyncMock(return_value=SimpleNamespace(name="A", picture=None)),
        ),
        patch(
            f"{MODULE}.execute_agent", new=AsyncMock(return_value=_ok_response())
        ) as ea,
        patch(
            f"{MODULE}.execute_lead", new=AsyncMock(return_value=_ok_response())
        ) as el,
    ):
        await run_autonomous_task(
            team_id="team-1",
            owner_user_id="user-1",
            task_id="task-1",
            prompt="do it",
            has_memory=True,
            target_agent_id="agent-x",
        )

        ea.assert_awaited_once()
        el.assert_not_awaited()
        # The direct message targets the agent itself.
        call = ea.await_args
        assert call is not None
        sent = call.args[0]
        assert sent.agent_id == "agent-x"


@pytest.mark.asyncio
async def test_runner_lead_path_when_no_target_agent():
    from app.entrypoints.autonomous import run_autonomous_task

    with (
        patch(f"{MODULE}.clear_thread_memory", new=AsyncMock()),
        patch(f"{MODULE}.create_agent_activity", new=AsyncMock()),
        patch(f"{MODULE}.get_agent", new=AsyncMock()),
        patch(
            f"{MODULE}.execute_agent", new=AsyncMock(return_value=_ok_response())
        ) as ea,
        patch(
            f"{MODULE}.execute_lead", new=AsyncMock(return_value=_ok_response())
        ) as el,
    ):
        await run_autonomous_task(
            team_id="team-1",
            owner_user_id="user-1",
            task_id="task-1",
            prompt="do it",
            has_memory=False,
            target_agent_id=None,
        )

        ea.assert_not_awaited()
        el.assert_awaited_once()
        call = el.await_args
        assert call is not None
        assert call.args[0] == "team-1"
        assert call.args[1] == "user-1"
        # The lead message is attributed to the synthetic team lead agent.
        sent = call.args[2]
        assert sent.agent_id == "team-team-1"
