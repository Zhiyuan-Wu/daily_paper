"""
Recommendation strategies package.

This package contains individual strategy implementations that inherit
from BaseRecommender. Each strategy can be independently registered
and used in the fusion recommendation system.

Available strategies:
- KeywordSemanticRecommender: Semantic similarity to user interests
- DisinterestedFilterRecommender: Filter out disinterested keywords
- InterestedSemanticRecommender: Similarity to recently interested papers
- DisinterestedSemanticRecommender: Dissimilarity to disliked papers
- RepetitionFilterRecommender: Downweight frequently recommended papers
- LLMThemeRecommender: LLM-generated theme matching
"""

from daily_paper.recommenders.strategies.keyword_semantic import KeywordSemanticRecommender
from daily_paper.recommenders.strategies.keyword_filter import DisinterestedFilterRecommender
from daily_paper.recommenders.strategies.interested_semantic import InterestedSemanticRecommender
from daily_paper.recommenders.strategies.disinterested_filter import DisinterestedSemanticRecommender
from daily_paper.recommenders.strategies.repetition_filter import RepetitionFilterRecommender
from daily_paper.recommenders.strategies.llm_themes import LLMThemeRecommender

__all__ = [
    "KeywordSemanticRecommender",
    "DisinterestedFilterRecommender",
    "InterestedSemanticRecommender",
    "DisinterestedSemanticRecommender",
    "RepetitionFilterRecommender",
    "LLMThemeRecommender",
]
