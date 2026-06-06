"""Twitter tools."""

import logging
from typing import TypedDict

from intentkit.clients import TwitterClientConfig
from intentkit.config.config import config as system_config
from intentkit.tools.base import ToolsetConfig, ToolState
from intentkit.tools.twitter.base import TwitterBaseTool
from intentkit.tools.twitter.follow_user import TwitterFollowUser
from intentkit.tools.twitter.get_mentions import TwitterGetMentions
from intentkit.tools.twitter.get_timeline import TwitterGetTimeline
from intentkit.tools.twitter.get_user_by_username import TwitterGetUserByUsername
from intentkit.tools.twitter.get_user_tweets import TwitterGetUserTweets
from intentkit.tools.twitter.like_tweet import TwitterLikeTweet
from intentkit.tools.twitter.post_tweet import TwitterPostTweet
from intentkit.tools.twitter.reply_tweet import TwitterReplyTweet
from intentkit.tools.twitter.retweet import TwitterRetweet
from intentkit.tools.twitter.search_tweets import TwitterSearchTweets

# we cache tools in system level, because they are stateless
_cache: dict[str, TwitterBaseTool] = {}

logger = logging.getLogger(__name__)


class ToolStates(TypedDict):
    get_mentions: ToolState
    post_tweet: ToolState
    reply_tweet: ToolState
    get_timeline: ToolState
    get_user_by_username: ToolState
    get_user_tweets: ToolState
    follow_user: ToolState
    like_tweet: ToolState
    retweet: ToolState
    search_tweets: ToolState


class Config(ToolsetConfig, TwitterClientConfig):
    """Configuration for Twitter tools."""

    states: ToolStates


async def get_tools(
    config: "Config",
    is_private: bool,
    **_,
) -> list[TwitterBaseTool]:
    """Get all Twitter tools."""
    available_tools = []

    # Include tools based on their state
    for tool_name, state in config["states"].items():
        if state == "disabled":
            continue
        elif state == "public" or (state == "private" and is_private):
            available_tools.append(tool_name)

    # Get each tool using the cached getter
    result = []
    for name in available_tools:
        tool = get_twitter_tool(name)
        if tool:
            result.append(tool)
    return result


def get_twitter_tool(
    name: str,
) -> TwitterBaseTool | None:
    """Get a Twitter tool by name.

    Args:
        name: The name of the tool to get

    Returns:
        The requested Twitter tool
    """
    if name == "get_mentions":
        if name not in _cache:
            _cache[name] = TwitterGetMentions()
        return _cache[name]
    elif name == "post_tweet":
        if name not in _cache:
            _cache[name] = TwitterPostTweet()
        return _cache[name]
    elif name == "reply_tweet":
        if name not in _cache:
            _cache[name] = TwitterReplyTweet()
        return _cache[name]
    elif name == "get_timeline":
        if name not in _cache:
            _cache[name] = TwitterGetTimeline()
        return _cache[name]
    elif name == "follow_user":
        if name not in _cache:
            _cache[name] = TwitterFollowUser()
        return _cache[name]
    elif name == "like_tweet":
        if name not in _cache:
            _cache[name] = TwitterLikeTweet()
        return _cache[name]
    elif name == "retweet":
        if name not in _cache:
            _cache[name] = TwitterRetweet()
        return _cache[name]
    elif name == "search_tweets":
        if name not in _cache:
            _cache[name] = TwitterSearchTweets()
        return _cache[name]
    elif name == "get_user_by_username":
        if name not in _cache:
            _cache[name] = TwitterGetUserByUsername()
        return _cache[name]
    elif name == "get_user_tweets":
        if name not in _cache:
            _cache[name] = TwitterGetUserTweets()
        return _cache[name]
    else:
        logger.warning("Unknown Twitter tool: %s", name)
        return None


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return all(
        [
            bool(system_config.twitter_oauth2_client_id),
            bool(system_config.twitter_oauth2_client_secret),
        ]
    )
