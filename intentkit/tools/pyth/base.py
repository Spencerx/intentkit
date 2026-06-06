"""Pyth tools base class."""

from intentkit.tools.base import IntentKitTool


class PythBaseTool(IntentKitTool):
    """Base class for Pyth tools.

    Pyth tools fetch price data from the Pyth oracle network.
    These tools do not require a wallet as they only read data.
    """

    category: str = "pyth"
