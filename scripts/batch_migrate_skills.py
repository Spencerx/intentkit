#!/usr/bin/env python3
"""
Batch migration script for Agent tools configuration.

This script fetches all agents from the database, migrates their tools configuration
from the old format (xxx_tools and xxx_config) to the new format where they are moved
into the tools field as a sub-dictionary, and saves them back to the database.

Usage:
  intentkit export AGENT_ID
  intentkit import AGENT_ID.yaml
"""

import asyncio
import logging

from sqlalchemy import select

from intentkit.config.config import config
from intentkit.config.db import get_session, init_db
from intentkit.models.agent import AgentTable

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def migrate_agent_tools(agent: AgentTable) -> bool:
    """
    Migrate an agent's tools from old format to new format.

    Old format:
    ```
    acolyt_tools = ["ask_gpt"]
    acolyt_config = {"api_key": "abc"}
    ```

    New format:
    ```
    tools = {
        "acolyt": {
            "states": {"ask_gpt": "public"},
            "enabled": true
        }
    }
    ```

    Args:
        agent: The agent to migrate

    Returns:
        bool: True if the agent was modified, False otherwise
    """
    # Initialize tools field if it doesn't exist
    if agent.tools is None:
        agent.tools = {}

    # Define the mapping of old tool fields to new tool names
    tool_mappings = [
        {"tools": "cdp_tools", "config": None, "name": "cdp"},
        {"tools": "twitter_tools", "config": "twitter_config", "name": "twitter"},
        {"tools": "enso_tools", "config": "enso_config", "name": "enso"},
        {"tools": "acolyt_tools", "config": "acolyt_config", "name": "acolyt"},
        {"tools": "allora_tools", "config": "allora_config", "name": "allora"},
        {"tools": "elfa_tools", "config": "elfa_config", "name": "elfa"},
    ]

    modified = False

    # Process each tool mapping
    for mapping in tool_mappings:
        tools_field = mapping["tools"]
        config_field = mapping["config"]
        tool_name = mapping["name"]

        # Get the tools list using getattr to access the column values
        tools_list = getattr(agent, tools_field, None)

        # Skip if the tools list is empty or None
        if not tools_list:
            continue

        # Get the config if it exists
        config = getattr(agent, config_field, {}) if config_field else {}

        # Create the new tool entry
        tool_entry = {
            "states": {tool: "public" for tool in tools_list},
            "enabled": True,
        }

        # Add any config values
        if config:
            # Merge config with the tool entry
            for key, value in config.items():
                if key != "states" and key != "enabled":
                    tool_entry[key] = value

        # Add the tool entry to the tools field
        agent.tools[tool_name] = tool_entry

        # Clear the old fields
        setattr(agent, tools_field, None)
        if config_field:
            setattr(agent, config_field, None)

        modified = True

    return modified


async def batch_migrate_tools():
    """
    Fetch all agents from the database, migrate their tools, and save them back.
    """
    async with get_session() as session:
        # Fetch all agents
        result = await session.execute(select(AgentTable))
        agents = result.scalars().all()

        logger.info(f"Found {len(agents)} agents to process")

        migrated_count = 0
        for agent in agents:
            try:
                # Migrate the agent's tools
                modified = await migrate_agent_tools(agent)

                if modified:
                    # Save the agent back to the database
                    session.add(agent)
                    migrated_count += 1
                    logger.info(f"Migrated agent {agent.id} ({agent.name})")
            except Exception as e:
                logger.error(f"Error migrating agent {agent.id}: {e}")

        if migrated_count > 0:
            # Commit the changes
            await session.commit()
            logger.info(f"Successfully migrated {migrated_count} agents")
        else:
            logger.info("No agents needed migration")


async def main():
    """
    Main entry point for the script.
    """
    # Initialize the database connection
    await init_db(**config.db)

    # Run the batch migration
    await batch_migrate_tools()


if __name__ == "__main__":
    asyncio.run(main())
