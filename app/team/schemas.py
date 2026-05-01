"""Team-specific request/response schemas.

Kept separate from ``intentkit.models`` because these are server-side input
shapes for the ``app/team`` API only — they aren't part of the shared agent
domain model.
"""

from __future__ import annotations

from enum import Enum
from typing import ClassVar

from pydantic import BaseModel, ConfigDict
from pydantic import Field as PydanticField

from intentkit.models.agent.public_info import AgentExample


class TeamAgentTag(str, Enum):
    """Allowed tags for an agent published from the team UI.

    Values are lowercase, hyphen-separated for DB/URL friendliness; UI labels
    are derived in the frontend.
    """

    # Productivity & Work
    PRODUCTIVITY = "productivity"
    WRITING = "writing"
    TRANSLATION = "translation"
    CODING = "coding"
    SUMMARIZATION = "summarization"
    EMAIL = "email"
    MEETINGS = "meetings"

    # Creative
    CREATIVE_WRITING = "creative-writing"
    ART = "art"
    DESIGN = "design"
    MUSIC = "music"
    VIDEO = "video"
    PHOTOGRAPHY = "photography"
    ROLEPLAY = "roleplay"
    STORYTELLING = "storytelling"

    # Education
    EDUCATION = "education"
    LANGUAGE_LEARNING = "language-learning"
    MATH = "math"
    SCIENCE = "science"
    TUTORING = "tutoring"

    # Lifestyle
    LIFESTYLE = "lifestyle"
    FITNESS = "fitness"
    COOKING = "cooking"
    TRAVEL = "travel"
    FASHION = "fashion"
    PARENTING = "parenting"
    PETS = "pets"
    SHOPPING = "shopping"

    # Entertainment
    GAMES = "games"
    MOVIES = "movies"
    TV = "tv"
    BOOKS = "books"
    ANIME = "anime"
    COMICS = "comics"
    SPORTS = "sports"

    # Knowledge
    RESEARCH = "research"
    NEWS = "news"
    HISTORY = "history"
    PHILOSOPHY = "philosophy"
    PSYCHOLOGY = "psychology"

    # Health
    HEALTH = "health"
    MENTAL_HEALTH = "mental-health"
    NUTRITION = "nutrition"
    MEDITATION = "meditation"

    # Companion
    COMPANION = "companion"
    FRIENDSHIP = "friendship"
    DATING = "dating"

    # Business
    BUSINESS = "business"
    FINANCE = "finance"
    MARKETING = "marketing"
    SALES = "sales"
    LEGAL = "legal"
    HR = "hr"

    # Tech
    DEVELOPER_TOOLS = "developer-tools"
    DATA_ANALYSIS = "data-analysis"
    AUTOMATION = "automation"
    SECURITY = "security"

    # Other
    UTILITY = "utility"
    OTHER = "other"


# Category ordering and grouping for the public-tags listing endpoint.
# Frontend uses this to render grouped selectors; the order here is the order
# users will see.
TEAM_AGENT_TAG_CATEGORIES: list[tuple[str, list[TeamAgentTag]]] = [
    (
        "productivity",
        [
            TeamAgentTag.PRODUCTIVITY,
            TeamAgentTag.WRITING,
            TeamAgentTag.TRANSLATION,
            TeamAgentTag.CODING,
            TeamAgentTag.SUMMARIZATION,
            TeamAgentTag.EMAIL,
            TeamAgentTag.MEETINGS,
        ],
    ),
    (
        "creative",
        [
            TeamAgentTag.CREATIVE_WRITING,
            TeamAgentTag.ART,
            TeamAgentTag.DESIGN,
            TeamAgentTag.MUSIC,
            TeamAgentTag.VIDEO,
            TeamAgentTag.PHOTOGRAPHY,
            TeamAgentTag.ROLEPLAY,
            TeamAgentTag.STORYTELLING,
        ],
    ),
    (
        "education",
        [
            TeamAgentTag.EDUCATION,
            TeamAgentTag.LANGUAGE_LEARNING,
            TeamAgentTag.MATH,
            TeamAgentTag.SCIENCE,
            TeamAgentTag.TUTORING,
        ],
    ),
    (
        "lifestyle",
        [
            TeamAgentTag.LIFESTYLE,
            TeamAgentTag.FITNESS,
            TeamAgentTag.COOKING,
            TeamAgentTag.TRAVEL,
            TeamAgentTag.FASHION,
            TeamAgentTag.PARENTING,
            TeamAgentTag.PETS,
            TeamAgentTag.SHOPPING,
        ],
    ),
    (
        "entertainment",
        [
            TeamAgentTag.GAMES,
            TeamAgentTag.MOVIES,
            TeamAgentTag.TV,
            TeamAgentTag.BOOKS,
            TeamAgentTag.ANIME,
            TeamAgentTag.COMICS,
            TeamAgentTag.SPORTS,
        ],
    ),
    (
        "knowledge",
        [
            TeamAgentTag.RESEARCH,
            TeamAgentTag.NEWS,
            TeamAgentTag.HISTORY,
            TeamAgentTag.PHILOSOPHY,
            TeamAgentTag.PSYCHOLOGY,
        ],
    ),
    (
        "health",
        [
            TeamAgentTag.HEALTH,
            TeamAgentTag.MENTAL_HEALTH,
            TeamAgentTag.NUTRITION,
            TeamAgentTag.MEDITATION,
        ],
    ),
    (
        "companion",
        [
            TeamAgentTag.COMPANION,
            TeamAgentTag.FRIENDSHIP,
            TeamAgentTag.DATING,
        ],
    ),
    (
        "business",
        [
            TeamAgentTag.BUSINESS,
            TeamAgentTag.FINANCE,
            TeamAgentTag.MARKETING,
            TeamAgentTag.SALES,
            TeamAgentTag.LEGAL,
            TeamAgentTag.HR,
        ],
    ),
    (
        "tech",
        [
            TeamAgentTag.DEVELOPER_TOOLS,
            TeamAgentTag.DATA_ANALYSIS,
            TeamAgentTag.AUTOMATION,
            TeamAgentTag.SECURITY,
        ],
    ),
    (
        "other",
        [
            TeamAgentTag.UTILITY,
            TeamAgentTag.OTHER,
        ],
    ),
]


class TeamAgentPublishInput(BaseModel):
    """Request body for the team publish-to-public endpoint.

    Carries only the four public-info fields the team UI exposes. Anything
    else (ticker, token_*, x402_price, fee_percentage, public_extra) is
    intentionally not accepted here — the team handler fills in the
    fee_percentage default itself and ignores other public-info fields.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(
        title="TeamAgentPublishInput",
        extra="forbid",
    )

    description: str = PydanticField(
        ...,
        min_length=1,
        max_length=1000,
        description="Public description of the agent",
    )
    example_intro: str = PydanticField(
        ...,
        min_length=1,
        max_length=2000,
        description="Intro shown above the example prompts in a new chat",
    )
    examples: list[AgentExample] = PydanticField(
        ...,
        min_length=1,
        max_length=6,
        description="Example prompts (1-6) shown to users in a new chat",
    )
    tags: list[TeamAgentTag] | None = PydanticField(
        None,
        max_length=3,
        description="Up to 3 category tags from the predefined list",
    )
