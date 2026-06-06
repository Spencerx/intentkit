from typing import Literal

from intentkit.tools.base import IntentKitTool


class UIBaseTool(IntentKitTool):
    """Base class for UI-related tools."""

    category: str = "ui"

    # Set response format to content_and_artifact for returning tuple
    response_format: Literal["content", "content_and_artifact"] = "content_and_artifact"
