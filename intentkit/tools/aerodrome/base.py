from intentkit.tools.onchain import IntentKitOnChainTool


class AerodromeBaseTool(IntentKitOnChainTool):
    """Base class for Aerodrome tools."""

    category: str = "aerodrome"
