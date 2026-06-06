"""Base class for lead tools."""

from __future__ import annotations

from intentkit.tools.base import IntentKitTool


class LeadTool(IntentKitTool):
    """Base class for all lead tools."""

    category: str = "lead"
