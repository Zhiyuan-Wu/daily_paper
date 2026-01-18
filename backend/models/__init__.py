"""
Pydantic models for API requests and responses.
"""

from .paper import (
    PaperResponse,
    PaperListResponse,
    SummaryResponse,
    PaperSearchRequest,
)
from .user import (
    UserProfileResponse,
    UserProfileUpdateRequest,
    InteractionCreateRequest,
    InteractionResponse,
)
from .report import (
    ReportResponse,
    ReportGenerateRequest,
)
from .recommendation import (
    RecommendationResponse,
)

__all__ = [
    # Paper models
    "PaperResponse",
    "PaperListResponse",
    "SummaryResponse",
    "PaperSearchRequest",
    # User models
    "UserProfileResponse",
    "UserProfileUpdateRequest",
    "InteractionCreateRequest",
    "InteractionResponse",
    # Report models
    "ReportResponse",
    "ReportGenerateRequest",
    # Recommendation models
    "RecommendationResponse",
]
