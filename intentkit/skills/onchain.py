from typing import TYPE_CHECKING

from web3 import Web3

from intentkit.clients import get_evm_account as fetch_evm_account
from intentkit.clients.web3 import get_web3_client
from intentkit.skills.base import IntentKitSkill

if TYPE_CHECKING:
    from cdp import EvmServerAccount


class IntentKitOnChainSkill(IntentKitSkill):
    """Shared helpers for on-chain enabled skills."""

    def web3_client(self) -> Web3:
        """Get a Web3 client for the active agent network."""
        context = self.get_context()
        agent = context.agent
        network_id = agent.network_id
        return get_web3_client(network_id)

    async def get_evm_account(self) -> "EvmServerAccount":
        """Fetch the EVM account associated with the active agent."""
        context = self.get_context()
        agent = context.agent
        return await fetch_evm_account(agent)
