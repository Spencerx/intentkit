from typing import NotRequired

from langchain_core.tools import BaseTool

from intentkit.tools.base import ToolsetConfig
from intentkit.tools.jupiter.price import JupiterGetPrice
from intentkit.tools.jupiter.swap import JupiterGetQuote


class JupiterConfig(ToolsetConfig):
    api_key: NotRequired[str | None]


async def get_tools(
    config: JupiterConfig,
    is_private: bool,
    **_,
) -> list[BaseTool]:
    api_key = config.get("api_key")
    return [
        JupiterGetPrice(api_key=api_key),
        JupiterGetQuote(api_key=api_key),
    ]


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return True
