from intentkit.core.engine import (
    _build_media_content_block,
    _guess_media_mime_type,
)
from intentkit.models.chat import ChatMessageAttachmentType


def test_image_block_uses_legacy_image_url_shape():
    block = _build_media_content_block(
        ChatMessageAttachmentType.IMAGE,
        "https://cdn.example.com/foo/bar.jpg",
    )
    assert block == {
        "type": "image_url",
        "image_url": {"url": "https://cdn.example.com/foo/bar.jpg"},
    }


def test_audio_block_includes_source_type_and_mime():
    block = _build_media_content_block(
        ChatMessageAttachmentType.AUDIO,
        "https://cdn.example.com/voice/123.mp3",
    )
    assert block == {
        "type": "audio",
        "source_type": "url",
        "url": "https://cdn.example.com/voice/123.mp3",
        "mime_type": "audio/mpeg",
    }


def test_video_block_includes_source_type_and_mime():
    block = _build_media_content_block(
        ChatMessageAttachmentType.VIDEO,
        "https://cdn.example.com/clip/abc.mp4",
    )
    assert block["type"] == "video"
    assert block["source_type"] == "url"
    assert block["mime_type"] == "video/mp4"


def test_file_block_falls_back_to_octet_stream():
    block = _build_media_content_block(
        ChatMessageAttachmentType.FILE,
        "https://cdn.example.com/file/no-ext",
    )
    assert block["mime_type"] == "application/octet-stream"


def test_guess_mime_strips_query_string():
    mime = _guess_media_mime_type(
        ChatMessageAttachmentType.AUDIO,
        "https://cdn.example.com/voice/123.mp3?signed=abc&exp=999",
    )
    assert mime == "audio/mpeg"


def test_guess_mime_unknown_extension_uses_default():
    mime = _guess_media_mime_type(
        ChatMessageAttachmentType.AUDIO,
        "https://cdn.example.com/voice/123",
    )
    assert mime == "audio/mpeg"
