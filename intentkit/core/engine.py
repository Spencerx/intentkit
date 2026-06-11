"""AI Agent Management Module.

This module provides functionality for initializing and executing AI agents. It handles:
- Agent initialization with LangChain
- Tool and tool management
- Agent execution and response handling
- Memory management with PostgreSQL
- Integration with CDP and Twitter

The module uses a global cache to store initialized agents for better performance.
"""

# pyright: reportImportCycles=false

import asyncio
import base64
import logging
import mimetypes
import re
import textwrap
import time
import traceback
from typing import Any, NamedTuple

import httpcore
import httpx
from epyxid import XID
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    RemoveMessage,
)
from langchain_core.runnables import RunnableConfig
from langgraph.errors import GraphRecursionError, InvalidUpdateError
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.exc import SQLAlchemyError

from intentkit.abstracts.graph import AgentContext, AgentState
from intentkit.config.config import config
from intentkit.config.db import get_session
from intentkit.core.agent import get_agent
from intentkit.core.budget import check_hourly_budget_exceeded
from intentkit.core.chat import clear_thread_memory
from intentkit.core.credit import expense_message, expense_tool
from intentkit.core.executor import (  # noqa: F401
    agent_executor,
)
from intentkit.models.agent import Agent
from intentkit.models.app_setting import SystemMessageType
from intentkit.models.chat import (
    AuthorType,
    ChatMessage,
    ChatMessageAttachmentType,
    ChatMessageCreate,
    ChatMessageToolCall,
)
from intentkit.models.credit import CreditAccount, OwnerType
from intentkit.models.llm import LLMModelInfo, LLMProvider, calculate_search_cost
from intentkit.models.user import User
from intentkit.tools.base import get_tool_price
from intentkit.utils.error import IntentKitAPIError

logger = logging.getLogger(__name__)

# Attachment types that carry a URL worth forwarding to sub-agents.
_FORWARDABLE_TYPES = frozenset(
    {
        ChatMessageAttachmentType.IMAGE,
        ChatMessageAttachmentType.AUDIO,
        ChatMessageAttachmentType.VIDEO,
        ChatMessageAttachmentType.FILE,
    }
)

# Maps each forwardable attachment type to (model capability flag,
# unsupported-error system message). The CSV's `supports_<type>_input`
# flags are the source of truth; if a model advertises a capability that
# its provider's LangChain adapter cannot actually deliver, the call
# surfaces an internal error and the operator should correct the CSV.
_MEDIA_INPUT_SPECS: list[tuple[ChatMessageAttachmentType, str, SystemMessageType]] = [
    (
        ChatMessageAttachmentType.IMAGE,
        "supports_image_input",
        SystemMessageType.IMAGE_INPUT_NOT_SUPPORTED,
    ),
    (
        ChatMessageAttachmentType.AUDIO,
        "supports_audio_input",
        SystemMessageType.AUDIO_INPUT_NOT_SUPPORTED,
    ),
    (
        ChatMessageAttachmentType.VIDEO,
        "supports_video_input",
        SystemMessageType.VIDEO_INPUT_NOT_SUPPORTED,
    ),
    (
        ChatMessageAttachmentType.FILE,
        "supports_file_input",
        SystemMessageType.FILE_INPUT_NOT_SUPPORTED,
    ),
]

# Per-type fallback when both the HTTP Content-Type and the URL extension
# fail to yield a usable mime. Gemini's inlineData and OpenAI's input_audio
# both reject empty mime/format values, so we always need a concrete value.
_MEDIA_DEFAULT_MIME: dict[ChatMessageAttachmentType, str] = {
    ChatMessageAttachmentType.IMAGE: "image/jpeg",
    ChatMessageAttachmentType.AUDIO: "audio/mpeg",
    ChatMessageAttachmentType.VIDEO: "video/mp4",
    ChatMessageAttachmentType.FILE: "application/octet-stream",
}

# Cap a single fetch — the upload to S3 already bounds attachment size
# upstream. 30 s is well above any expected voice/image/file fetch.
_MEDIA_FETCH_TIMEOUT = 30.0


class _FetchedMedia(NamedTuple):
    data: bytes
    mime_type: str


async def _fetch_media_bytes(
    url: str, atype: ChatMessageAttachmentType
) -> _FetchedMedia:
    """Fetch a media URL and resolve its mime type.

    Order of preference for mime: HTTP Content-Type response header
    (explicit, set by S3 at upload time) → URL path extension via
    `mimetypes` → per-type default.
    """
    async with httpx.AsyncClient(
        timeout=_MEDIA_FETCH_TIMEOUT, follow_redirects=True
    ) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    raw_ct = resp.headers.get("content-type", "")
    mime = raw_ct.split(";", 1)[0].strip().lower()
    if not mime or mime == "application/octet-stream":
        path_only = url.split("?", 1)[0].split("#", 1)[0]
        guessed, _ = mimetypes.guess_type(path_only)
        if guessed:
            mime = guessed
    if not mime:
        mime = _MEDIA_DEFAULT_MIME[atype]
    return _FetchedMedia(data=resp.content, mime_type=mime)


def _build_image_url_block(url: str) -> dict[str, Any]:
    """OpenAI Chat Completions image block — accepted by every adapter."""
    return {"type": "image_url", "image_url": {"url": url}}


