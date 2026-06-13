"""Corruption risk scoring for tender documents.

Applies a configurable set of rule-based checks against a parsed TenderDocument
to produce a RiskReport with per-section scores and flagged clauses.  Rules
are jurisdiction-independent heuristics covering timeline, specifications,
budget, evaluation criteria, emergency procurement, and contract terms.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import List, Optional, Tuple

from ..shared.models import (
    TenderDocument,
    TenderSection,
    FlaggedClause,
    Severity,
    RiskReport,
    RiskLevel,
)


class RiskScorer:
    """Rule-based + LLM-assisted corruption risk scorer.

    Each rule in :attr:`rules` is a dict with an id, label, severity,
    description, and a callable *check* method.  The scorer runs every
    check and collects any returned (FlaggedClause, RiskLevel) tuples.
    """

    def __init__(self):
        # Default scoring rules — jurisdiction-independent heuristics
        self.rules = self._default_rules()

    # ── Rule definitions ──────────────────────────────────────────────

    def _default_rules(self) -> List[dict]:
        """Build the default set of risk-check rules."""
        return [
            {
                "id": "timeline-too-short",
                "label": "Suspiciously Short Timeline",
                "section": TenderSection.TIMELINE,
                "severity": Severity.HIGH,
                "description": (
                    "Bid submission period appears unusually short, "
                    "limiting competition."
                ),
                "check": self._check_timeline,
            },
            {
                "id": "single-brand-spec",
                "label": "Single Brand / Tailored Specification",
                "section": TenderSection.SPECIFICATION,
                "severity": Severity.HIGH,
                "description": (
                    "Technical specifications reference a specific brand, "
                    "model, or appear tailored to one supplier."
                ),
                "check": self._check_single_brand,
            },
            {
                "id": "budget-inflation",
                "label": "Potential Budget Inflation",
                "section": TenderSection.BUDGET,
                "severity": Severity.MEDIUM,
                "description": (
                    "Budget data shows potential inflation indicators: "
                    "vague cost breakdown, no rate analysis, round numbers."
                ),
                "check": self._check_budget_inflation,
            },
            {
                "id": "opaque-evaluation",
                "label": "Vague Evaluation Criteria",
                "section": TenderSection.EVALUATION_CRITERIA,
                "severity": Severity.HIGH,
                "description": (
                    "Evaluation criteria are missing, vague, or use "
                    "subjective language."
                ),
                "check": self._check_opaque_evaluation,
            },
            {
                "id": "missing-evaluation-section",
                "label": "No Evaluation Criteria Section",
                "section": TenderSection.EVALUATION_CRITERIA,
                "severity": Severity.CRITICAL,
                "description": (
                    "No evaluation methodology published — impossible "
                    "to verify fair award."
                ),
                "check": self._check_missing_section,
            },
            {
                "id": "emergency-keywords",
                "label": "Emergency Procurement Without Justification",
                "section": TenderSection.DETAILS,
                "severity": Severity.CRITICAL,
                "description": (
                    "Emergency/direct procurement mentioned without "
                    "explanation of the emergency."
                ),
                "check": self._check_emergency,
            },
            {
                "id": "vague-spec",
                "label": "Vague or Copy-Pasted Specifications",
                "section": TenderSection.SPECIFICATION,
                "severity": Severity.MEDIUM,
                "description": (
                    "Technical specs are vague, generic, or appear "
                    "copy-pasted from another document."
                ),
                "check": self._check_vague_spec,
            },
            {
                "id": "conflict-interest-signals",
                "label": "Potential Conflict of Interest Signals",
                "section": TenderSection.TERMS,
                "severity": Severity.HIGH,
                "description": (
                    "Terms lack conflict of interest declaration or "
                    "recusal requirements."
                ),
                "check": self._check_conflict_interest,
            },
            {
                "id": "unusual-contract-terms",
                "label": "Unusual or One-Sided Contract Terms",
                "section": TenderSection.TERMS,
                "severity": Severity.MEDIUM,
                "description": (
                    "Contract terms appear unusually favorable to "
                    "contractor or lack standard safeguards."
                ),
                "check": self._check_unusual_terms,
            },
        ]

    # ── Main scoring entry point ──────────────────────────────────────

    def score(self, tender: TenderDocument) -> RiskReport:
        """Run all rules against a tender document and produce a risk report.

        Args:
            tender: A parsed TenderDocument.

        Returns:
            A RiskReport containing the overall risk level, per-section
            scores, flagged clauses, and a human-readable summary.
        """
        flagged: List[FlaggedClause] = []
        section_scores: dict[str, RiskLevel] = {}

        # Track which sections received at least one flag
        flagged_sections = set()

        for rule in self.rules:
            result = rule["check"](tender)
            if result:
                clause, section_risk_override = result
                flagged.append(clause)
                flagged_sections.add(rule["section"].value)
                section_scores[rule["section"].value] = section_risk_override

        # Any section that wasn't flagged defaults to GREEN
        for section in TenderSection:
            if section.value not in section_scores:
                section_scores[section.value] = RiskLevel.GREEN

        # Overall risk aggregation:
        #   CRITICAL if any critical flag
        #   RED     if 3+ high flags
        #   YELLOW  if any high or 2+ medium flags
        #   GREEN   otherwise
        overall = self._compute_overall(flagged)

        summary = self._generate_summary(flagged, overall)

        return RiskReport(
            tender=tender,
            overall_risk=overall,
            section_scores=section_scores,
            flagged_clauses=flagged,
            summary=summary,
        )

    # ── Aggregation helpers ───────────────────────────────────────────

    def _compute_overall(self, flagged: List[FlaggedClause]) -> RiskLevel:
        """Derive the overall risk level from all flagged clauses."""
        critical = any(f.severity == Severity.CRITICAL for f in flagged)
        high_count = sum(1 for f in flagged if f.severity == Severity.HIGH)
        medium_count = sum(1 for f in flagged if f.severity == Severity.MEDIUM)

        if critical or high_count >= 3:
            return RiskLevel.RED
        if high_count >= 1 or medium_count >= 2:
            return RiskLevel.YELLOW
        return RiskLevel.GREEN

    def _generate_summary(
        self, flagged: List[FlaggedClause], overall: RiskLevel
    ) -> str:
        """Produce a short human-readable summary of the risk analysis."""
        if not flagged:
            return (
                "No red flags detected. "
                "The tender appears procedurally sound."
            )
        total = len(flagged)
        critical = sum(1 for f in flagged if f.severity == Severity.CRITICAL)
        high = sum(1 for f in flagged if f.severity == Severity.HIGH)
        medium = sum(1 for f in flagged if f.severity == Severity.MEDIUM)

        lines = [
            f"Risk Level: {overall.upper()}",
            f"Total red flags: {total} "
            f"({critical} critical, {high} high, {medium} medium)",
        ]
        if overall == RiskLevel.RED:
            lines.append(
                "This tender shows strong indicators of corruption risk. "
                "Consider legal counsel."
            )
        elif overall == RiskLevel.YELLOW:
            lines.append(
                "This tender has several concerning indicators. "
                "Further investigation recommended."
            )
        else:
            lines.append(
                "Low risk indicators — standard due diligence still advised."
            )

        return " ".join(lines)

    # ── Section-text helper ───────────────────────────────────────────

    def _find_section_text(
        self, tender: TenderDocument, section: TenderSection
    ) -> Optional[str]:
        """Get combined text from all sections of a given type.

        Returns None if no sections of that type exist.
        """
        texts = [s.content for s in tender.sections if s.section == section]
        return "\n".join(texts) if texts else None

    # ── Individual check methods ──────────────────────────────────────

    def _check_timeline(
        self, tender: TenderDocument
    ) -> Optional[Tuple[FlaggedClause, RiskLevel]]:
        """Check if the bid-submission timeline is unreasonably short.

        Searches for explicit day-count references (e.g. '7 days') and
        cross-references publication/deadline dates when both are present.
        Supports both Gregorian (AD) and Bikram Sambat (BS) Nepali calendar dates.
        """
        text = self._find_section_text(tender, TenderSection.TIMELINE)
        if not text:
            text = tender.raw_text

        # Look for day-count mentions (handles English & Indonesian)
        day_patterns = re.findall(
            r"(\d+)\s*(?:day|days|hari|din)", text.lower()
        )
        if day_patterns:
            min_days = min(int(d) for d in day_patterns)
            if min_days <= 7:
                return (
                    FlaggedClause(
                        red_flag_id="timeline-too-short",
                        label="Suspiciously Short Timeline",
                        severity=Severity.CRITICAL,
                        description=(
                            f"Submission period of {min_days} days is "
                            f"critically short (normally 14-40 days)."
                        ),
                        risk_reason=(
                            "Very short deadlines exclude legitimate "
                            "bidders who need time to prepare, ensuring "
                            "only pre-selected insiders can bid. This is "
                            "the #1 rigging tactic in procurement fraud."
                        ),
                        location="Timeline section",
                        excerpt=f"{min_days} day(s) found in timeline",
                        suggestion=(
                            "Minimum bid periods are typically 14-25 days "
                            "for national, 40 days for international "
                            "procurement."
                        ),
                    ),
                    RiskLevel.RED,
                )
            elif min_days <= 14:
                return (
                    FlaggedClause(
                        red_flag_id="timeline-too-short",
                        label="Suspiciously Short Timeline",
                        severity=Severity.HIGH,
                        description=(
                            f"Submission period of {min_days} days "
                            "is below recommended minimum."
                        ),
                        risk_reason=(
                            "Abbreviated timelines discourage competition "
                            "and make it easier to steer contracts to a "
                            "known party."
                        ),
                        location="Timeline section",
                        excerpt=f"{min_days} day(s) found in timeline",
                        suggestion=(
                            "Verify if expedited procurement is "
                            "legally justified."
                        ),
                    ),
                    RiskLevel.RED,
                )

        # Cross-reference publication date vs. deadline date when both
        # are present as structured dates in the document.
        deadline_match = re.search(
            r"(?:deadline|closing|submission)[:\s]+"
            r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{1,2}-\d{1,2})",
            text,
            re.IGNORECASE,
        )
        publish_match = re.search(
            r"(?:published|issued|date)[:\s]+"
            r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{1,2}-\d{1,2})",
            text,
            re.IGNORECASE,
        )
        if deadline_match and publish_match:
            # Support multiple date formats: dd/mm/yyyy, yyyy-mm-dd, dd-mm-yyyy
            date_formats = ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"]
            pub = None
            deadline = None
            for fmt in date_formats:
                try:
                    pub = datetime.strptime(publish_match.group(1), fmt)
                    break
                except ValueError:
                    continue
            for fmt in date_formats:
                try:
                    deadline = datetime.strptime(deadline_match.group(1), fmt)
                    break
                except ValueError:
                    continue

            # ── Bikram Sambat conversion ─────────────────────────────
            # Nepali dates (BS) are typically ~56 years 8 months ahead of AD
            # e.g., BS 2082 ≈ AD 2025-2026. If year > 2070, likely BS.
            if pub and pub.year > 2070:
                pub = self._bs_to_ad(pub)
            if deadline and deadline.year > 2070:
                deadline = self._bs_to_ad(deadline)
            # ────────────────────────────────────────────────────────
            
            if pub and deadline:
                diff = (deadline - pub).days
                if diff < 7:
                    return (
                        FlaggedClause(
                            red_flag_id="timeline-too-short",
                            label="Suspiciously Short Timeline",
                            severity=Severity.CRITICAL,
                            description=(
                                f"Only {diff} days between publication "
                                f"and submission deadline "
                                f"(normally 14-40 days)."
                            ),
                            risk_reason=(
                                "Very short deadlines exclude legitimate "
                                "bidders who need time to prepare."
                            ),
                            location="Timeline section",
                            excerpt=(
                                f"{diff} days from publication to deadline"
                            ),
                            suggestion=(
                                "Minimum bid periods are typically "
                                "14-25 days for national, 40 days for "
                                "international procurement."
                            ),
                        ),
                        RiskLevel.RED,
                    )

        return None

    def _bs_to_ad(self, bs_date: datetime) -> datetime:
        """Convert Bikram Sambat date to Gregorian (AD) approximately.

        Uses the standard approximation: AD = BS - 56 years - 8 months - 17 days.
        This is accurate within ~1-2 days for most dates.

        For precise conversion, install nepali-datetime: pip install nepali-datetime
        """
        try:
            # Try precise conversion if nepali-datetime is available
            from nepali_datetime import date as nepali_date
            bs = nepali_date(bs_date.year, bs_date.month, bs_date.day)
            ad = bs.to_datetime_date()
            return datetime(ad.year, ad.month, ad.day)
        except ImportError:
            # Fallback: approximate conversion
            # BS 2082-01-01 ≈ AD 2025-04-14 (difference: -56y -8m -17d)
            from dateutil.relativedelta import relativedelta
            return bs_date - relativedelta(years=56, months=8, days=17)
        except Exception:
            # If conversion fails entirely, return original with warning
            return bs_date

    def _check_single_brand(
        self, tender: TenderDocument
    ) -> Optional[Tuple[FlaggedClause, RiskLevel]]:
        """Check for single-brand / tailored specification references.

        Flags specs that name a specific brand or model without an
        'or equivalent' qualifier.
        """
        text = self._find_section_text(tender, TenderSection.SPECIFICATION)
        if not text:
            return None

        text_lower = text.lower()
        brand_signals = [
            r"\b(tm|®|™|brand|model no[.:])\b",
            r"\b(or equivalent|or similar|or equal)\b",
        ]
        specific_brands = re.findall(
            r"(?:brand|make|model)[:\s]+(\w+)", text_lower
        )

        has_or_equivalent = any(
            re.search(signal, text_lower) for signal in brand_signals
        )

        if specific_brands and not has_or_equivalent:
            return (
                FlaggedClause(
                    red_flag_id="single-brand-spec",
                    label="Single Brand / Tailored Specification",
                    severity=Severity.HIGH,
                    description=(
                        f"Specification references specific brand(s): "
                        f"{', '.join(specific_brands[:3])} without "
                        f"'or equivalent' language."
                    ),
                    risk_reason=(
                        "Tailored specs lock out all other suppliers, "
                        "guaranteeing the contract goes to a specific "
                        "vendor. This is a classic bid-rigging technique "
                        "that eliminates competition entirely."
                    ),
                    location="Specification section",
                    excerpt=(
                        f"Found brand references: "
                        f"{', '.join(specific_brands[:3])}"
                    ),
                    suggestion=(
                        "Specifications should be generic/"
                        "performance-based. Brand-specific specs "
                        "restrict competition."
                    ),
                ),
                RiskLevel.RED,
            )

        return None

    def _check_budget_inflation(
        self, tender: TenderDocument
    ) -> Optional[Tuple[FlaggedClause, RiskLevel]]:
        """Check for budget inflation indicators.

        Looks for: large round numbers, missing cost breakdowns, and
        vague budget language.  Flags at 2+ indicators.
        """
        text = self._find_section_text(tender, TenderSection.BUDGET)
        if not text:
            text = tender.raw_text

        text_lower = text.lower()
        indicators = 0
        reasons = []

        # Round numbers in large amounts (e.g. NPR 50,000,000)
        if re.search(
            r"(?:rs\.?|npr|nrs|rp\.?|idr|usd|\$)\s*\d+[kmlb]?\s*[0-9]{6,}",
            text_lower,
        ):
            indicators += 1
            reasons.append(
                "Large round numbers suggest estimates without "
                "proper rate analysis"
            )

        # No cost breakdown or rate analysis present
        if not re.search(
            r"(?:breakdown|rate analysis|unit price|quantity|"
            r"bill of quantities|boq)",
            text_lower,
        ):
            indicators += 1
            reasons.append(
                "No cost breakdown or rate analysis provided"
            )

        # Vague budget language
        if re.search(
            r"(?:estimated|approx|about|around)\s*"
            r"(?:cost|budget|value)",
            text_lower,
        ):
            indicators += 1
            reasons.append(
                "Vague budget language without firm figures"
            )

        if indicators >= 2:
            return (
                FlaggedClause(
                    red_flag_id="budget-inflation",
                    label="Potential Budget Inflation",
                    severity=Severity.HIGH
                    if indicators >= 3
                    else Severity.MEDIUM,
                    description="; ".join(reasons),
                    risk_reason=(
                        "Inflated budgets create room for kickbacks, "
                        "overbilling, and embezzlement. Without a proper "
                        "cost breakdown, there is no way to verify funds "
                        "are legitimate."
                    ),
                    location="Budget section",
                    excerpt=text[:300] if len(text) > 300 else text,
                    suggestion=(
                        "Request detailed cost breakdown with unit rates "
                        "and quantities."
                    ),
                ),
                RiskLevel.YELLOW,
            )

        return None

    def _check_opaque_evaluation(
        self, tender: TenderDocument
    ) -> Optional[Tuple[FlaggedClause, RiskLevel]]:
        """Check if evaluation criteria are clear and specific.

        Marks a flag when criteria lack quantifiable scoring methodology
        or rely heavily on subjective wording.
        """
        text = self._find_section_text(
            tender, TenderSection.EVALUATION_CRITERIA
        )
        if not text:
            return None

        text_lower = text.lower()
        subjective_words = [
            "satisfactory",
            "acceptable",
            "appropriate",
            "adequate",
            "reasonable",
            "qualified",
            "suitable",
            "best",
        ]
        specific_indicators = [
            "points",
            "score",
            "weight",
            "percentage",
            "criteria",
            "methodology",
            "marking",
            "threshold",
            "passing",
        ]

        has_specific = any(w in text_lower for w in specific_indicators)
        has_subjective = sum(1 for w in subjective_words if w in text_lower)

        if not has_specific:
            return (
                FlaggedClause(
                    red_flag_id="opaque-evaluation",
                    label="Vague Evaluation Criteria",
                    severity=Severity.HIGH,
                    description=(
                        "Evaluation criteria lack specific scoring "
                        "weights or methodology."
                    ),
                    risk_reason=(
                        "Without published scoring criteria, there is no "
                        "way to hold evaluators accountable. The winning "
                        "bid can be chosen arbitrarily, enabling "
                        "favoritism and bribery."
                    ),
                    location="Evaluation Criteria section",
                    excerpt=text[:300] if len(text) > 300 else text,
                    suggestion=(
                        "Evaluation must include clear, quantifiable "
                        "criteria with assigned weights."
                    ),
                ),
                RiskLevel.RED,
            )

        if has_subjective >= 3 and not has_specific:
            return (
                FlaggedClause(
                    red_flag_id="opaque-evaluation",
                    label="Vague Evaluation Criteria",
                    severity=Severity.MEDIUM,
                    description=(
                        "Over-reliance on subjective evaluation language "
                        "without objective measures."
                    ),
                    risk_reason=(
                        "Subjective language like 'satisfactory' or "
                        "'acceptable' lets evaluators justify any choice, "
                        "masking bid-rigging behind vague assessment."
                    ),
                    location="Evaluation Criteria section",
                    excerpt=text[:300] if len(text) > 300 else text,
                    suggestion=(
                        "Replace subjective criteria with objective, "
                        "measurable indicators."
                    ),
                ),
                RiskLevel.YELLOW,
            )

        return None

    def _check_missing_section(
        self, tender: TenderDocument
    ) -> Optional[Tuple[FlaggedClause, RiskLevel]]:
        """Check if the evaluation criteria section is entirely missing.

        Falls back to raw-text keyword search when the LLM parser did
        not produce an evaluation section (e.g. during testing).
        """
        ev_sections = [
            s
            for s in tender.sections
            if s.section == TenderSection.EVALUATION_CRITERIA
        ]
        if ev_sections:
            return None

        # Fallback: search the raw text for evaluation headers/keywords
        raw_lower = tender.raw_text.lower()
        eval_headers = [
            r"section\s+\d+\s*[:–—-]\s*evaluation",
            r"evaluation criteria",
            r"evaluation method",
            r"marking scheme",
            r"scoring method",
            r"technical evaluation",
            r"financial evaluation",
            r"\bqbs\b",
            r"\bqcbs\b",
            r"\blcb\b",
            r"points?\s+system",
            r"weighted\s+criteria",
        ]
        found_header = any(re.search(p, raw_lower) for p in eval_headers)
        if found_header:
            return None

        return (
            FlaggedClause(
                red_flag_id="missing-evaluation-section",
                label="No Evaluation Criteria Section",
                severity=Severity.CRITICAL,
                description=(
                    "The tender document does not contain an evaluation "
                    "criteria section."
                ),
                risk_reason=(
                    "Hiding the evaluation criteria is the most extreme "
                    "red flag. Without transparency in how bids are "
                    "scored, corruption cannot be detected — the award "
                    "can be given to any bidder without accountability."
                ),
                location="Entire document",
                excerpt="No evaluation criteria section found",
                suggestion=(
                    "Every tender must publish clear evaluation criteria. "
                    "This omission is a serious procedural violation."
                ),
            ),
            RiskLevel.RED,
        )

    def _check_emergency(
        self, tender: TenderDocument
    ) -> Optional[Tuple[FlaggedClause, RiskLevel]]:
        """Check for emergency procurement signals without justification.

        Flags documents that mention 'emergency' or 'urgent' procurement
        but lack an accompanying justification.
        """
        text = tender.raw_text.lower()
        emergency_words = [
            "emergency",
            "urgent",
            "direct appointment",
            "penunjukan langsung",
            "immediate",
            "force majeure",
            "musibah",
            "darurat",
        ]
        justification_words = [
            "justification",
            "reason",
            "explanation",
            "alasan",
            "karena",
        ]

        found_emergency = [w for w in emergency_words if w in text]
        if found_emergency:
            has_justification = any(w in text for w in justification_words)
            if not has_justification:
                return (
                    FlaggedClause(
                        red_flag_id="emergency-keywords",
                        label="Emergency Procurement Without Justification",
                        severity=Severity.CRITICAL,
                        description=(
                            f"Document mentions emergency procurement "
                            f"({', '.join(found_emergency)}) but no "
                            f"justification provided."
                        ),
                        risk_reason=(
                            "Emergency procurement bypasses standard "
                            "competitive bidding, which is the primary "
                            "safeguard against corruption. Without "
                            "documented justification, it is a vehicle "
                            "for awarding contracts without oversight."
                        ),
                        location="Document body",
                        excerpt=f"Found: {', '.join(found_emergency)}",
                        suggestion=(
                            "Emergency procurement requires formal "
                            "declaration with specific justification. "
                            "Unjustified emergency procurement is a top "
                            "corruption indicator."
                        ),
                    ),
                    RiskLevel.RED,
                )
        return None

    def _check_vague_spec(
        self, tender: TenderDocument
    ) -> Optional[Tuple[FlaggedClause, RiskLevel]]:
        """Check for overly vague or placeholder specifications."""
        text = self._find_section_text(tender, TenderSection.SPECIFICATION)
        if not text:
            return None

        text_lower = text.lower()
        vagueness = [
            "to be determined",
            "tbd",
            "specification pending",
            "to be confirmed",
            "as per standard",
            "general specification",
            "as per requirement",
        ]
        found_vague = [w for w in vagueness if w in text_lower]

        if found_vague and len(text) < 500:
            return (
                FlaggedClause(
                    red_flag_id="vague-spec",
                    label="Vague or Copy-Pasted Specifications",
                    severity=Severity.MEDIUM,
                    description=(
                        "Technical specifications are vague or contain "
                        "placeholder language."
                    ),
                    risk_reason=(
                        "Vague specs make it impossible to judge whether "
                        "the delivered work meets requirements. This lets "
                        "contractors deliver substandard work and still "
                        "claim compliance, a common corruption pattern in "
                        "public works."
                    ),
                    location="Specification section",
                    excerpt=f"Found vague terms: {', '.join(found_vague)}",
                    suggestion=(
                        "Specifications should be detailed, measurable, "
                        "and verifiable."
                    ),
                ),
                RiskLevel.YELLOW,
            )

        return None

    def _check_conflict_interest(
        self, tender: TenderDocument
    ) -> Optional[Tuple[FlaggedClause, RiskLevel]]:
        """Check for conflict-of-interest / recusal provisions in terms."""
        text = self._find_section_text(tender, TenderSection.TERMS)
        if not text:
            return None

        text_lower = text.lower()
        coi_keywords = [
            "conflict of interest",
            "recuse",
            "disqualification",
            "pecuniary",
            "benturan kepentingan",
            "undue influence",
            "cooling-off",
        ]

        found_coi = [w for w in coi_keywords if w in text_lower]
        if not found_coi:
            return (
                FlaggedClause(
                    red_flag_id="conflict-interest-signals",
                    label="Potential Conflict of Interest Signals",
                    severity=Severity.HIGH,
                    description=(
                        "No conflict of interest or recusal provisions "
                        "found in terms."
                    ),
                    risk_reason=(
                        "Without conflict of interest rules, procurement "
                        "officials can award contracts to their own "
                        "relatives, business partners, or shell companies "
                        "without legal consequence."
                    ),
                    location="Terms and Conditions section",
                    excerpt="No conflict of interest provisions detected",
                    suggestion=(
                        "Standard procurement documents must include "
                        "conflict of interest clauses and recusal "
                        "requirements."
                    ),
                ),
                RiskLevel.YELLOW,
            )

        return None

    def _check_unusual_terms(
        self, tender: TenderDocument
    ) -> Optional[Tuple[FlaggedClause, RiskLevel]]:
        """Check for unusually one-sided contract terms.

        Flags terms that waive standard protections such as penalties,
        performance bonds, or inspection rights.
        """
        text = self._find_section_text(tender, TenderSection.TERMS)
        if not text:
            return None

        text_lower = text.lower()
        unusual = [
            "no penalty",
            "no liquidated damages",
            "no performance bond",
            "waive",
            "indemnify",
            "no inspection",
            "no supervision",
            "release from liability",
        ]

        found_unusual = [w for w in unusual if w in text_lower]
        if len(found_unusual) >= 2:
            return (
                FlaggedClause(
                    red_flag_id="unusual-contract-terms",
                    label="Unusual or One-Sided Contract Terms",
                    severity=Severity.MEDIUM,
                    description=(
                        f"Contract terms contain potentially problematic "
                        f"provisions: {', '.join(found_unusual)}"
                    ),
                    risk_reason=(
                        "One-sided terms that waive penalties, guarantees, "
                        "or inspections remove all consequences for "
                        "non-performance. This enables contractors to take "
                        "the money and deliver nothing, a hallmark of "
                        "procurement fraud."
                    ),
                    location="Terms and Conditions section",
                    excerpt=f"Found: {', '.join(found_unusual)}",
                    suggestion=(
                        "Standard procurement contracts should include "
                        "penalty clauses, performance guarantees, and "
                        "inspection rights."
                    ),
                ),
                RiskLevel.YELLOW,
            )

        return None
