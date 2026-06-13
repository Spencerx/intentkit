"""Extractors for LangChain message content across provider formats."""

import logging
from typing import Any

from intentkit.models.llm import LLMProvider

logger = logging.getLogger(__name__)


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
