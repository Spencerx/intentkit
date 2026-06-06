"""ERC721 tools base class."""

from intentkit.tools.onchain import IntentKitOnChainTool


class ERC721BaseTool(IntentKitOnChainTool):
    """Base class for ERC721 NFT tools.

    ERC721 tools provide functionality to interact with NFT contracts
    including checking balances, minting, and transferring tokens.

    These tools work with any EVM-compatible wallet provider (CDP, Safe/Privy).
    """

    category: str = "erc721"
