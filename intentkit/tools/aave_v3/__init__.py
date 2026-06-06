"""Aave V3 lending protocol tools."""

import logging
from typing import Any, TypedDict

from intentkit.tools.aave_v3.base import AaveV3BaseTool
from intentkit.tools.aave_v3.borrow import AaveV3Borrow
from intentkit.tools.aave_v3.get_reserve_data import AaveV3GetReserveData
from intentkit.tools.aave_v3.get_user_account_data import AaveV3GetUserAccountData
from intentkit.tools.aave_v3.repay import AaveV3Repay
from intentkit.tools.aave_v3.set_collateral import AaveV3SetCollateral
from intentkit.tools.aave_v3.supply import AaveV3Supply
from intentkit.tools.aave_v3.withdraw import AaveV3Withdraw
from intentkit.tools.base import ToolsetConfig, ToolState

logger = logging.getLogger(__name__)

_cache: dict[str, AaveV3BaseTool] = {}


class ToolStates(TypedDict):
    aave_v3_get_user_account_data: ToolState
    aave_v3_get_reserve_data: ToolState
    aave_v3_supply: ToolState
    aave_v3_withdraw: ToolState
    aave_v3_borrow: ToolState
    aave_v3_repay: ToolState
    aave_v3_set_collateral: ToolState


class Config(ToolsetConfig):
    """Configuration for Aave V3 tools."""

    states: ToolStates


async def get_tools(
    config: "Config",
    is_private: bool,
    **_: Any,
) -> list[AaveV3BaseTool]:
    """Get all Aave V3 tools."""
    available_tools: list[str] = []

    for tool_name, state in config["states"].items():
        if state == "disabled":
            continue
        elif state == "public" or (state == "private" and is_private):
            available_tools.append(tool_name)

    result: list[AaveV3BaseTool] = []
    for name in available_tools:
        tool = _get_tool(name)
        if tool:
            result.append(tool)
    return result


def _get_tool(name: str) -> AaveV3BaseTool | None:
    if name not in _cache:
        if name == "aave_v3_get_user_account_data":
            _cache[name] = AaveV3GetUserAccountData()
        elif name == "aave_v3_get_reserve_data":
            _cache[name] = AaveV3GetReserveData()
        elif name == "aave_v3_supply":
            _cache[name] = AaveV3Supply()
        elif name == "aave_v3_withdraw":
            _cache[name] = AaveV3Withdraw()
        elif name == "aave_v3_borrow":
            _cache[name] = AaveV3Borrow()
        elif name == "aave_v3_repay":
            _cache[name] = AaveV3Repay()
        elif name == "aave_v3_set_collateral":
            _cache[name] = AaveV3SetCollateral()
        else:
            logger.warning("Unknown aave_v3 tool: %s", name)
            return None
    return _cache[name]


def available() -> bool:
    """Aave V3 requires no platform API keys."""
    return True
