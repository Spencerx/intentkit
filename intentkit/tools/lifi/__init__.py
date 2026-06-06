import logging
from typing import Any, NotRequired, TypedDict

from intentkit.tools.base import ToolsetConfig, ToolState
from intentkit.tools.lifi.base import LiFiBaseTool
from intentkit.tools.lifi.token_execute import TokenExecute
from intentkit.tools.lifi.token_quote import TokenQuote

# Cache tools at the system level, because they are stateless
_cache: dict[str, LiFiBaseTool] = {}

# Set up logging
logger = logging.getLogger(__name__)


class ToolStates(TypedDict):
    token_quote: ToolState
    token_execute: ToolState


class Config(ToolsetConfig):
    """Configuration for LiFi tools."""

    states: ToolStates
    default_slippage: NotRequired[float | None]
    allowed_chains: NotRequired[list[str] | None]
    max_execution_time: NotRequired[int | None]


async def get_tools(
    config: "Config",
    is_private: bool,
    **_: Any,
) -> list[LiFiBaseTool]:
    """Get all LiFi tools."""
    available_tools: list[str] = []

    # Log configuration
    logger.info("[LiFi_Tools] Initializing with config: %s", config)
    logger.info("[LiFi_Tools] Is private session: %s", is_private)

    # Include tools based on their state
    for tool_name, state in config["states"].items():
        if state == "disabled":
            logger.info("[LiFi_Tools] Skipping disabled tool: %s", tool_name)
            continue
        elif state == "public" or (state == "private" and is_private):
            available_tools.append(tool_name)
            logger.info("[LiFi_Tools] Including tool: %s (state: %s)", tool_name, state)
        else:
            logger.info(
                f"[LiFi_Tools] Skipping private tool in public session: {tool_name}"
            )

    logger.info("[LiFi_Tools] Available tools: %s", available_tools)

    # Get each tool using the cached getter
    tools: list[LiFiBaseTool] = []
    for name in available_tools:
        tool = get_lifi_tool(name, config)
        if tool:
            tools.append(tool)
            logger.info("[LiFi_Tools] Successfully loaded tool: %s", name)

    logger.info("[LiFi_Tools] Total tools loaded: %s", len(tools))
    return tools


def get_lifi_tool(
    name: str,
    config: Config,
) -> LiFiBaseTool | None:
    """Get a LiFi tool by name."""
    # Create a cache key that includes configuration to ensure tools
    # with different configurations are treated as separate instances
    cache_key = f"{name}_{id(config)}"

    # Extract configuration options with proper defaults
    default_slippage: float = config.get("default_slippage", None) or 0.03
    allowed_chains = config.get("allowed_chains", None)
    max_execution_time: int = config.get("max_execution_time", None) or 300

    # Validate configuration
    if default_slippage < 0.001 or default_slippage > 0.5:
        logger.warning(
            f"[LiFi_Tools] Invalid default_slippage: {default_slippage}, using 0.03"
        )
        default_slippage = 0.03

    if max_execution_time < 60 or max_execution_time > 1800:
        logger.warning(
            f"[LiFi_Tools] Invalid max_execution_time: {max_execution_time}, using 300"
        )
        max_execution_time = 300

    if name == "token_quote":
        if cache_key not in _cache:
            logger.info(
                f"[LiFi_Tools] Initializing token_quote tool with slippage: {default_slippage}"
            )
            if allowed_chains:
                logger.info("[LiFi_Tools] Allowed chains: %s", allowed_chains)

            _cache[cache_key] = TokenQuote(
                default_slippage=default_slippage,
                allowed_chains=allowed_chains,
            )
        return _cache[cache_key]

    elif name == "token_execute":
        if cache_key not in _cache:
            logger.info("[LiFi_Tools] Initializing token_execute tool")
            logger.info(
                f"[LiFi_Tools] Configuration - slippage: {default_slippage}, max_time: {max_execution_time}"
            )
            if allowed_chains:
                logger.info("[LiFi_Tools] Allowed chains: %s", allowed_chains)

            # Log a warning about CDP wallet requirements
            logger.warning(
                "[LiFi_Tools] token_execute requires a properly configured CDP wallet with sufficient funds"
            )

            _cache[cache_key] = TokenExecute(
                default_slippage=default_slippage,
                allowed_chains=allowed_chains,
                max_execution_time=max_execution_time,
            )
        return _cache[cache_key]

    else:
        logger.warning("[LiFi_Tools] Unknown LiFi tool requested: %s", name)
        return None


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return True