def _build_v1_data_block(
    atype: ChatMessageAttachmentType, fetched: _FetchedMedia
) -> dict[str, Any]:
    """LangChain v1 standard multimodal data block with embedded base64.

    This shape is recognized by every provider adapter we use:
      - langchain-google-genai decodes base64 and forwards as Gemini
        ``inlineData(data, mimeType)``
      - langchain-openai converts to ``input_audio`` / ``file`` Chat
        Completions blocks (audio + PDFs only)
      - langchain-anthropic converts ``file`` to ``document`` blocks
        (PDFs only — Anthropic has no audio/video input)
      - langchain-openrouter / langchain-xai inherit OpenAI conversion

    Fetching ourselves and embedding the bytes avoids LangChain's URL fetch
    + mime guessing path, which has produced empty-mimeType errors against
    Gemini in the field.
    """
    return {
        "type": atype.value,
        "base64": base64.b64encode(fetched.data).decode("ascii"),
        "mime_type": fetched.mime_type,
    }


# Cap raw_chunks to prevent unbounded memory growth in super_mode
_MAX_RAW_CHUNKS = 200


def extract_thinking_content(msg: Any) -> str | None:
    """Extract reasoning/thinking content from a LangChain AIMessage.

    Handles multiple provider formats:
    - additional_kwargs["reasoning_content"] (OpenRouter, DeepSeek, xAI) — string
    - additional_kwargs["reasoning"]["summary"] (OpenAI Responses API v0 compat) — dict
    - content list: type="reasoning" with reasoning/summary/text (langchain-core, OpenAI)
    - content list: type="thinking" with thinking field (Anthropic, Google Gemini)
    """
    texts: list[str] = []

    # 1. Check additional_kwargs (OpenRouter, DeepSeek, xAI, OpenAI v0)
    kwargs = getattr(msg, "additional_kwargs", None) or {}
    if isinstance(kwargs, dict):
        # OpenRouter / DeepSeek / xAI: reasoning_content is a string
        rc = kwargs.get("reasoning_content")
        if isinstance(rc, str) and rc:
            texts.append(rc)
        # OpenAI Responses API v0 compat: reasoning is a dict with summary list
        reasoning = kwargs.get("reasoning")
        if isinstance(reasoning, dict):
            for s in reasoning.get("summary", []):
                if isinstance(s, dict) and s.get("text"):
                    texts.append(s["text"])

    # 2. Check content blocks
    content = getattr(msg, "content", None)
    if isinstance(content, list):
        for item in content:
            if not isinstance(item, dict):
                continue
            item_type = item.get("type")
            if item_type == "reasoning":
                # langchain-core standard: text in "reasoning" field
                r = item.get("reasoning")
                if isinstance(r, str) and r:
                    texts.append(r)
                # OpenAI Responses API: summary list
                elif isinstance(item.get("summary"), list):
                    for s in item["summary"]:
                        if isinstance(s, dict) and s.get("text"):
                            texts.append(s["text"])
                # Fallback: direct text field
                elif item.get("text"):
                    texts.append(item["text"])
            elif item_type == "thinking":
                # Anthropic / Google Gemini: text in "thinking" field
                t = item.get("thinking")
                if isinstance(t, str) and t:
                    texts.append(t)

    return "\n\n".join(texts) if texts else None


def extract_text_content(content: object) -> str:
    if isinstance(content, list):
        texts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                t = item.get("text")
                ty = item.get("type")
                if t is not None and (ty == "text" or ty is None):
                    texts.append(t)
            elif isinstance(item, str):
                texts.append(item)
        return "".join(texts)
    if isinstance(content, dict):
        if content.get("type") == "text" and "text" in content:
            return content["text"]
        if "text" in content:
            return content["text"]
        return ""
    if isinstance(content, str):
        return content
    return ""


def extract_cached_input_tokens(msg: Any) -> int:
    """Extract cache_read token count from a LangChain message's usage_metadata."""
    if not hasattr(msg, "usage_metadata") or not msg.usage_metadata:
        return 0
    details = msg.usage_metadata.get("input_token_details")
    if not details:
        return 0
    return details.get("cache_read", 0)


def count_web_searches(msg: Any, provider: LLMProvider) -> int:
    """Count web search calls in the model response by provider."""
    additional = getattr(msg, "additional_kwargs", None) or {}
    response_meta = getattr(msg, "response_metadata", None) or {}

    if provider == LLMProvider.OPENAI:
        return sum(
            1
            for t in additional.get("tool_outputs", [])
            if t.get("type") == "web_search_call"
        )

    if provider == LLMProvider.GOOGLE:
        grounding = (
            additional.get("grounding_metadata")
            or additional.get("groundingMetadata")
            or response_meta.get("grounding_metadata")
            or response_meta.get("groundingMetadata")
        )
        if grounding:
            logger.debug("Google grounding_metadata: %s", grounding)
            queries = grounding.get("web_search_queries")
            if queries is None:
                queries = grounding.get("webSearchQueries")
            return len(queries) if queries else 0
        return 0

    if provider == LLMProvider.XAI:
        tool_usage = response_meta.get("server_side_tool_usage") or additional.get(
            "server_side_tool_usage"
        )
        if tool_usage and isinstance(tool_usage, dict):
            logger.debug("xAI server_side_tool_usage: %s", tool_usage)
            # Known keys: web_search, x_search
            count = 0
            for key, val in tool_usage.items():
                if "search" in key.lower():
                    count += int(val) if isinstance(val, (int, float)) else 0
            return count
        return 0

    # OpenRouter and others: cost bundled in token billing, no separate charge
    return 0


