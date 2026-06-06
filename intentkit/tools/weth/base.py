"""WETH tools base class."""

from intentkit.tools.onchain import IntentKitOnChainTool


class WethBaseTool(IntentKitOnChainTool):
    """Base class for WETH wrapping/unwrapping tools.

    WETH tools provide functionality to wrap ETH to WETH and unwrap WETH to ETH.
    WETH (Wrapped ETH) is an ERC20 token representation of ETH.

    These tools work with any EVM-compatible wallet provider (CDP, Safe/Privy).
    """

    category: str = "weth"
