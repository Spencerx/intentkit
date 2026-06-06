from intentkit.tools.onchain import IntentKitOnChainTool


class PancakeSwapBaseTool(IntentKitOnChainTool):
    """Base class for PancakeSwap tools."""

    category: str = "pancakeswap"
