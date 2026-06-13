"""Media attachment handling for the chat engine.

Fetches attachment bytes and converts them into the multimodal content
blocks each LangChain provider adapter understands.
"""

import base64
import mimetypes
from typing import Any, NamedTuple

import httpx

from intentkit.models.app_setting import SystemMessageType
from intentkit.models.chat import ChatMessageAttachmentType

# Attachment types that carry a URL worth forwarding to sub-agents.
FORWARDABLE_TYPES = frozenset(
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
MEDIA_INPUT_SPECS: list[tuple[ChatMessageAttachmentType, str, SystemMessageType]] = [
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
MEDIA_DEFAULT_MIME: dict[ChatMessageAttachmentType, str] = {
    ChatMessageAttachmentType.IMAGE: "image/jpeg",
    ChatMessageAttachmentType.AUDIO: "audio/mpeg",
    ChatMessageAttachmentType.VIDEO: "video/mp4",
    ChatMessageAttachmentType.FILE: "application/octet-stream",
}

# Cap a single fetch — the upload to S3 already bounds attachment size
# upstream. 30 s is well above any expected voice/image/file fetch.
MEDIA_FETCH_TIMEOUT = 30.0


class FetchedMedia(NamedTuple):
    data: bytes
    mime_type: str


async def fetch_media_bytes(url: str, atype: ChatMessageAttachmentType) -> FetchedMedia:
    """Fetch a media URL and resolve its mime type.

    Order of preference for mime: HTTP Content-Type response header
    (explicit, set by S3 at upload time) → URL path extension via
    `mimetypes` → per-type default.
    """
    async with httpx.AsyncClient(
        timeout=MEDIA_FETCH_TIMEOUT, follow_redirects=True
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
        mime = MEDIA_DEFAULT_MIME[atype]
    return FetchedMedia(data=resp.content, mime_type=mime)


def build_image_url_block(url: str) -> dict[str, Any]:
    """OpenAI Chat Completions image block — accepted by every adapter."""
    return {"type": "image_url", "image_url": {"url": url}}


def build_v1_data_block(
    atype: ChatMessageAttachmentType, fetched: FetchedMedia
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