async def stream_agent(message: ChatMessageCreate):
    """
    Stream agent execution results as an async generator.

    This function:
    1. Configures execution context with thread ID
    2. Initializes agent if not in cache
    3. Streams agent execution results
    4. Formats and times the execution steps

    Args:
        message (ChatMessageCreate): The chat message containing agent_id, chat_id, and message content

    Yields:
        ChatMessage: Individual response messages including timing information
    """
    agent = await get_agent(message.agent_id)
    if not agent:
        raise IntentKitAPIError(
            status_code=404, key="AgentNotFound", message="Agent not found"
        )
    executor, cold_start_cost = await agent_executor(message.agent_id)
    message.cold_start_cost = cold_start_cost
    async for chat_message in stream_agent_raw(message, agent, executor):
        yield chat_message


async def _create_system_error_response(
    message_type: SystemMessageType,
    user_message: ChatMessage,
    time_cost: float,
) -> ChatMessage:
    """Create and save a system error/info message.

    This helper consolidates the repeated pattern of creating a
    ``ChatMessageCreate.from_system_message(...)`` and calling ``.save()``.
    """
    error_message_create = await ChatMessageCreate.from_system_message(
        message_type,
        agent_id=user_message.agent_id,
        chat_id=user_message.chat_id,
        user_id=user_message.user_id or "",
        author_id=user_message.agent_id,
        thread_type=user_message.author_type,
        reply_to=user_message.id,
        time_cost=time_cost,
    )
    return await error_message_create.save()


async def _validate_payment(
    user_message: ChatMessage,
    agent: Agent,
    payer: str | None,
    start: float,
) -> ChatMessage | None:
    """Validate payment preconditions.

    Returns ``None`` when validation passes, or a saved ``ChatMessage``
    error that the caller should yield and then return.
    """
    if not payer:
        raise IntentKitAPIError(
            500,
            "PaymentError",
            "Payment is enabled but no team_id available for billing",
        )
    if agent.fee_percentage and agent.fee_percentage > 100:
        owner = await User.get(agent.owner) if agent.owner else None
        if owner and agent.fee_percentage > 100 + owner.nft_count * 10:
            return await _create_system_error_response(
                SystemMessageType.SERVICE_FEE_ERROR,
                user_message,
                time.perf_counter() - start,
            )
    # Fetch team credit account
    team_account = await CreditAccount.get_or_create(OwnerType.TEAM, payer)
    # As long as balance is positive, allow one conversation opportunity.
    # Credit can go negative during the conversation — that is acceptable.
    if team_account.balance <= 0:
        return await _create_system_error_response(
            SystemMessageType.INSUFFICIENT_BALANCE,
            user_message,
            time.perf_counter() - start,
        )
    return None


async def _handle_model_chunk(
    chunk: dict[str, Any],
    user_message: ChatMessage,
    agent: Agent,
    model: LLMModelInfo,
    payer: str | None,
    this_time: float,
    last: float,
    thread_id: str,
    cached_tool_step: Any,
    in_tools_phase: bool,
) -> tuple[list[ChatMessage], float, Any, bool]:
    """Handle a stream chunk that contains ``model`` messages.

    Returns ``(messages_to_yield, updated_last, cached_tool_step, in_tools_phase)``.
    """
    messages_out: list[ChatMessage] = []

    if len(chunk["model"]["messages"]) != 1:
        logger.error(
            "unexpected model message: " + str(chunk["model"]["messages"]),
            extra={"thread_id": thread_id},
        )
    msg = chunk["model"]["messages"][0]
    has_tools = hasattr(msg, "tool_calls") and bool(msg.tool_calls)
    if has_tools:
        in_tools_phase = True
        cached_tool_step = msg
    content = extract_text_content(msg.content) if hasattr(msg, "content") else ""
    thinking = extract_thinking_content(msg)
    # Yield standalone thinking message for tool-call chunks
    if has_tools and thinking:
        thinking_message_create = ChatMessageCreate(
            id=str(XID()),
            agent_id=user_message.agent_id,
            chat_id=user_message.chat_id,
            user_id=user_message.user_id,
            author_id=user_message.agent_id,
            author_type=AuthorType.THINKING,
            model=agent.model,
            thread_type=user_message.author_type,
            reply_to=user_message.id,
            message=thinking,
        )
        thinking_message = await thinking_message_create.save()
        messages_out.append(thinking_message)
    if content and not has_tools:
        usage = getattr(msg, "usage_metadata", None) or {}
        chat_message_create = ChatMessageCreate(
            id=str(XID()),
            agent_id=user_message.agent_id,
            chat_id=user_message.chat_id,
            user_id=user_message.user_id,
            author_id=user_message.agent_id,
            author_type=AuthorType.AGENT,
            model=agent.model,
            thread_type=user_message.author_type,
            reply_to=user_message.id,
            message=content,
            thinking=thinking,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            cached_input_tokens=extract_cached_input_tokens(msg),
            time_cost=this_time - last,
        )
        last = this_time
        async with get_session() as session:
            amount = await model.calculate_cost(
                chat_message_create.input_tokens,
                chat_message_create.output_tokens,
                chat_message_create.cached_input_tokens,
            )

            search_count = count_web_searches(msg, model.provider)
            if search_count > 0:
                search_cost = await calculate_search_cost(model.provider, search_count)
                logger.info(
                    "[%s] Web search: %s calls, provider=%s, cost=%s",
                    user_message.agent_id,
                    search_count,
                    model.provider.value,
                    search_cost,
                )
                amount += search_cost
            credit_event = await expense_message(
                session,
                team_id=payer or "",
                message_id=chat_message_create.id,
                start_message_id=user_message.id,
                base_llm_amount=amount,
                agent=agent,
                user_id=user_message.user_id,
            )
            logger.info("[%s] expense message: %s", user_message.agent_id, amount)
            # Reconciliation: log OpenRouter-reported cost alongside our
            # token-based calculation so discrepancies can be audited.
            or_cost = (getattr(msg, "response_metadata", None) or {}).get("cost")
            if or_cost is not None:
                logger.info(
                    "[%s] openrouter reported cost: %s",
                    user_message.agent_id,
                    or_cost,
                )
            chat_message_create.credit_event_id = credit_event.id
            chat_message_create.credit_cost = credit_event.total_amount
            chat_message = await chat_message_create.save_in_session(session)
            await session.commit()
            messages_out.append(chat_message)

    return messages_out, last, cached_tool_step, in_tools_phase


