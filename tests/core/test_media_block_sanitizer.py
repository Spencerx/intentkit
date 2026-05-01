from typing import Any
from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from intentkit.core.middleware import MediaBlockSanitizerMiddleware


class _StubRequest:
    def __init__(self, messages: list[Any]) -> None:
        self.messages = messages
        self.last_override: dict[str, Any] | None = None

    def override(self, **kwargs: Any) -> "_StubRequest":
        self.last_override = kwargs
        if "messages" in kwargs:
            self.messages = kwargs["messages"]
        return self


@pytest.mark.asyncio
async def test_repairs_audio_block_with_mp3_extension() -> None:
    request = _StubRequest(
        messages=[
            HumanMessage(
                content=[
                    {"type": "text", "text": "what's in this audio?"},
                    {"type": "audio", "url": "https://cdn.example.com/voice/abc.mp3"},
                ]
            )
        ]
    )
    handler = AsyncMock(return_value="ok")

    result = await MediaBlockSanitizerMiddleware().awrap_model_call(request, handler)  # pyright: ignore[reportArgumentType]

    assert result == "ok"
    handler.assert_awaited_once()
    patched_msg = request.messages[0]
    assert isinstance(patched_msg, HumanMessage)
    assert isinstance(patched_msg.content, list)
    media = patched_msg.content[1]
    assert isinstance(media, dict)
    assert media["mime_type"] == "audio/mpeg"
    assert media["url"] == "https://cdn.example.com/voice/abc.mp3"


@pytest.mark.asyncio
async def test_strips_query_string_before_extension_lookup() -> None:
    request = _StubRequest(
        messages=[
            HumanMessage(
                content=[
                    {
                        "type": "video",
                        "url": "https://cdn.example.com/clips/foo.mp4?signed=xyz",
                    }
                ]
            )
        ]
    )
    handler = AsyncMock(return_value="ok")

    await MediaBlockSanitizerMiddleware().awrap_model_call(request, handler)  # pyright: ignore[reportArgumentType]

    block = request.messages[0].content[0]
    assert block["mime_type"] == "video/mp4"


@pytest.mark.asyncio
async def test_drops_file_block_when_mime_unresolvable() -> None:
    request = _StubRequest(
        messages=[
            HumanMessage(
                content=[
                    {"type": "text", "text": "describe this"},
                    {"type": "file", "url": "https://cdn.example.com/voice/raw.silk"},
                ]
            )
        ]
    )
    handler = AsyncMock(return_value="ok")

    await MediaBlockSanitizerMiddleware().awrap_model_call(request, handler)  # pyright: ignore[reportArgumentType]

    msg = request.messages[0]
    assert isinstance(msg.content, list)
    assert len(msg.content) == 1
    assert msg.content[0]["type"] == "text"


@pytest.mark.asyncio
async def test_uses_per_type_default_when_extension_missing() -> None:
    request = _StubRequest(
        messages=[
            HumanMessage(
                content=[
                    {"type": "audio", "url": "https://cdn.example.com/voice/no-ext"}
                ]
            )
        ]
    )
    handler = AsyncMock(return_value="ok")

    await MediaBlockSanitizerMiddleware().awrap_model_call(request, handler)  # pyright: ignore[reportArgumentType]

    block = request.messages[0].content[0]
    assert block["mime_type"] == "audio/mpeg"


@pytest.mark.asyncio
async def test_passes_through_blocks_with_mime_type() -> None:
    msg = HumanMessage(
        content=[
            {"type": "audio", "base64": "ZmFrZQ==", "mime_type": "audio/wav"},
        ]
    )
    request = _StubRequest(messages=[msg])
    handler = AsyncMock(return_value="ok")

    await MediaBlockSanitizerMiddleware().awrap_model_call(request, handler)  # pyright: ignore[reportArgumentType]

    # No modification: message identity preserved, override not called.
    assert request.messages[0] is msg
    assert request.last_override is None


@pytest.mark.asyncio
async def test_replaces_emptied_content_with_empty_string() -> None:
    request = _StubRequest(
        messages=[
            HumanMessage(
                content=[{"type": "file", "url": "https://cdn.example.com/x.silk"}]
            )
        ]
    )
    handler = AsyncMock(return_value="ok")

    await MediaBlockSanitizerMiddleware().awrap_model_call(request, handler)  # pyright: ignore[reportArgumentType]

    assert request.messages[0].content == ""


@pytest.mark.asyncio
async def test_skips_ai_messages() -> None:
    ai = AIMessage(
        content=[
            {"type": "audio", "url": "https://cdn.example.com/no-ext"},
        ]
    )
    request = _StubRequest(messages=[ai])
    handler = AsyncMock(return_value="ok")

    await MediaBlockSanitizerMiddleware().awrap_model_call(request, handler)  # pyright: ignore[reportArgumentType]

    assert request.messages[0] is ai
    assert request.last_override is None


@pytest.mark.asyncio
async def test_handles_string_content_unchanged() -> None:
    msg = HumanMessage(content="just text")
    request = _StubRequest(messages=[msg])
    handler = AsyncMock(return_value="ok")

    await MediaBlockSanitizerMiddleware().awrap_model_call(request, handler)  # pyright: ignore[reportArgumentType]

    assert request.messages[0] is msg
    assert request.last_override is None


@pytest.mark.asyncio
async def test_drops_file_block_when_extension_resolves_to_octet_stream() -> None:
    request = _StubRequest(
        messages=[
            HumanMessage(
                content=[
                    {"type": "text", "text": "describe this"},
                    {"type": "file", "url": "https://cdn.example.com/blob/payload.bin"},
                ]
            )
        ]
    )
    handler = AsyncMock(return_value="ok")

    await MediaBlockSanitizerMiddleware().awrap_model_call(request, handler)  # pyright: ignore[reportArgumentType]

    msg = request.messages[0]
    assert isinstance(msg.content, list)
    assert len(msg.content) == 1
    assert msg.content[0]["type"] == "text"


@pytest.mark.asyncio
async def test_repairs_image_block_with_jpg_extension() -> None:
    request = _StubRequest(
        messages=[
            HumanMessage(
                content=[
                    {"type": "image", "url": "https://cdn.example.com/photos/cat.jpg"}
                ]
            )
        ]
    )
    handler = AsyncMock(return_value="ok")

    await MediaBlockSanitizerMiddleware().awrap_model_call(request, handler)  # pyright: ignore[reportArgumentType]

    block = request.messages[0].content[0]
    assert block["mime_type"] == "image/jpeg"
