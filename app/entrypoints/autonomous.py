import logging

from epyxid import XID

from intentkit.core.agent import get_agent
from intentkit.core.agent_activity import create_agent_activity
from intentkit.core.chat import clear_thread_memory
from intentkit.core.client import execute_agent, execute_lead
from intentkit.models.agent_activity import AgentActivityCreate
from intentkit.models.chat import AuthorType, ChatMessage, ChatMessageCreate

logger = logging.getLogger(__name__)


async def run_autonomous_task(
    team_id: str,
    owner_user_id: str,
    task_id: str,
    prompt: str,
    has_memory: bool = True,
    target_agent_id: str | None = None,
):
    """
    Run a team autonomous task.

    When ``target_agent_id`` is set, the task runs directly on that agent. When
    it is omitted, the task runs through the team lead, which decides delegation
    from the prompt.

    Args:
        team_id: The team that owns the task.
        owner_user_id: The user the run is attributed to (the team owner).
        task_id: The ID of the autonomous task.
        prompt: The autonomous prompt to execute.
        has_memory: Whether to retain conversation memory between runs. If False,
            clears thread memory before execution.
        target_agent_id: Optional agent to run directly; lead-orchestrated if None.
    """
    via = f"agent {target_agent_id}" if target_agent_id else f"lead of team {team_id}"
    logger.info("Running autonomous task %s via %s", task_id, via)

    # The agent the run (and any error activity) is attributed to.
    effective_agent_id = target_agent_id or f"team-{team_id}"
    agent_name: str | None = None
    agent_picture: str | None = None

    try:
        chat_id = f"autonomous-{task_id}"

        # Clear thread memory if has_memory is False
        if not has_memory:
            try:
                _ = await clear_thread_memory(effective_agent_id, chat_id)
                logger.debug(
                    f"Cleared thread memory for task {task_id} (has_memory=False)"
                )
            except Exception as e:
                # Log the error but continue with execution
                logger.warning(
                    "Failed to clear thread memory for task %s: %s", task_id, e
                )

        message = ChatMessageCreate(
            id=str(XID()),
            agent_id=effective_agent_id,
            team_id=team_id,
            chat_id=chat_id,
            user_id=owner_user_id,
            author_id="autonomous",
            author_type=AuthorType.TRIGGER,
            thread_type=AuthorType.TRIGGER,
            message=prompt,
        )

        resp: list[ChatMessage]
        if target_agent_id:
            # Direct execution on the target agent.
            agent = await get_agent(target_agent_id)
            agent_name = agent.name if agent else None
            agent_picture = agent.picture if agent else None
            resp = await execute_agent(message)
        else:
            # Lead-orchestrated execution: the lead reads the prompt and
            # delegates to a team agent via lead_call_agent.
            resp = await execute_lead(team_id, owner_user_id, message)

        # Log the response
        logger.info(
            f"Task {task_id} completed: " + "\n".join(str(m) for m in resp),
            extra={"aid": effective_agent_id},
        )

        # Check response and create error activity if needed
        if not resp:
            try:
                activity = AgentActivityCreate(
                    agent_id=effective_agent_id,
                    agent_name=agent_name,
                    agent_picture=agent_picture,
                    text="Unexpected result: empty response",
                )
                _ = await create_agent_activity(activity)
            except Exception as e:
                logger.warning(
                    f"Failed to create error activity for task {task_id}: {e}",
                    extra={"aid": effective_agent_id},
                )
        else:
            last_msg = resp[-1]
            error_text = None

            if last_msg.author_type == AuthorType.AGENT:
                pass  # Success, do nothing
            elif last_msg.author_type == AuthorType.SYSTEM:
                error_text = f"Task execution error: {last_msg.message}"
            else:
                error_text = "Unexpected return error"

            if error_text:
                try:
                    activity = AgentActivityCreate(
                        agent_id=effective_agent_id,
                        agent_name=agent_name,
                        agent_picture=agent_picture,
                        text=error_text,
                    )
                    _ = await create_agent_activity(activity)
                except Exception as e:
                    logger.warning(
                        f"Failed to create error activity for task {task_id}: {e}",
                        extra={"aid": effective_agent_id},
                    )

    except Exception as e:
        logger.error(
            f"Error in autonomous task {task_id} for team {team_id}: {repr(e)}",
            exc_info=True,
        )
        try:
            activity = AgentActivityCreate(
                agent_id=effective_agent_id,
                agent_name=agent_name,
                agent_picture=agent_picture,
                text=f"Autonomous task exception: {repr(e)}",
            )
            _ = await create_agent_activity(activity)
        except Exception as activity_error:
            logger.warning(
                f"Failed to create exception activity for task {task_id}: {activity_error}",
                extra={"aid": effective_agent_id},
            )