async def _handle_tools_chunk(
    chunk: dict[str, Any],
    user_message: ChatMessage,
    agent: Agent,
    model: LLMModelInfo,
    payer: str | None,
    this_time: float,
    last: float,
    thread_id: str,
    cached_tool_step: Any,
) -> tuple[list[ChatMessage], float]:
    """Handle a stream chunk that contains ``tools`` messages.

    Returns ``(messages_to_yield, updated_last)``.
    """
    if not cached_tool_step:
        logger.error(
            "unexpected tools message: " + str(chunk["tools"]),
            extra={"thread_id": thread_id},
        )
        return [], last

    tool_calls: list[ChatMessageToolCall] = []
    cached_attachments: list[Any] = []
    have_first_call_in_cache = False  # tool node emit every tool call
    for msg in chunk["tools"]["messages"]:
        if not hasattr(msg, "tool_call_id"):
            logger.error(
                "unexpected tools message: " + str(chunk["tools"]),
                extra={"thread_id": thread_id},
            )
            continue
        for call_index, call in enumerate(cached_tool_step.tool_calls):
            if call["id"] == msg.tool_call_id:
                if call_index == 0:
                    have_first_call_in_cache = True
                tool_call: ChatMessageToolCall = {
                    "id": msg.tool_call_id,
                    "name": call["name"],
                    "parameters": call["args"],
                    "success": True,
                }
                status = getattr(msg, "status", None)
                if status == "error":
                    tool_call["success"] = False
                    tool_call["error_message"] = str(msg.content)
                else:
                    if config.debug:
                        tool_call["response"] = str(msg.content)
                    else:
                        tool_call["response"] = textwrap.shorten(
                            str(msg.content), width=1000, placeholder="..."
                        )
                    artifact = getattr(msg, "artifact", None)
                    if artifact:
                        cached_attachments.extend(artifact)
                tool_calls.append(tool_call)
                break

    tool_usage = getattr(cached_tool_step, "usage_metadata", None) or {}
    tool_message_create = ChatMessageCreate(
        id=str(XID()),
        agent_id=user_message.agent_id,
        chat_id=user_message.chat_id,
        user_id=user_message.user_id,
        author_id=user_message.agent_id,
        author_type=AuthorType.TOOL,
        model=agent.model,
        thread_type=user_message.author_type,
        reply_to=user_message.id,
        message="",
        tool_calls=tool_calls,
        attachments=cached_attachments,
        input_tokens=(
            tool_usage.get("input_tokens", 0) if have_first_call_in_cache else 0
        ),
        output_tokens=(
            tool_usage.get("output_tokens", 0) if have_first_call_in_cache else 0
        ),
        cached_input_tokens=(
            extract_cached_input_tokens(cached_tool_step)
            if have_first_call_in_cache
            else 0
        ),
        time_cost=this_time - last,
    )
    last = this_time
    async with get_session() as session:
        # 1. Message-level credit event (if applicable)
        if have_first_call_in_cache:
            message_amount = await model.calculate_cost(
                tool_message_create.input_tokens,
                tool_message_create.output_tokens,
                tool_message_create.cached_input_tokens,
            )
            message_payment_event = await expense_message(
                session,
                team_id=payer or "",
                message_id=tool_message_create.id,
                start_message_id=user_message.id,
                base_llm_amount=message_amount,
                agent=agent,
                user_id=user_message.user_id,
            )
            tool_message_create.credit_event_id = message_payment_event.id
            tool_message_create.credit_cost = message_payment_event.total_amount
        # 2. Per-tool credit events
        for tool_call in tool_calls:
            if not tool_call["success"]:
                continue
            tool_price = get_tool_price(tool_call["name"])
            payment_event = await expense_tool(
                session,
                team_id=payer or "",
                message_id=tool_message_create.id,
                start_message_id=user_message.id,
                tool_call_id=tool_call.get("id", ""),
                tool_name=tool_call["name"],
                price=tool_price,
                agent=agent,
                user_id=user_message.user_id,
            )
            tool_call["credit_event_id"] = payment_event.id
            tool_call["credit_cost"] = payment_event.total_amount
            logger.info("[%s] tool payment: %s", user_message.agent_id, tool_call)
        # 3. Single insert with all credit info populated
        tool_message_create.tool_calls = tool_calls
        tool_message = await tool_message_create.save_in_session(session)
        await session.commit()
        return [tool_message], last


