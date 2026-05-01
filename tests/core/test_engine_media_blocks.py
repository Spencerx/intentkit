import base64

import httpx
import pytest

from intentkit.core.engine import (
    _build_image_url_block,
    _build_v1_data_block,
    _fetch_media_bytes,
    _FetchedMedia,
)
from intentkit.models.chat import ChatMessageAttachmentType


def test_image_block_uses_legacy_image_url_shape():
    assert _build_image_url_block("https://cdn.example.com/foo/bar.jpg") == {
        "type": "image_url",
        "image_url": {"url": "https://cdn.example.com/foo/bar.jpg"},
    }


def test_v1_data_block_audio_carries_base64_and_mime():
    fetched = _FetchedMedia(data=b"\x00\x01\x02", mime_type="audio/mpeg")
    block = _build_v1_data_block(ChatMessageAttachmentType.AUDIO, fetched)
    assert block == {
        "type": "audio",
        "base64": base64.b64encode(b"\x00\x01\x02").decode("ascii"),
        "mime_type": "audio/mpeg",
    }


def test_v1_data_block_video_uses_video_type():
    fetched = _FetchedMedia(data=b"raw mp4", mime_type="video/mp4")
    block = _build_v1_data_block(ChatMessageAttachmentType.VIDEO, fetched)
    assert block["type"] == "video"
    assert block["mime_type"] == "video/mp4"
    assert base64.b64decode(block["base64"]) == b"raw mp4"


def test_v1_data_block_file_uses_file_type():
    fetched = _FetchedMedia(data=b"%PDF-1.4 ...", mime_type="application/pdf")
    block = _build_v1_data_block(ChatMessageAttachmentType.FILE, fetched)
    assert block["type"] == "file"
    assert block["mime_type"] == "application/pdf"


@pytest.mark.asyncio
async def test_fetch_media_uses_response_content_type(monkeypatch):
    async def fake_get(self, url):
        request = httpx.Request("GET", url)
        return httpx.Response(
            200,
            content=b"ID3 fake mp3",
            headers={"content-type": "audio/mpeg; charset=binary"},
            request=request,
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    fetched = await _fetch_media_bytes(
        "https://cdn.example.com/voice/abc.mp3",
        ChatMessageAttachmentType.AUDIO,
    )
    assert fetched.data == b"ID3 fake mp3"
    assert fetched.mime_type == "audio/mpeg"


@pytest.mark.asyncio
async def test_fetch_media_falls_back_to_url_extension(monkeypatch):
    async def fake_get(self, url):
        request = httpx.Request("GET", url)
        return httpx.Response(
            200,
            content=b"ID3 fake mp3",
            headers={"content-type": "application/octet-stream"},
            request=request,
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    fetched = await _fetch_media_bytes(
        "https://cdn.example.com/voice/abc.mp3?signed=xyz",
        ChatMessageAttachmentType.AUDIO,
    )
    assert fetched.mime_type == "audio/mpeg"


@pytest.mark.asyncio
async def test_fetch_media_falls_back_to_per_type_default(monkeypatch):
    async def fake_get(self, url):
        request = httpx.Request("GET", url)
        return httpx.Response(
            200,
            content=b"raw",
            headers={},
            request=request,
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    fetched = await _fetch_media_bytes(
        "https://cdn.example.com/voice/no-ext",
        ChatMessageAttachmentType.AUDIO,
    )
    assert fetched.mime_type == "audio/mpeg"

    fetched = await _fetch_media_bytes(
        "https://cdn.example.com/file/no-ext",
        ChatMessageAttachmentType.FILE,
    )
    assert fetched.mime_type == "application/octet-stream"


@pytest.mark.asyncio
async def test_fetch_media_propagates_http_error(monkeypatch):
    async def fake_get(self, url):
        request = httpx.Request("GET", url)
        return httpx.Response(404, content=b"", request=request)

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    with pytest.raises(httpx.HTTPStatusError):
        await _fetch_media_bytes(
            "https://cdn.example.com/missing.mp3",
            ChatMessageAttachmentType.AUDIO,
        )
