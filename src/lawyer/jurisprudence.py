"""Legal knowledge base query — offers semantic and keyword search over legal corpus."""

from __future__ import annotations

from typing import List, Optional

from ..shared.models import JurisdictionCode, LegalArticle
from ..shared.jurisdiction import JurisdictionLoader


class LegalQueryEngine:
    """Query the legal knowledge base for relevant articles."""

    def __init__(self, loader: JurisdictionLoader):
        self.loader = loader

    def find_relevant_articles(self, jurisdiction: JurisdictionCode,
                               query: str) -> List[LegalArticle]:
        """Find legal articles relevant to a user's question using keyword matching."""
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

            # Check for keyword matches
            q_words = set(query_lower.split())
            k_words = set(keywords.split())
            overlap = q_words & k_words
            score += len(overlap) * 2

            # Check specific terms
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
        """Get ALL legal articles for a jurisdiction (for system prompt context)."""
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
