"""PDF generation utilities for post content."""

from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi.responses import Response

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_POST_TEMPLATE = (_TEMPLATE_DIR / "post_pdf.html").read_text()

_MD_EXTENSIONS = [
    "fenced_code",
    "tables",
    "codehilite",
    "pymdownx.tasklist",
]

_MD_EXTENSION_CONFIGS = {
    "codehilite": {
        "css_class": "codehilite",
        "guess_lang": False,
    },
    "pymdownx.tasklist": {
        "custom_checkbox": True,
    },
}

_FOR_PATTERN = re.compile(
    r"\{%\s*for\s+(\w+)\s+in\s+(\w+)\s*%\}(.*?)\{%\s*endfor\s*%\}",
    re.DOTALL,
)
_IF_PATTERN = re.compile(
    r"\{%\s*if\s+(\w+)\s*%\}(.*?)\{%\s*endif\s*%\}",
    re.DOTALL,
)
_VAR_PATTERN = re.compile(r"\{\{\s*(\w+)\s*\}\}")

# Variables that contain pre-rendered HTML and should not be escaped
_RAW_VARS = {"content"}

# Allowed URL schemes for image fetching (blocks file://, data:, etc.)
_ALLOWED_SCHEMES = {"http", "https"}

# Empty stand-in returned for any blocked resource so rendering still succeeds.
_BLOCKED_RESOURCE = {"string": b"", "mime_type": "image/png"}


def _is_disallowed_address(hostname: str) -> bool:
    """Return True if the hostname resolves to a non-public IP (SSRF guard).

    Blocks loopback, private, link-local, reserved, multicast, and unspecified
    ranges (e.g. 127.0.0.1, 10.0.0.0/8, 169.254.169.254) so server-side asset
    fetching cannot reach internal services. Fails closed: a host that cannot be
    resolved is treated as disallowed.
    """
    try:
        infos = socket.getaddrinfo(hostname, None)
    except (socket.gaierror, UnicodeError, ValueError):
        return True

    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            return True
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return True
    return False


def _safe_url_fetcher(url: str, timeout: int = 10, ssl_context: Any = None) -> Any:
    """URL fetcher for WeasyPrint that blocks non-HTTP schemes and non-public
    hosts (SSRF prevention).

    The host is resolved and rejected if it maps to a private/internal address.
    This is the requested host only; it does not follow redirects, so a public
    host that 3xx-redirects to an internal one is not covered here and should be
    constrained at the network egress layer.
    """
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        return _BLOCKED_RESOURCE
    if not parsed.hostname or _is_disallowed_address(parsed.hostname):
        return _BLOCKED_RESOURCE

    from weasyprint import default_url_fetcher

    return default_url_fetcher(url, timeout=timeout, ssl_context=ssl_context)


def _resolve_image_url(url: str | None, cdn_base: str | None) -> str:
    """Resolve a potentially relative image URL to an absolute URL."""
    if not url:
        return ""
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if cdn_base:
        base = cdn_base.rstrip("/")
        rel = url.lstrip("/")
        return f"{base}/{rel}"
    return url


def _render_template(template: str, **kwargs: object) -> str:
    """Simple template rendering with {{ var }}, {% if %}, {% for %} support."""
    result = template

    for match in _FOR_PATTERN.finditer(result):
        var_name = match.group(1)
        list_name = match.group(2)
        body = match.group(3)
        items = kwargs.get(list_name, [])
        rendered = ""
        if items and hasattr(items, "__iter__"):
            for item in items:  # pyright: ignore[reportGeneralTypeIssues]
                rendered += body.replace("{{ " + var_name + " }}", escape(str(item)))
        result = result.replace(match.group(0), rendered, 1)

    for match in _IF_PATTERN.finditer(result):
        var_name = match.group(1)
        body = match.group(2)
        value = kwargs.get(var_name)
        if value:
            result = result.replace(match.group(0), body, 1)
        else:
            result = result.replace(match.group(0), "", 1)

    for match in _VAR_PATTERN.finditer(result):
        var_name = match.group(1)
        value = kwargs.get(var_name, "")
        safe_value = str(value) if var_name in _RAW_VARS else escape(str(value))
        result = result.replace(match.group(0), safe_value, 1)

    return result


def _generate_pdf(
    title: str,
    markdown_content: str,
    agent_name: str,
    created_at: datetime,
    tags: list[str] | None = None,
    cover: str | None = None,
    cdn_base: str | None = None,
) -> bytes:
    """Convert post content to a styled PDF. Runs synchronously (CPU-bound)."""
    import markdown as md
    from weasyprint import HTML

    html_body = md.markdown(
        markdown_content,
        extensions=_MD_EXTENSIONS,
        extension_configs=_MD_EXTENSION_CONFIGS,
    )

    date_str = created_at.strftime("%B %d, %Y")
    resolved_cover = _resolve_image_url(cover, cdn_base)

    full_html = _render_template(
        _POST_TEMPLATE,
        title=title,
        content=html_body,
        agent_name=agent_name,
        date=date_str,
        tags=tags or [],
        cover=resolved_cover,
    )

    result = HTML(string=full_html, url_fetcher=_safe_url_fetcher).write_pdf()
    if result is None:
        raise RuntimeError("WeasyPrint failed to generate PDF")
    return result


async def generate_post_pdf(
    title: str,
    markdown_content: str,
    agent_name: str,
    created_at: datetime,
    tags: list[str] | None = None,
    cover: str | None = None,
    cdn_base: str | None = None,
) -> bytes:
    """Convert post content to a styled PDF asynchronously.

    Wraps the CPU-bound WeasyPrint rendering in a thread to avoid
    blocking the event loop.
    """
    return await asyncio.to_thread(
        _generate_pdf,
        title,
        markdown_content,
        agent_name,
        created_at,
        tags,
        cover,
        cdn_base,
    )


async def post_pdf_response(
    post: Any,
    filename: str | None = None,
    cdn_base: str | None = None,
) -> Response:
    """Generate a PDF from a post record and return it as a download Response.

    Accepts any object with title, markdown, agent_name, created_at, tags,
    cover, slug, and id attributes (e.g., AgentPostTable).
    """
    pdf_bytes = await generate_post_pdf(
        title=post.title,
        markdown_content=post.markdown,
        agent_name=post.agent_name,
        created_at=post.created_at,
        tags=post.tags,
        cover=post.cover,
        cdn_base=cdn_base,
    )
    fname = filename or f"{post.slug or post.id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )
