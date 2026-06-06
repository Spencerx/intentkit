"""Superfluid tools base class."""

from intentkit.tools.onchain import IntentKitOnChainTool


class SuperfluidBaseTool(IntentKitOnChainTool):
    """Base class for Superfluid streaming payment tools.

    Superfluid tools provide functionality to create, update, and delete
    money streams using the Superfluid protocol. Streams allow continuous
    real-time payments.

    These tools work with any EVM-compatible wallet provider (CDP, Safe/Privy).
    """

    category: str = "superfluid"
