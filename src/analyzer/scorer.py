"""Corruption risk scoring for tender documents."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from ..shared.models import (
    TenderDocument, TenderSection, FlaggedClause, Severity,
    RiskReport, RiskLevel,
)


class RiskScorer:
    """Rule-based + LLM-assisted corruption risk scorer."""

    def __init__(self):
        # Default scoring rules — these are jurisdiction-independent heuristics
        self.rules = self._default_rules()

    def _default_rules(self) -> List[dict]:
        return [
            {
                "id": "timeline-too-short",
                "label": "Suspiciously Short Timeline",
                "section": TenderSection.TIMELINE,
                "severity": Severity.HIGH,
                "description": "Bid submission period appears unusually short, limiting competition.",
                "check": self._check_timeline,
            },
            {
                "id": "single-brand-spec",
                "label": "Single Brand / Tailored Specification",
                "section": TenderSection.SPECIFICATION,
                "severity": Severity.HIGH,
                "description": "Technical specifications reference a specific brand, model, or appear tailored to one supplier.",
                "check": self._check_single_brand,
            },
            {
                "id": "budget-inflation",
                "label": "Potential Budget Inflation",
                "section": TenderSection.BUDGET,
                "severity": Severity.MEDIUM,
                "description": "Budget data shows potential inflation indicators: vague cost breakdown, no rate analysis, round numbers.",
                "check": self._check_budget_inflation,
            },
            {
                "id": "opaque-evaluation",
                "label": "Vague Evaluation Criteria",
                "section": TenderSection.EVALUATION_CRITERIA,
                "severity": Severity.HIGH,
                "description": "Evaluation criteria are missing, vague, or use subjective language.",
                "check": self._check_opaque_evaluation,
            },
            {
                "id": "missing-evaluation-section",
                "label": "No Evaluation Criteria Section",
                "section": TenderSection.EVALUATION_CRITERIA,
                "severity": Severity.CRITICAL,
                "description": "No evaluation methodology published — impossible to verify fair award.",
                "check": self._check_missing_section,
            },
            {
                "id": "emergency-keywords",
                "label": "Emergency Procurement Without Justification",
                "section": TenderSection.DETAILS,
                "severity": Severity.CRITICAL,
                "description": "Emergency/direct procurement mentioned without explanation of the emergency.",
                "check": self._check_emergency,
            },
            {
                "id": "vague-spec",
                "label": "Vague or Copy-Pasted Specifications",
                "section": TenderSection.SPECIFICATION,
                "severity": Severity.MEDIUM,
                "description": "Technical specs are vague, generic, or appear copy-pasted from another document.",
                "check": self._check_vague_spec,
            },
            {
                "id": "conflict-interest-signals",
                "label": "Potential Conflict of Interest Signals",
                "section": TenderSection.TERMS,
                "severity": Severity.HIGH,
                "description": "Terms lack conflict of interest declaration or recusal requirements.",
                "check": self._check_conflict_interest,
            },
            {
                "id": "unusual-contract-terms",
                "label": "Unusual or One-Sided Contract Terms",
                "section": TenderSection.TERMS,
                "severity": Severity.MEDIUM,
                "description": "Contract terms appear unusually favorable to contractor or lack standard safeguards.",
                "check": self._check_unusual_terms,
            },
        ]

    def score(self, tender: TenderDocument) -> RiskReport:
        """Run all rules against a tender document and produce a risk report."""
        flagged: List[FlaggedClause] = []
        section_scores: Dict[str, RiskLevel] = {}

        # Track which sections got flagged
        flagged_sections = set()

        for rule in self.rules:
            result = rule["check"](tender)
            if result:
                clause, section_risk_override = result
                flagged.append(clause)
                flagged_sections.add(rule["section"].value)
                section_scores[rule["section"].value] = section_risk_override

        # Assign section scores
        for section in TenderSection:
            if section.value not in section_scores:
                section_scores[section.value] = RiskLevel.GREEN

        # Overall risk: CRITICAL if any critical flag, RED if multiple high, YELLOW if any medium
        overall = self._compute_overall(flagged)

        summary = self._generate_summary(flagged, overall)

        return RiskReport(
            tender=tender,
            overall_risk=overall,
            section_scores=section_scores,
            flagged_clauses=flagged,
            summary=summary,
        )

    def _compute_overall(self, flagged: List[FlaggedClause]) -> RiskLevel:
        critical = any(f.severity == Severity.CRITICAL for f in flagged)
        high_count = sum(1 for f in flagged if f.severity == Severity.HIGH)
        medium_count = sum(1 for f in flagged if f.severity == Severity.MEDIUM)

        if critical or high_count >= 3:
            return RiskLevel.RED
        if high_count >= 1 or medium_count >= 2:
            return RiskLevel.YELLOW
        return RiskLevel.GREEN

    def _generate_summary(self, flagged: List[FlaggedClause],
                          overall: RiskLevel) -> str:
        if not flagged:
            return "No red flags detected. The tender appears procedurally sound."
        total = len(flagged)
        critical = sum(1 for f in flagged if f.severity == Severity.CRITICAL)
        high = sum(1 for f in flagged if f.severity == Severity.HIGH)
        medium = sum(1 for f in flagged if f.severity == Severity.MEDIUM)

        lines = [
            f"Risk Level: {overall.upper()}",
            f"Total red flags: {total} ({critical} critical, {high} high, {medium} medium)",
        ]
        if overall == RiskLevel.RED:
            lines.append("This tender shows strong indicators of corruption risk. Consider legal counsel.")
        elif overall == RiskLevel.YELLOW:
            lines.append("This tender has several concerning indicators. Further investigation recommended.")
        else:
            lines.append("Low risk indicators — standard due diligence still advised.")

        return " ".join(lines)

    # --- Individual check methods ---

    def _find_section_text(self, tender: TenderDocument, section: TenderSection) -> Optional[str]:
        """Get combined text from all sections of a given type."""
        texts = [s.content for s in tender.sections if s.section == section]
        return "\n".join(texts) if texts else None

    def _check_timeline(self, tender: TenderDocument) -> Optional[Tuple[FlaggedClause, RiskLevel]]:
        """Check if timeline is unreasonably short."""
        text = self._find_section_text(tender, TenderSection.TIMELINE)
        if not text:
            text = tender.raw_text

        # Look for day mentions
        day_patterns = re.findall(r'(\d+)\s*(?:day|days|hari|din)', text.lower())
        if day_patterns:
            min_days = min(int(d) for d in day_patterns)
            if min_days <= 7:
                return FlaggedClause(
                    red_flag_id="timeline-too-short",
                    label="Suspiciously Short Timeline",
                    severity=Severity.CRITICAL,
                    description=f"Submission period of {min_days} days is critically short (normally 14-40 days).",
                    location="Timeline section",
                    excerpt=f"{min_days} day(s) found in timeline",
                    suggestion="Minimum bid periods are typically 14-25 days for national, 40 days for international procurement.",
                ), RiskLevel.RED
            elif min_days <= 14:
                return FlaggedClause(
                    red_flag_id="timeline-too-short",
                    label="Suspiciously Short Timeline",
                    severity=Severity.HIGH,
                    description=f"Submission period of {min_days} days is below recommended minimum.",
                    location="Timeline section",
                    excerpt=f"{min_days} day(s) found in timeline",
                    suggestion="Verify if expedited procurement is legally justified.",
                ), RiskLevel.RED

        # Check for very short deadlines mentioned as dates
        deadline_match = re.search(r'(?:deadline|closing|submission)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', text)
        publish_match = re.search(r'(?:published|issued|date)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', text)
        if deadline_match and publish_match:
            try:
                pub = datetime.strptime(publish_match.group(1), "%d/%m/%Y")
                deadline = datetime.strptime(deadline_match.group(1), "%d/%m/%Y")
                diff = (deadline - pub).days
                if diff < 7:
                    return FlaggedClause(...), RiskLevel.RED
            except ValueError:
                pass

        return None

    def _check_single_brand(self, tender: TenderDocument) -> Optional[Tuple[FlaggedClause, RiskLevel]]:
        """Check for single brand/model references in specs."""
        text = self._find_section_text(tender, TenderSection.SPECIFICATION)
        if not text:
            return None

        text_lower = text.lower()
        brand_signals = [
            r'\b(tm|®|™|brand|model no[.:])\b',
            r'\b(or equivalent|or similar|or equal)\b',
        ]
        specific_brands = re.findall(r'(?:brand|make|model)[:\s]+(\w+)', text_lower)

        has_or_equivalent = False
        for signal in brand_signals:
            if re.search(signal, text_lower):
                has_or_equivalent = True

        if specific_brands and not has_or_equivalent:
            return FlaggedClause(
                red_flag_id="single-brand-spec",
                label="Single Brand / Tailored Specification",
                severity=Severity.HIGH,
                description=f"Specification references specific brand(s): {', '.join(specific_brands[:3])} without 'or equivalent' language.",
                location="Specification section",
                excerpt=f"Found brand references: {', '.join(specific_brands[:3])}",
                suggestion="Specifications should be generic/performance-based. Brand-specific specs restrict competition.",
            ), RiskLevel.RED

        return None

    def _check_budget_inflation(self, tender: TenderDocument) -> Optional[Tuple[FlaggedClause, RiskLevel]]:
        """Check for budget inflation indicators."""
        text = self._find_section_text(tender, TenderSection.BUDGET)
        if not text:
            text = tender.raw_text

        text_lower = text.lower()
        indicators = 0
        reasons = []

        # Round numbers in large amounts
        if re.search(r'(?:rs\.?|npr|nrs|rp\.?|idr|usd|$)\s*\d+[kmlb]?\s*[0-9]{6,}', text_lower):
            indicators += 1
            reasons.append("Large round numbers suggest estimates without proper rate analysis")

        # No cost breakdown
        if not re.search(r'(?:breakdown|rate analysis|unit price|quantity|bill of quantities|boq)', text_lower):
            indicators += 1
            reasons.append("No cost breakdown or rate analysis provided")

        # Vague budget language
        if re.search(r'(?:estimated|approx|about|around)\s*(?:cost|budget|value)', text_lower):
            indicators += 1
            reasons.append("Vague budget language without firm figures")

        if indicators >= 2:
            return FlaggedClause(
                red_flag_id="budget-inflation",
                label="Potential Budget Inflation",
                severity=Severity.HIGH if indicators >= 3 else Severity.MEDIUM,
                description="; ".join(reasons),
                location="Budget section",
                excerpt=text[:300] if len(text) > 300 else text,
                suggestion="Request detailed cost breakdown with unit rates and quantities.",
            ), RiskLevel.YELLOW

        return None

    def _check_opaque_evaluation(self, tender: TenderDocument) -> Optional[Tuple[FlaggedClause, RiskLevel]]:
        """Check if evaluation criteria are clear and specific."""
        text = self._find_section_text(tender, TenderSection.EVALUATION_CRITERIA)
        if not text:
            return None

        text_lower = text.lower()
        subjective_words = [
            "satisfactory", "acceptable", "appropriate", "adequate",
            "reasonable", "qualified", "suitable", "best",
        ]
        specific_indicators = [
            "points", "score", "weight", "percentage", "criteria",
            "methodology", "marking", "threshold", "passing",
        ]

        has_specific = any(w in text_lower for w in specific_indicators)
        has_subjective = sum(1 for w in subjective_words if w in text_lower)

        if not has_specific:
            return FlaggedClause(
                red_flag_id="opaque-evaluation",
                label="Vague Evaluation Criteria",
                severity=Severity.HIGH,
                description="Evaluation criteria lack specific scoring weights or methodology.",
                location="Evaluation Criteria section",
                excerpt=text[:300] if len(text) > 300 else text,
                suggestion="Evaluation must include clear, quantifiable criteria with assigned weights.",
            ), RiskLevel.RED

        if has_subjective >= 3 and not has_specific:
            return FlaggedClause(
                red_flag_id="opaque-evaluation",
                label="Vague Evaluation Criteria",
                severity=Severity.MEDIUM,
                description="Over-reliance on subjective evaluation language without objective measures.",
                location="Evaluation Criteria section",
                excerpt=text[:300] if len(text) > 300 else text,
                suggestion="Replace subjective criteria with objective, measurable indicators.",
            ), RiskLevel.YELLOW

        return None

    def _check_missing_section(self, tender: TenderDocument) -> Optional[Tuple[FlaggedClause, RiskLevel]]:
        """Check if evaluation criteria section is entirely missing.

        Falls back to raw text search if no sections were parsed (e.g.
        when the LLM parser was skipped during testing).
        """
        ev_sections = [s for s in tender.sections if s.section == TenderSection.EVALUATION_CRITERIA]
        if ev_sections:
            return None

        # Fallback: check raw text for evaluation criteria headers/keywords
        raw_lower = tender.raw_text.lower()
        eval_headers = [
            r"section\s+\d+\s*[:\-–—]\s*evaluation",
            r"evaluation criteria",
            r"evaluation method",
            r"marking scheme",
            r"scoring method",
            r"technical evaluation",
            r"financial evaluation",
            r"qbs\b", r"qcbs\b", r"lcb\b",
            r"points?\s+system",
            r"weighted\s+criteria",
        ]
        found_header = any(re.search(p, raw_lower) for p in eval_headers)
        if found_header:
            return None

        return FlaggedClause(
            red_flag_id="missing-evaluation-section",
            label="No Evaluation Criteria Section",
            severity=Severity.CRITICAL,
            description="The tender document does not contain an evaluation criteria section.",
            location="Entire document",
            excerpt="No evaluation criteria section found",
            suggestion="Every tender must publish clear evaluation criteria. This omission is a serious procedural violation.",
        ), RiskLevel.RED

    def _check_emergency(self, tender: TenderDocument) -> Optional[Tuple[FlaggedClause, RiskLevel]]:
        """Check for emergency procurement signals."""
        text = tender.raw_text.lower()
        emergency_words = ["emergency", "urgent", "direct appointment", "penunjukan langsung",
                           "immediate", "force majeure", "musibah", "darurat"]
        justification_words = ["justification", "reason", "explanation", "alasan", "karena"]

        found_emergency = [w for w in emergency_words if w in text]
        if found_emergency:
            has_justification = any(w in text for w in justification_words)
            if not has_justification:
                return FlaggedClause(
                    red_flag_id="emergency-keywords",
                    label="Emergency Procurement Without Justification",
                    severity=Severity.CRITICAL,
                    description=f"Document mentions emergency procurement ({', '.join(found_emergency)}) but no justification provided.",
                    location="Document body",
                    excerpt=f"Found: {', '.join(found_emergency)}",
                    suggestion="Emergency procurement requires formal declaration with specific justification. Unjustified emergency procurement is a top corruption indicator.",
                ), RiskLevel.RED
        return None

    def _check_vague_spec(self, tender: TenderDocument) -> Optional[Tuple[FlaggedClause, RiskLevel]]:
        """Check for overly vague specifications."""
        text = self._find_section_text(tender, TenderSection.SPECIFICATION)
        if not text:
            return None

        text_lower = text.lower()
        vagueness = ["to be determined", "tbd", "specification pending", "to be confirmed",
                      "as per standard", "general specification", "as per requirement"]
        found_vague = [w for w in vagueness if w in text_lower]

        if found_vague and len(text) < 500:
            return FlaggedClause(
                red_flag_id="vague-spec",
                label="Vague or Copy-Pasted Specifications",
                severity=Severity.MEDIUM,
                description="Technical specifications are vague or contain placeholder language.",
                location="Specification section",
                excerpt=f"Found vague terms: {', '.join(found_vague)}",
                suggestion="Specifications should be detailed, measurable, and verifiable.",
            ), RiskLevel.YELLOW

        return None

    def _check_conflict_interest(self, tender: TenderDocument) -> Optional[Tuple[FlaggedClause, RiskLevel]]:
        """Check for conflict of interest provisions."""
        text = self._find_section_text(tender, TenderSection.TERMS)
        if not text:
            return None

        text_lower = text.lower()
        coi_keywords = ["conflict of interest", "recuse", "disqualification", "pecuniary",
                        "benturan kepentingan", "undue influence", "cooling-off"]

        found_coi = [w for w in coi_keywords if w in text_lower]
        if not found_coi:
            return FlaggedClause(
                red_flag_id="conflict-interest-signals",
                label="Potential Conflict of Interest Signals",
                severity=Severity.HIGH,
                description="No conflict of interest or recusal provisions found in terms.",
                location="Terms and Conditions section",
                excerpt="No conflict of interest provisions detected",
                suggestion="Standard procurement documents must include conflict of interest clauses and recusal requirements.",
            ), RiskLevel.YELLOW

        return None

    def _check_unusual_terms(self, tender: TenderDocument) -> Optional[Tuple[FlaggedClause, RiskLevel]]:
        """Check for unusually one-sided contract terms."""
        text = self._find_section_text(tender, TenderSection.TERMS)
        if not text:
            return None

        text_lower = text.lower()
        unusual = ["no penalty", "no liquidated damages", "no performance bond",
                   "waive", "indemnify", "no inspection", "no supervision",
                   "release from liability"]

        found_unusual = [w for w in unusual if w in text_lower]
        if len(found_unusual) >= 2:
            return FlaggedClause(
                red_flag_id="unusual-contract-terms",
                label="Unusual or One-Sided Contract Terms",
                severity=Severity.MEDIUM,
                description=f"Contract terms contain potentially problematic provisions: {', '.join(found_unusual)}",
                location="Terms and Conditions section",
                excerpt=f"Found: {', '.join(found_unusual)}",
                suggestion="Standard procurement contracts should include penalty clauses, performance guarantees, and inspection rights.",
            ), RiskLevel.YELLOW

        return None