def _is_unrecoverable_checkpoint_error(exc: Exception) -> bool:
    """Check if an exception indicates unrecoverable checkpoint corruption.

    Only these cases warrant clearing thread memory. Transient errors
    (LLM API failures, network issues, etc.) should preserve conversation history.
    """
    import json
    import pickle
    import struct

    # Checkpoint state machine corruption
    if isinstance(exc, InvalidUpdateError):
        return True

    # Deserialization failure in checkpoint data (pickle, JSON, msgpack paths)
    unrecoverable_types: tuple[type[Exception], ...] = (
        pickle.UnpicklingError,
        struct.error,
        json.JSONDecodeError,
    )
    try:
        import ormsgpack

        unrecoverable_types = (*unrecoverable_types, ormsgpack.MsgpackDecodeError)
    except ImportError:
        pass

    if isinstance(exc, unrecoverable_types):
        return True

    return False


def _summarize_history_messages(msgs: list[Any], max_messages: int = 10) -> list[dict]:
    """Build a compact summary of the last N thread messages.

    Focuses on tool_calls carried on AIMessage — useful when the LLM returns
    MALFORMED_FUNCTION_CALL and the offending call isn't present in the current
    turn's chunks, so we have to look back in checkpoint history.
    """
    summary: list[dict] = []
    for msg in msgs[-max_messages:]:
        entry: dict = {
            "type": type(msg).__name__,
            "id": getattr(msg, "id", None),
        }
        tool_calls = getattr(msg, "tool_calls", None)
        if tool_calls:
            entry["tool_calls"] = [
                {"name": tc.get("name"), "args": tc.get("args")} for tc in tool_calls
            ]
        invalid_tc = getattr(msg, "invalid_tool_calls", None)
        if invalid_tc:
            entry["invalid_tool_calls"] = invalid_tc
        content = getattr(msg, "content", None)
        if content:
            preview = extract_text_content(content) or str(content)
            entry["content_preview"] = preview[:200]
        thinking = extract_thinking_content(msg)
        if thinking:
            entry["thinking_preview"] = thinking[:200]
        response_meta = getattr(msg, "response_metadata", None)
        if response_meta and "finish_reason" in response_meta:
            entry["finish_reason"] = response_meta["finish_reason"]
        summary.append(entry)
    return summary


async def _cleanup_empty_model_output(
    executor: Any,
    stream_config: "RunnableConfig",
    agent_id: str,
    thread_id: str,
) -> list[Any]:
    """Handle checkpoint fallout from a zero-output model turn (e.g. Gemini
    MALFORMED_FUNCTION_CALL).

    Returns the full message list (for diagnostics) and, if the last message
    is an empty AIMessage (no content, no tool_calls), removes it so the next
    user turn doesn't inherit the junk state. Without this the thread keeps
    the empty message and subsequent turns may misbehave.
    """
    try:
        snap = await executor.aget_state(stream_config)
        msgs = snap.values.get("messages") if snap.values else None
    except Exception:
        logger.warning(
            f"Failed to fetch thread state for {agent_id}",
            extra={"thread_id": thread_id},
            exc_info=True,
        )
        return []

    if not msgs:
        return []

    last = msgs[-1]
    # Treat list-content (e.g. thinking-only blocks) as empty when
    # extract_text_content yields nothing — a non-empty list is still truthy
    # so a direct `not last.content` check would miss these.
    if (
        isinstance(last, AIMessage)
        and not extract_text_content(last.content)
        and not last.tool_calls
    ):
        if not last.id:
            logger.warning(
                f"Empty AIMessage has no id; skipping removal for {agent_id}",
                extra={"thread_id": thread_id},
            )
        else:
            try:
                await executor.aupdate_state(
                    stream_config,
                    {"messages": [RemoveMessage(id=last.id)]},
                )
                logger.info(
                    f"Removed empty AIMessage for {agent_id}",
                    extra={"thread_id": thread_id},
                )
            except Exception:
                logger.warning(
                    f"Failed to remove empty AIMessage for {agent_id}",
                    extra={"thread_id": thread_id},
                    exc_info=True,
                )
    return msgs


