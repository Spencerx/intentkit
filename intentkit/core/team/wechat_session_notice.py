"""Build the synthesized prompt sent to the lead agent when the wechat
24-hour reply window is about to close.

The Go integration's per-team timer fires this through the
``/core/lead/stream`` endpoint with ``system_trigger='wechat_session_expiring'``.
The lead agent receives the prompt as a TRIGGER-author message, generates a
heads-up message for the user, and the response is dispatched back over
wechat by the existing sender path while the window is still open.
"""

from __future__ import annotations

import logging

from intentkit.core.autonomous import list_team_autonomous_tasks
from intentkit.core.lead.service import get_team_agents

logger = logging.getLogger(__name__)


# Trigger value shared with integrations/wechat/bot/session_timer.go
# (SessionTriggerExpiring). Keep aligned.
WECHAT_SESSION_EXPIRING = "wechat_session_expiring"


async def _build_team_status_block(team_id: str) -> str:
    """Return a compact, human-readable summary of the team's agents and the
    team's currently enabled autonomous tasks. Best-effort: failures are
    swallowed and reflected as a placeholder line so the notice still goes
    out even if status collection breaks."""
    try:
        agents = await get_team_agents(team_id)
    except Exception:
        logger.warning(
            "wechat session notice: failed to list team agents", exc_info=True
        )
        return "（暂无法获取 agent 状态）"

    try:
        tasks = await list_team_autonomous_tasks(team_id)
    except Exception:
        logger.warning(
            "wechat session notice: failed to list autonomous tasks for team %s",
            team_id,
            exc_info=True,
        )
        tasks = []

    lines: list[str] = []
    if agents:
        lines.append("团队 agent：" + "、".join(a.name or a.id for a in agents))
    else:
        lines.append("团队当前没有部署任何 agent。")

    enabled_tasks = [t for t in tasks if t.enabled]
    if enabled_tasks:
        task_summaries = [f"{t.name or t.id}（cron={t.cron}）" for t in enabled_tasks]
        lines.append(
            f"进行中的自动任务 {len(enabled_tasks)} 个 — " + "；".join(task_summaries)
        )
    else:
        lines.append("暂无启用中的自动任务。")

    return "\n".join(lines)


async def build_expiring_prompt(team_id: str) -> str:
    """Build the synthesized user-facing prompt for the lead agent."""
    status_block = await _build_team_status_block(team_id)
    return (
        "系统事件：用户在微信上即将达到 24 小时未与你互动的时间窗口，"
        "再过 30 分钟左右我将无法主动给 ta 发消息。"
        "请直接以你自己的口吻给用户写一条微信消息，做到：\n"
        "1) 简明告知微信对主动消息有 1 天的时间限制，即将到期；\n"
        "2) 提示如果想继续接收推送，回复任意消息或交付一个新任务即可；\n"
        "3) 顺带把当前每个 agent 的状态和未完成任务概要带上。\n\n"
        "回复直接就是发给用户的文本，不要再加引导语、问候或 markdown。\n\n"
        "当前团队状态如下：\n"
        f"{status_block}"
    )
