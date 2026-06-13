"""Legal knowledge base query — keyword-based search over the legal corpus.

Provides a :class:`LegalQueryEngine` that scores relevance of jurisdiction
red-flag entries against a user's natural-language question by simple keyword
overlap and specific-term matching.
"""

from __future__ import annotations

from typing import List

from ..shared.models import JurisdictionCode, LegalArticle
from ..shared.jurisdiction import JurisdictionLoader


class LegalQueryEngine:
    """Query the legal knowledge base for articles relevant to a user query.

    All data is sourced from the :class:`JurisdictionLoader` which reads
    YAML-based red-flag definitions.  Scoring is keyword-overlap based; no
    embeddings or external services are used.
    """

    def __init__(self, loader: JurisdictionLoader):
        """Initialise the query engine.

        Args:
            loader: Jurisdiction loader providing access to red-flag data.
        """
        self.loader = loader

    def find_relevant_articles(self, jurisdiction: JurisdictionCode,
                               query: str) -> List[LegalArticle]:
        """Find legal articles relevant to a user's question using keyword matching.

        Each red-flag entry is scored by:
        - **Word overlap** between query and (label + description) — +2 per word
        - **Specific-term bonus** for domain keywords — +3 per matched term

        Only entries scoring ≥ 3 are returned.

        Args:
            jurisdiction: The jurisdiction to search within.
            query: The user's natural-language question.

        Returns:
            A list of :class:`LegalArticle` instances, sorted by insertion
            order (as encountered in the YAML corpus).
        """
        try:
            flags = self.loader.get_red_flags(jurisdiction)
        except FileNotFoundError:
            return []

        query_lower = query.lower()
        articles = []

        for flag in flags:
            # Score relevance by keyword overlap
            score = 0
            keywords = f"{flag.get('label', '')} {flag.get('description', '')}".lower()
            ref = flag.get("law_reference", {})

            # -- General word overlap --
            q_words = set(query_lower.split())
            k_words = set(keywords.split())
            overlap = q_words & k_words
            score += len(overlap) * 2

            # -- Domain-specific term matching --
            specific_terms = [
                "timeline", "deadline", "day", "days", "bid period",
                "single", "sole", "brand", "specification",
                "budget", "cost", "price", "inflation", "markup", "mark-up",
                "evaluation", "criteria", "score", "weight",
                "emergency", "urgent", "direct",
                "conflict", "interest", "recuse",
                "contract", "term", "penalty", "bond",
                "disqualif", "reject", "appeal",
                "complaint", "report", "whistle",
                "splitting", "split",
            ]
            for term in specific_terms:
                if term in query_lower and term in keywords:
                    score += 3

            if score >= 3:
                law_ref = f"{ref.get('act') or ref.get('reg', '')}, {ref.get('section') or ref.get('article', '')}"
                law_ref = law_ref.strip(", ")

                action = flag.get("action", {})
                articles.append(LegalArticle(
                    jurisdiction=jurisdiction,
                    article_id=flag.get("id", ""),
                    label=flag.get("label", ""),
                    description=flag.get("description", ""),
                    source=law_ref or "See legal corpus",
                    text=ref.get("text", ""),
                    penalty=flag.get("penalty"),
                    action=action.get("what", ""),
                    report_template=action.get("template"),
                ))

        return articles

    def get_all_articles(self, jurisdiction: JurisdictionCode) -> List[LegalArticle]:
        """Return ALL legal articles for a jurisdiction (used for system-prompt context).

        Unlike :meth:`find_relevant_articles`, this method returns every
        red-flag entry without scoring, providing a complete picture of the
        legal corpus for the given jurisdiction.

        Args:
            jurisdiction: The jurisdiction to query.

        Returns:
            A list of all :class:`LegalArticle` instances in the corpus.
        """
        try:
            flags = self.loader.get_red_flags(jurisdiction)
        except FileNotFoundError:
            return []

        articles = []
        for flag in flags:
            ref = flag.get("law_reference", {})
            law_ref = f"{ref.get('act') or ref.get('reg', '')}, {ref.get('section') or ref.get('article', '')}"
            law_ref = law_ref.strip(", ")
            action = flag.get("action", {})

            articles.append(LegalArticle(
                jurisdiction=jurisdiction,
                article_id=flag.get("id", ""),
                label=flag.get("label", ""),
                description=flag.get("description", ""),
                source=law_ref or "See legal corpus",
                text=ref.get("text", ""),
                penalty=flag.get("penalty"),
                action=action.get("what", ""),
                report_template=action.get("template"),
            ))

        return articles