async def _cancel_cleanup(
    executor: Any,
    stream_config: "RunnableConfig",
    in_tools_phase: bool,
    user_message: "ChatMessageCreate",
    thread_id: str,
    start: float,
) -> None:
    """Run cancel-time DB cleanup, intended to be called inside asyncio.shield()."""
    if in_tools_phase:
        # Cancelled during tool execution — checkpoint has tool_calls without results.
        # Remove the last AIMessage (with tool_calls) to prevent re-execution on next message.
        try:
            snap = await executor.aget_state(stream_config)
            msgs = snap.values.get("messages") if snap.values else None
            if msgs and isinstance(msgs[-1], AIMessage) and msgs[-1].tool_calls:
                await executor.aupdate_state(
                    stream_config,
                    {"messages": [RemoveMessage(id=msgs[-1].id)]},
                )
                logger.info(
                    f"Removed dangling tool_call message for {user_message.agent_id}",
                    extra={"thread_id": thread_id},
                )
            else:
                logger.info(
                    f"No dangling tool_call found for {user_message.agent_id}, skipping cleanup",
                    extra={"thread_id": thread_id},
                )
        except Exception:
            logger.warning(
                f"Failed to remove dangling tool_call message, clearing thread for {user_message.agent_id}",
                extra={"thread_id": thread_id},
                exc_info=True,
            )
    # Save cancellation message directly (stream is already dead, can't yield)
    cancel_message_create = ChatMessageCreate(
        id=str(XID()),
        agent_id=user_message.agent_id,
        chat_id=user_message.chat_id,
        user_id=user_message.user_id,
        author_id=user_message.agent_id,
        author_type=AuthorType.SYSTEM,
        thread_type=user_message.author_type,
        reply_to=user_message.id,
        message="User cancelled the conversation",
        time_cost=time.perf_counter() - start,
    )
    await cancel_message_create.save()


def _build_stream_config(
    user_message: ChatMessage,
    agent: Agent,
    team_id: str | None,
    thread_id: str,
) -> RunnableConfig:
    """Build the LangGraph run config for a chat stream.

    The metadata block is attached by LangSmith tracing to every run in the
    trace, so a shared tracing project can be filtered by environment, agent,
    team, channel, etc.
    """
    # super mode — determined by agent config
    recursion_limit = config.recursion_limit
    if agent.super_mode:
        recursion_limit = max(config.super_recursion_limit, 1000)
    metadata: dict[str, Any] = {
        "env": config.env,
        "agent_id": user_message.agent_id,
        "chat_id": user_message.chat_id,
        "thread_id": thread_id,
        # author_type is already a plain string here (use_enum_values)
        "channel": user_message.author_type,
        "model": agent.model,
    }
    if user_message.user_id:
        metadata["user_id"] = user_message.user_id
    if team_id:
        metadata["team_id"] = team_id
    if agent.team_id:
        metadata["agent_team_id"] = agent.team_id
    if user_message.app_id:
        metadata["app_id"] = user_message.app_id
    return {
        "configurable": {
            "thread_id": thread_id,
        },
        "recursion_limit": recursion_limit,
        "metadata": metadata,
    }


