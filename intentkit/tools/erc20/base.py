"""ERC20 tools base class."""

from intentkit.tools.onchain import IntentKitOnChainTool


class ERC20BaseTool(IntentKitOnChainTool):
    """Base class for ERC20 token tools.

    ERC20 tools provide functionality to interact with ERC20 tokens
    including checking balances, transferring tokens, and managing approvals.

    These tools work with any EVM-compatible wallet provider (CDP, Safe/Privy).
    """

    category: str = "erc20"
