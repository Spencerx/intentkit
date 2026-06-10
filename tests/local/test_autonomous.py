import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from intentkit.models.autonomous import AutonomousTask, AutonomousTaskStatus

from app.local.autonomous import autonomous_router
from app.local.lead import LEAD_TEAM_ID, LEAD_USER_ID


# Create a test app with the autonomous router
def create_test_app():
    app = FastAPI()
    app.include_router(autonomous_router)
    return app


@pytest.fixture
def client():
    return TestClient(create_test_app())


@pytest.fixture
def mock_task():
    return AutonomousTask(
        id="new-task-id",
        team_id=LEAD_TEAM_ID,
        name="New Task",
        cron="*/5 * * * *",
        prompt="New prompt",
        enabled=True,
        status=AutonomousTaskStatus.WAITING,
        next_run_time=None,
    )


@pytest.mark.asyncio
async def test_list_autonomous(client, monkeypatch):
    import app.local.autonomous as autonomous_module

    async def mock_list(team_id):
        assert team_id == LEAD_TEAM_ID
        return [
            AutonomousTask(
                id="task-1",
                team_id=LEAD_TEAM_ID,
                name="Task 1",
                cron="0 * * * *",
                prompt="Do something",
                enabled=True,
                status=AutonomousTaskStatus.WAITING,
            )
        ]

    monkeypatch.setattr(autonomous_module, "list_team_autonomous_tasks", mock_list)

    response = client.get("/autonomous")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == "task-1"
    assert data[0]["chat_id"] == "autonomous-task-1"


@pytest.mark.asyncio
async def test_add_autonomous(client, mock_task, monkeypatch):
    import app.local.autonomous as autonomous_module

    async def mock_add_autonomous_task(team_id, task_request, created_by=None):
        assert team_id == LEAD_TEAM_ID
        assert created_by == LEAD_USER_ID
        return mock_task

    monkeypatch.setattr(
        autonomous_module, "add_autonomous_task", mock_add_autonomous_task
    )

    payload = {
        "name": "New Task",
        "cron": "*/5 * * * *",
        "prompt": "New prompt",
        "enabled": True,
        "target_agent_id": "agent-x",
    }

    response = client.post("/autonomous", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "New Task"
    assert data["cron"] == "*/5 * * * *"
    assert data["chat_id"].startswith("autonomous-")


@pytest.mark.asyncio
async def test_update_autonomous(client, monkeypatch):
    import app.local.autonomous as autonomous_module

    updated_task = AutonomousTask(
        id="task-1",
        team_id=LEAD_TEAM_ID,
        name="Updated Task",
        cron="0 * * * *",
        prompt="Do something",
        enabled=False,
        status=None,
        next_run_time=None,
    )

    async def mock_update_autonomous_task(team_id, task_id, task_update):
        assert team_id == LEAD_TEAM_ID
        return updated_task

    monkeypatch.setattr(
        autonomous_module, "update_autonomous_task", mock_update_autonomous_task
    )

    payload = {"name": "Updated Task", "enabled": False}

    response = client.patch("/autonomous/task-1", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "task-1"
    assert data["name"] == "Updated Task"
    assert data["enabled"] is False


@pytest.mark.asyncio
async def test_delete_autonomous(client, monkeypatch):
    import app.local.autonomous as autonomous_module

    async def mock_delete_autonomous_task(team_id, task_id):
        assert team_id == LEAD_TEAM_ID

    monkeypatch.setattr(
        autonomous_module, "delete_autonomous_task", mock_delete_autonomous_task
    )

    response = client.delete("/autonomous/task-1")
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_update_autonomous_status_uses_core_update(monkeypatch):
    import app.autonomous as autonomous_module

    called = {"value": False}

    async def mock_update_autonomous_task_status(
        team_id, task_id, status, next_run_time
    ):
        called["value"] = True

    class MockJob:
        def __init__(self):
            self.id = "team-1-task-1"
            self.args = ["team-1", "user", "task-1", "prompt", True, None]
            self.next_run_time = None

    monkeypatch.setattr(
        autonomous_module,
        "update_autonomous_task_status",
        mock_update_autonomous_task_status,
    )
    monkeypatch.setattr(
        autonomous_module.scheduler, "get_job", lambda _job_id: MockJob()
    )

    await autonomous_module.update_autonomous_status(
        "team-1-task-1", AutonomousTaskStatus.RUNNING
    )

    assert called["value"] is True
