"""System skills for IntentKit agents.

These skills wrap core functionality and are available to all agents
without additional configuration. Each skill is a cached singleton instance
that can be imported directly where needed.
"""

from intentkit.core.system_skills.base import SystemSkill
from intentkit.core.system_skills.call_agent import CallAgentSkill
from intentkit.core.system_skills.create_activity import CreateActivitySkill
from intentkit.core.system_skills.create_post import CreatePostSkill
from intentkit.core.system_skills.current_time import CurrentTimeSkill
from intentkit.core.system_skills.get_post import GetPostSkill
from intentkit.core.system_skills.read_webpage import ReadWebpageCloudflareSkill
from intentkit.core.system_skills.recent_activities import RecentActivitiesSkill
from intentkit.core.system_skills.recent_posts import RecentPostsSkill
from intentkit.core.system_skills.search_web import WebSearchSkill
from intentkit.core.system_skills.store_image import StoreImageSkill
from intentkit.core.system_skills.update_memory import UpdateMemorySkill

__all__ = [
    "SystemSkill",
    "call_agent",
    "create_activity",
    "create_post",
    "current_time",
    "get_post",
    "read_webpage_cloudflare",
    "recent_activities",
    "recent_posts",
    "store_image",
    "update_memory",
    "web_search",
]

# Cached singleton instances — import these directly where needed.
call_agent = CallAgentSkill()
create_activity = CreateActivitySkill()
create_post = CreatePostSkill()
current_time = CurrentTimeSkill()
get_post = GetPostSkill()
read_webpage_cloudflare = ReadWebpageCloudflareSkill()
recent_activities = RecentActivitiesSkill()
recent_posts = RecentPostsSkill()
store_image = StoreImageSkill()
update_memory = UpdateMemorySkill()
web_search = WebSearchSkill()
