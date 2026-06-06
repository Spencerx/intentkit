"""Base class for manager tools."""

from __future__ import annotations

from intentkit.tools.base import IntentKitTool


class ManagerTool(IntentKitTool):
    """Base class for all manager tools."""

    category: str = "manager"
