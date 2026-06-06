"""Predefined tag categories for an agent published to public.

The enum is the source of truth for tag values across both the team API and
the manager-agent publish tool. UI labels are derived in the frontend.
The grouping (`AGENT_TAG_CATEGORIES`) is the single source of truth for how
tags are bucketed in the UI selector.
"""

from __future__ import annotations

from enum import Enum


class AgentTag(str, Enum):
    """Allowed tags for a publicly listed agent."""

    PRODUCTIVITY = "productivity"
    WRITING = "writing"
    TRANSLATION = "translation"
    CODING = "coding"
    SUMMARIZATION = "summarization"
    EMAIL = "email"
    MEETINGS = "meetings"
    CREATIVE_WRITING = "creative-writing"
    ART = "art"
    DESIGN = "design"
    MUSIC = "music"
    VIDEO = "video"
    PHOTOGRAPHY = "photography"
    ROLEPLAY = "roleplay"
    STORYTELLING = "storytelling"
    EDUCATION = "education"
    LANGUAGE_LEARNING = "language-learning"
    MATH = "math"
    SCIENCE = "science"
    TUTORING = "tutoring"
    LIFESTYLE = "lifestyle"
    FITNESS = "fitness"
    COOKING = "cooking"
    TRAVEL = "travel"
    FASHION = "fashion"
    PARENTING = "parenting"
    PETS = "pets"
    SHOPPING = "shopping"
    GAMES = "games"
    MOVIES = "movies"
    TV = "tv"
    BOOKS = "books"
    ANIME = "anime"
    COMICS = "comics"
    SPORTS = "sports"
    RESEARCH = "research"
    NEWS = "news"
    HISTORY = "history"
    PHILOSOPHY = "philosophy"
    PSYCHOLOGY = "psychology"
    HEALTH = "health"
    MENTAL_HEALTH = "mental-health"
    NUTRITION = "nutrition"
    MEDITATION = "meditation"
    COMPANION = "companion"
    FRIENDSHIP = "friendship"
    DATING = "dating"
    BUSINESS = "business"
    FINANCE = "finance"
    MARKETING = "marketing"
    SALES = "sales"
    LEGAL = "legal"
    HR = "hr"
    DEVELOPER_TOOLS = "developer-tools"
    DATA_ANALYSIS = "data-analysis"
    AUTOMATION = "automation"
    SECURITY = "security"
    UTILITY = "utility"
    OTHER = "other"


AGENT_TAG_CATEGORIES: dict[str, list[AgentTag]] = {
    "productivity": [
        AgentTag.PRODUCTIVITY,
        AgentTag.WRITING,
        AgentTag.TRANSLATION,
        AgentTag.CODING,
        AgentTag.SUMMARIZATION,
        AgentTag.EMAIL,
        AgentTag.MEETINGS,
    ],
    "creative": [
        AgentTag.CREATIVE_WRITING,
        AgentTag.ART,
        AgentTag.DESIGN,
        AgentTag.MUSIC,
        AgentTag.VIDEO,
        AgentTag.PHOTOGRAPHY,
        AgentTag.ROLEPLAY,
        AgentTag.STORYTELLING,
    ],
    "education": [
        AgentTag.EDUCATION,
        AgentTag.LANGUAGE_LEARNING,
        AgentTag.MATH,
        AgentTag.SCIENCE,
        AgentTag.TUTORING,
    ],
    "lifestyle": [
        AgentTag.LIFESTYLE,
        AgentTag.FITNESS,
        AgentTag.COOKING,
        AgentTag.TRAVEL,
        AgentTag.FASHION,
        AgentTag.PARENTING,
        AgentTag.PETS,
        AgentTag.SHOPPING,
    ],
    "entertainment": [
        AgentTag.GAMES,
        AgentTag.MOVIES,
        AgentTag.TV,
        AgentTag.BOOKS,
        AgentTag.ANIME,
        AgentTag.COMICS,
        AgentTag.SPORTS,
    ],
    "knowledge": [
        AgentTag.RESEARCH,
        AgentTag.NEWS,
        AgentTag.HISTORY,
        AgentTag.PHILOSOPHY,
        AgentTag.PSYCHOLOGY,
    ],
    "health": [
        AgentTag.HEALTH,
        AgentTag.MENTAL_HEALTH,
        AgentTag.NUTRITION,
        AgentTag.MEDITATION,
    ],
    "companion": [
        AgentTag.COMPANION,
        AgentTag.FRIENDSHIP,
        AgentTag.DATING,
    ],
    "business": [
        AgentTag.BUSINESS,
        AgentTag.FINANCE,
        AgentTag.MARKETING,
        AgentTag.SALES,
        AgentTag.LEGAL,
        AgentTag.HR,
    ],
    "tech": [
        AgentTag.DEVELOPER_TOOLS,
        AgentTag.DATA_ANALYSIS,
        AgentTag.AUTOMATION,
        AgentTag.SECURITY,
    ],
    "other": [
        AgentTag.UTILITY,
        AgentTag.OTHER,
    ],
}