async def stream_agent_raw(
    message: ChatMessageCreate,
    agent: Agent,
    executor: CompiledStateGraph[AgentState, AgentContext, Any, Any],
):
    start = time.perf_counter()
    # make sure reply_to is set
    message.reply_to = message.id

    # save input message first
    user_message = await message.save()

    # temporary debug logging for telegram messages
    if user_message.author_type == AuthorType.TELEGRAM:
        logger.info(
            f"[TELEGRAM DEBUG] Agent: {user_message.agent_id} | Chat: {user_message.chat_id} | Message: {user_message.message}"
        )

    if re.search(
        r"(@clear|/clear)(?!\w)",
        user_message.message.strip(),
        re.IGNORECASE,
    ):
        _ = await clear_thread_memory(user_message.agent_id, user_message.chat_id)

        confirmation_message = ChatMessageCreate(
            id=str(XID()),
            agent_id=user_message.agent_id,
            chat_id=user_message.chat_id,
            user_id=user_message.user_id,
            author_id=user_message.agent_id,
            author_type=AuthorType.AGENT,
            model=agent.model,
            thread_type=user_message.author_type,
            reply_to=user_message.id,
            message="Memory in context has been cleared.",
            time_cost=time.perf_counter() - start,
        )

        yield await confirmation_message.save()
        return

    model = await LLMModelInfo.get(agent.model)

    payment_enabled = config.payment_enabled

    # Determine payer team (needed for credit event recording regardless of payment_enabled)
    # Normal user conversations: user's team pays
    # Platform channels (Telegram/Discord/Twitter/API/X402) and autonomous triggers:
    # agent's team pays
    payer = message.team_id
    if user_message.author_type in [
        AuthorType.TELEGRAM,
        AuthorType.DISCORD,
        AuthorType.TWITTER,
        AuthorType.API,
        AuthorType.X402,
        AuthorType.TRIGGER,
    ]:
        payer = agent.team_id

    budget_status = await check_hourly_budget_exceeded(f"base_llm:{payer}")
    if budget_status.exceeded:
        yield await _create_system_error_response(
            SystemMessageType.HOURLY_BUDGET_EXCEEDED,
            user_message,
            time.perf_counter() - start,
        )
        return

    # check user balance
    if payment_enabled:
        payment_error = await _validate_payment(user_message, agent, payer, start)
        if payment_error is not None:
            yield payment_error
            return

    is_private = False
    if user_message.user_id == agent.owner:
        is_private = True
    # Team-level access: if both team_ids exist and match, treat as private
    # Use original message (not user_message) because team_id is excluded from DB persistence
    if message.team_id and agent.team_id and message.team_id == agent.team_id:
        is_private = True
    # Hack for local mode: treat "system" user as private.
    # This is safe because in authenticated environments,
    # user_id cannot be "system".
    if user_message.user_id == "system":
        is_private = True

    last = start

    # Group media URLs by attachment type and gate each on the model's
    # corresponding supports_<type>_input capability.
    media_urls_by_type: dict[ChatMessageAttachmentType, list[str]] = {
        atype: [] for atype, _, _ in _MEDIA_INPUT_SPECS
    }
    if user_message.attachments:
        for att in user_message.attachments:
            atype = att.get("type")
            url = att.get("url")
            if atype in media_urls_by_type and url is not None:
                media_urls_by_type[atype].append(str(url))

    for atype, capability, error_type in _MEDIA_INPUT_SPECS:
        if not media_urls_by_type[atype]:
            continue
        if not getattr(model, capability):
            yield await _create_system_error_response(
                error_type,
                user_message,
                time.perf_counter() - start,
            )
            return

    input_message = user_message.message

    # Append media attachment URLs as text so the LLM can reference them
    # across turns (e.g. when delegating to sub-agents later).
    if user_message.attachments:
        url_lines = []
        for att in user_message.attachments:
            att_type = att.get("type")
            att_url = att.get("url")
            if att_type in _FORWARDABLE_TYPES and att_url:
                type_label = (
                    att_type.value
                    if isinstance(att_type, ChatMessageAttachmentType)
                    else att_type
                )
                url_lines.append(f"- [{type_label}] {att_url}")
        if url_lines:
            input_message += (
                "\n\n[Attachments in this message"
                " - use these URLs when delegating to other agents]\n"
                + "\n".join(url_lines)
            )

    # content to llm
    messages = [
        HumanMessage(content=input_message),
    ]
    # Image URLs ride straight through as `image_url` blocks; the LangChain
    # adapter handles the fetch. Audio/video/file get fetched here so we
    # can hand Gemini a `media` block with raw bytes + an explicit
    # mime_type, avoiding the empty-mimeType failure mode that the URL-only
    # data block path has produced in production.
    fetch_tasks: list = []
    fetch_meta: list[ChatMessageAttachmentType] = []
    for atype, _, _ in _MEDIA_INPUT_SPECS:
        urls = media_urls_by_type[atype]
        if not urls:
            continue
        logger.info(
            "Passing %d %s url(s) to LLM for agent=%s chat=%s: %s",
            len(urls),
            atype.value,
            user_message.agent_id,
            user_message.chat_id,
            urls,
        )
        if atype == ChatMessageAttachmentType.IMAGE:
            messages.extend(
                HumanMessage(content=[_build_image_url_block(url)]) for url in urls
            )
            continue
        for url in urls:
            fetch_tasks.append(_fetch_media_bytes(url, atype))
            fetch_meta.append(atype)

    if fetch_tasks:
        try:
            fetched_media = await asyncio.gather(*fetch_tasks)
        except Exception:
            logger.exception(
                "Failed to fetch media attachments for agent=%s chat=%s",
                user_message.agent_id,
                user_message.chat_id,
            )
            yield await _create_system_error_response(
                SystemMessageType.AGENT_INTERNAL_ERROR,
                user_message,
                time.perf_counter() - start,
            )
            return
        messages.extend(
            HumanMessage(content=[_build_v1_data_block(atype, fetched)])
            for atype, fetched in zip(fetch_meta, fetched_media, strict=True)
        )

    # stream config
    thread_id = f"{user_message.agent_id}-{user_message.chat_id}"
    stream_config = _build_stream_config(
        user_message, agent, message.team_id, thread_id
    )

    def get_agent_for_context() -> Agent:
        return agent

    context = AgentContext(
        agent_id=user_message.agent_id,
        get_agent=get_agent_for_context,
        chat_id=user_message.chat_id,
        user_id=user_message.user_id,
        team_id=message.team_id,
        app_id=user_message.app_id,
        entrypoint=user_message.author_type,
        is_private=is_private,
        payer=payer if payment_enabled else None,
        start_message_id=user_message.id,
        start_message_attachments=user_message.attachments,
        call_depth=message.call_depth,
    )

    # run
    yielded_any = False
    raw_chunks: list[Any] = []
    cached_tool_step = None
    in_tools_phase = False
    try:
        async for chunk in executor.astream(
            {"messages": messages},
            context=context,
            config=stream_config,
            stream_mode=["updates", "custom"],
            durability="exit",
        ):
            this_time = time.perf_counter()
            logger.debug("stream chunk: %s", chunk, extra={"thread_id": thread_id})
            if len(raw_chunks) < _MAX_RAW_CHUNKS:
                raw_chunks.append(chunk)

            if isinstance(chunk, tuple) and len(chunk) == 2:
                _, payload = chunk
                chunk = payload

            if not isinstance(chunk, dict):
                continue

            if "model" in chunk and "messages" in chunk["model"]:
                (
                    model_msgs,
                    last,
                    cached_tool_step,
                    in_tools_phase,
                ) = await _handle_model_chunk(
                    chunk,
                    user_message,
                    agent,
                    model,
                    payer,
                    this_time,
                    last,
                    thread_id,
                    cached_tool_step,
                    in_tools_phase,
                )
                for m in model_msgs:
                    yielded_any = True
                    yield m
            elif "tools" in chunk and "messages" in chunk["tools"]:
                in_tools_phase = False
                tools_msgs, last = await _handle_tools_chunk(
                    chunk,
                    user_message,
                    agent,
                    model,
                    payer,
                    this_time,
                    last,
                    thread_id,
                    cached_tool_step,
                )
                for m in tools_msgs:
                    yielded_any = True
                    yield m
            else:
                pass
    except asyncio.CancelledError:
        logger.info(
            f"Agent execution cancelled for {user_message.agent_id}",
            extra={"thread_id": thread_id},
        )
        # Shield cleanup DB operations from cancellation propagation.
        # Without shield, awaits inside CancelledError handler also get cancelled,
        # causing SQLAlchemy connection termination errors.
        await asyncio.shield(
            _cancel_cleanup(
                executor,
                stream_config,
                in_tools_phase,
                user_message,
                thread_id,
                start,
            )
        )
        return
    except (httpx.TimeoutException, httpcore.ReadTimeout, asyncio.TimeoutError):
        logger.error(
            f"Agent request timed out for {user_message.agent_id}",
            extra={"thread_id": thread_id},
        )
        yield await _create_system_error_response(
            SystemMessageType.TIMEOUT_ERROR,
            user_message,
            time.perf_counter() - start,
        )
        return
    except SQLAlchemyError as e:
        error_traceback = traceback.format_exc()
        logger.error(
            f"failed to execute agent: {str(e)}\n{error_traceback}",
            extra={"thread_id": thread_id},
        )
        yield await _create_system_error_response(
            SystemMessageType.AGENT_INTERNAL_ERROR,
            user_message,
            time.perf_counter() - start,
        )
        return
    except GraphRecursionError:
        logger.error(
            f"Recursion limit reached for Agent {user_message.agent_id} (Thread: {thread_id}). Sending error message to chat.",
            extra={"thread_id": thread_id, "agent_id": user_message.agent_id},
        )
        yield await _create_system_error_response(
            SystemMessageType.RECURSION_LIMIT_EXCEEDED,
            user_message,
            time.perf_counter() - start,
        )
        return
    except Exception as e:
        error_traceback = traceback.format_exc()
        logger.error(
            f"failed to execute agent: {str(e)}\n{error_traceback}",
            extra={"thread_id": thread_id, "agent_id": user_message.agent_id},
        )
        yield await _create_system_error_response(
            SystemMessageType.AGENT_INTERNAL_ERROR,
            user_message,
            time.perf_counter() - start,
        )
        # Only clear thread memory for known unrecoverable checkpoint corruption,
        # not for transient errors (LLM API failures, network issues, etc.)
        # that should preserve the conversation history.
        if _is_unrecoverable_checkpoint_error(e):
            logger.warning(
                f"Clearing thread memory due to unrecoverable error for {user_message.agent_id}",
                extra={"thread_id": thread_id},
            )
            _ = await clear_thread_memory(user_message.agent_id, user_message.chat_id)
        return

    # If the stream completed normally but yielded zero messages,
    # the LLM likely returned an empty response (no content, no tool calls).
    # Typical cause: Gemini MALFORMED_FUNCTION_CALL — the malformed call isn't
    # in this turn's chunks, so dump recent history tool_calls for diagnosis
    # and prune the empty AIMessage so the thread isn't stuck on next turn.
    if not yielded_any:
        history_msgs = await _cleanup_empty_model_output(
            executor,
            stream_config,
            user_message.agent_id,
            thread_id,
        )
        history_summary = _summarize_history_messages(history_msgs)
        logger.error(
            f"Agent {user_message.agent_id} produced no output messages. "
            f"Total chunks received: {len(raw_chunks)}. "
            f"Raw chunks: {raw_chunks}. "
            f"Recent history ({len(history_summary)} of {len(history_msgs)} msgs): "
            f"{history_summary}",
            extra={"thread_id": thread_id},
        )
        yield await _create_system_error_response(
            SystemMessageType.AGENT_INTERNAL_ERROR,
            user_message,
            time.perf_counter() - start,
        )


async def execute_agent(message: ChatMessageCreate) -> list[ChatMessage]:
    """
    Execute an agent with the given prompt and return response lines.

    This function:
    1. Configures execution context with thread ID
    2. Initializes agent if not in cache
    3. Streams agent execution results
    4. Formats and times the execution steps

    Args:
        message (ChatMessageCreate): The chat message containing agent_id, chat_id, and message content
        debug (bool): Enable debug mode, will save the tool results

    Returns:
        list[ChatMessage]: Formatted response lines including timing information
    """
    resp = []
    async for chat_message in stream_agent(message):
        resp.append(chat_message)
    return resp


async def thread_stats(agent_id: str, chat_id: str) -> list[BaseMessage]:
    thread_id = f"{agent_id}-{chat_id}"
    from langchain_core.runnables import RunnableConfig

    stream_config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    executor, _ = await agent_executor(agent_id)
    snap = await executor.aget_state(stream_config)
    if snap.values and "messages" in snap.values:
        return snap.values["messages"]
    else:
        return []
