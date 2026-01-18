"""
User interaction management module.

Manages user profile, interactions with papers, and preferences.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from sqlalchemy.orm import Session

from daily_paper.database import Paper, PaperInteraction, UserProfile

logger = logging.getLogger(__name__)


class UserManager:
    """
    Manager for user interactions and preferences.

    Since this is a single-user system, manages the single user profile
    and tracks interactions with papers.

    Typical usage:
        >>> manager = UserManager(session)
        >>> profile = manager.get_profile()
        >>> manager.mark_paper_interested(paper_id=123)
        >>> manager.update_interests(
        ...     interested_keywords="LLM, transformers",
        ...     interest_description="Natural language processing"
        ... )

    Attributes:
        session: Database session.
    """

    def __init__(self, session: Session):
        """
        Initialize the user manager.

        Args:
            session: SQLAlchemy database session.
        """
        self.session = session

    def get_profile(self) -> UserProfile:
        """
        Get or create user profile.

        Returns:
            UserProfile object (creates if doesn't exist).
        """
        profile = self.session.query(UserProfile).first()

        if not profile:
            # Create default profile
            profile = UserProfile(
                id=1,
                interested_keywords="",
                disinterested_keywords="",
                interest_description="",
            )
            self.session.add(profile)
            self.session.commit()
            logger.info("Created default user profile")

        return profile

    def update_interests(
        self,
        interested_keywords: Optional[str] = None,
        disinterested_keywords: Optional[str] = None,
        interest_description: Optional[str] = None,
    ) -> UserProfile:
        """
        Update user interests and preferences.

        Args:
            interested_keywords: Comma-separated keywords of interest.
            disinterested_keywords: Keywords to exclude.
            interest_description: Free-text description of interests.

        Returns:
            Updated UserProfile object.
        """
        profile = self.get_profile()

        if interested_keywords is not None:
            profile.interested_keywords = interested_keywords
        if disinterested_keywords is not None:
            profile.disinterested_keywords = disinterested_keywords
        if interest_description is not None:
            profile.interest_description = interest_description

        self.session.commit()
        logger.info("Updated user interests")

        return profile

    def mark_paper_interested(
        self,
        paper_id: int,
        notes: Optional[str] = None,
    ) -> PaperInteraction:
        """
        Mark a paper as interested.

        Args:
            paper_id: ID of the paper.
            notes: Optional user notes.

        Returns:
            Updated or created PaperInteraction object.
        """
        return self._set_paper_action(paper_id, "interested", notes)

    def mark_paper_not_interested(
        self,
        paper_id: int,
        notes: Optional[str] = None,
    ) -> PaperInteraction:
        """
        Mark a paper as not interested.

        Args:
            paper_id: ID of the paper.
            notes: Optional user notes.

        Returns:
            Updated or created PaperInteraction object.
        """
        return self._set_paper_action(paper_id, "not_interested", notes)

    def clear_paper_action(self, paper_id: int) -> Optional[PaperInteraction]:
        """
        Clear action on a paper (reset to no_action).

        Args:
            paper_id: ID of the paper.

        Returns:
            Updated PaperInteraction object or None.
        """
        interaction = (
            self.session.query(PaperInteraction)
            .filter(PaperInteraction.paper_id == paper_id)
            .first()
        )

        if interaction:
            interaction.action = "no_action"
            self.session.commit()
            logger.info(f"Cleared action on paper {paper_id}")
            return interaction

        return None

    def _set_paper_action(
        self,
        paper_id: int,
        action: str,
        notes: Optional[str] = None,
    ) -> PaperInteraction:
        """
        Set action on a paper.

        Internal method for marking paper interactions.

        Args:
            paper_id: ID of the paper.
            action: Action to set ('interested' or 'not_interested').
            notes: Optional user notes.

        Returns:
            Updated or created PaperInteraction object.
        """
        # Verify paper exists
        paper = self.session.query(Paper).filter(Paper.id == paper_id).first()
        if not paper:
            raise ValueError(f"Paper {paper_id} not found")

        # Get or create interaction
        interaction = (
            self.session.query(PaperInteraction)
            .filter(PaperInteraction.paper_id == paper_id)
            .first()
        )

        if interaction:
            interaction.action = action
            if notes is not None:
                interaction.notes = notes
        else:
            interaction = PaperInteraction(
                user_id=1,
                paper_id=paper_id,
                action=action,
                notes=notes,
                recommendation_count=0,
            )
            self.session.add(interaction)

        self.session.commit()
        logger.info(f"Marked paper {paper_id} as {action}")

        return interaction

    def get_interactions(
        self,
        action: Optional[str] = None,
        limit: int = 100,
    ) -> List[PaperInteraction]:
        """
        Get user interactions with papers.

        Args:
            action: Filter by action (None = all).
            limit: Maximum number of interactions to return.

        Returns:
            List of PaperInteraction objects.
        """
        query = self.session.query(PaperInteraction)

        if action:
            query = query.filter(PaperInteraction.action == action)

        interactions = query.order_by(
            PaperInteraction.created_at.desc()
        ).limit(limit).all()

        return interactions

    def get_interested_papers(self, limit: int = 50) -> List[Paper]:
        """
        Get papers marked as interested.

        Args:
            limit: Maximum number of papers to return.

        Returns:
            List of Paper objects.
        """
        interested_paper_ids = (
            self.session.query(PaperInteraction.paper_id)
            .filter(PaperInteraction.action == "interested")
            .all()
        )

        paper_ids = [pid for (pid,) in interested_paper_ids]

        papers = (
            self.session.query(Paper)
            .filter(Paper.id.in_(paper_ids))
            .limit(limit)
            .all()
        )

        return papers
