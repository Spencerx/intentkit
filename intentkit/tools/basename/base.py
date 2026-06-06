"""Basename tools base class."""

from intentkit.tools.onchain import IntentKitOnChainTool


class BasenameBaseTool(IntentKitOnChainTool):
    """Base class for Basename tools."""

    category: str = "basename"
