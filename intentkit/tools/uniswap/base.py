from intentkit.tools.onchain import IntentKitOnChainTool


class UniswapBaseTool(IntentKitOnChainTool):
    """Base class for Uniswap tools."""

    category: str = "uniswap"
