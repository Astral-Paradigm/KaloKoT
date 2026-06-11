"""Vendor/Contractor Intelligence — cross-reference bidders against risk indicators.

PRD Layer 1: cross-reference winning bidders against past awards,
shell company registries, and politically exposed persons (PEPs).

For MVP this uses rule-based detection (name patterns, registration
age heuristics, keyword signals) with no external API dependency.
Phase 2 adds live OpenCorporates / PEP data integration.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from ..shared.models import RiskLevel, Severity


# ── Shell Company Indicators ────────────────────────────────────────

SHELL_KEYWORDS: List[str] = [
    "enterprises", "trading", "general trading", "import export",
    "services", "consultancy", "logistics", "suppliers",
]

SHELL_PATTERNS: List[str] = [
    r"\b(offshore|shell|nominee)\s+(company|entity|firm)\b",
    r"\b(registered\s+agent|virtual\s+office)\b",
    r"\b(P\.?O\.?\s*Box)\s+\d+",
]

RECENT_REGISTRATION_DAYS = 180  # companies registered < 180 days ago are suspicious


# ── PEP Name Signals ────────────────────────────────────────────────

PEP_TITLE_SIGNALS: List[str] = [
    "minister", "secretary", "mp", "member of parliament",
    "hon'ble", "honorable", "ex-minister", "former minister",
    "mayor", "chairperson", "commissioner", "advisor",
]

PEP_SURNAME_DATABASE: List[str] = [
    # Nepal — common political surnames (illustrative; Phase 2 adds live PEP feed)
    "ojha", "thapa", "bhattarai", "pokharel", "khanal",
    "koirala", "neupane", "aryal", "regmi", "sharma",
    "pandey", "bhandari", "sigdel", "basnet", "khadka",
    "dahal", "karki", "subedi", "chapagain",
]


# ── Vendor Risk Score ────────────────────────────────────────────────

class VendorProfile:
    """Structured vendor/bidder profile for risk assessment."""

    def __init__(
        self,
        name: str,
        registration_number: Optional[str] = None,
        registration_date: Optional[str] = None,
        directors: Optional[List[str]] = None,
        address: Optional[str] = None,
    ):
        self.name = name
        self.registration_number = registration_number
        self.registration_date = registration_date
        self.directors = directors or []
        self.address = address

    def __repr__(self) -> str:
        return f"VendorProfile(name={self.name!r})"


class VendorRiskFlag:
    """A specific risk indicator for a vendor."""

    def __init__(self, label: str, severity: Severity, detail: str, category: str):
        self.label = label
        self.severity = severity
        self.detail = detail
        self.category = category  # "shell", "pep", "registration", "past_award"

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "severity": self.severity.value,
            "detail": self.detail,
            "category": self.category,
        }


class VendorIntelligence:
    """Analyse vendor/bidder risk profiles."""

    def __init__(self, known_shells: Optional[List[str]] = None):
        self.known_shells = known_shells or []

    def assess(self, vendor: VendorProfile) -> Tuple[RiskLevel, List[VendorRiskFlag]]:
        """Run all checks and return overall risk + flagged items."""
        flags: List[VendorRiskFlag] = []

        flags.extend(self._check_shell_indicators(vendor))
        flags.extend(self._check_pep_connection(vendor))
        flags.extend(self._check_registration_age(vendor))
        flags.extend(self._check_known_shells(vendor))

        if any(f.severity in (Severity.CRITICAL, Severity.HIGH) for f in flags):
            overall = RiskLevel.RED
        elif any(f.severity == Severity.MEDIUM for f in flags):
            overall = RiskLevel.YELLOW
        else:
            overall = RiskLevel.GREEN

        return overall, flags

    def _check_shell_indicators(self, vendor: VendorProfile) -> List[VendorRiskFlag]:
        """Detect shell company indicators from name, address, and patterns."""
        flags: List[VendorRiskFlag] = []
        name_lower = vendor.name.lower()

        # PO Box only — no physical address
        if vendor.address:
            if re.search(r"\bP\.?O\.?\s*Box\s+\d+", vendor.address, re.IGNORECASE):
                flags.append(VendorRiskFlag(
                    label="PO Box Address Only",
                    severity=Severity.MEDIUM,
                    detail=f"Vendor {vendor.name} lists only a PO Box as address.",
                    category="shell",
                ))

        # Generic trading / services suffix with no sector specificity
        generic_count = sum(1 for kw in SHELL_KEYWORDS if kw in name_lower)
        if generic_count >= 2:
            flags.append(VendorRiskFlag(
                label="Generic Company Name — Possible Shell",
                severity=Severity.MEDIUM,
                detail=f"Company name '{vendor.name}' contains multiple generic terms.",
                category="shell",
            ))

        # Detect shell patterns in name
        for pat in SHELL_PATTERNS:
            if re.search(pat, name_lower):
                flags.append(VendorRiskFlag(
                    label="Shell Pattern Detected in Name",
                    severity=Severity.HIGH,
                    detail=f"Name '{vendor.name}' matches shell indicator pattern: {pat}",
                    category="shell",
                ))

        return flags

    def _check_pep_connection(self, vendor: VendorProfile) -> List[VendorRiskFlag]:
        """Check if vendor name or directors match PEP signals."""
        flags: List[VendorRiskFlag] = []
        all_names = [vendor.name] + list(vendor.directors)

        for name in all_names:
            name_lower = name.lower()

            # Title-based PEP signals
            for title in PEP_TITLE_SIGNALS:
                if title in name_lower:
                    flags.append(VendorRiskFlag(
                        label="Politically Exposed Person Signal",
                        severity=Severity.HIGH,
                        detail=f"Name '{name}' contains PEP title indicator '{title}'.",
                        category="pep",
                    ))

            # Surname-based matching (heuristic)
            for surname in PEP_SURNAME_DATABASE:
                if surname in name_lower:
                    flags.append(VendorRiskFlag(
                        label="Surname Matches Known Political Family",
                        severity=Severity.LOW,
                        detail=f"Name '{name}' shares surname '{surname}' with known political figures.",
                        category="pep",
                    ))

        return flags

    def _check_registration_age(self, vendor: VendorProfile) -> List[VendorRiskFlag]:
        """Flag recently registered companies."""
        flags: List[VendorRiskFlag] = []
        if not vendor.registration_date:
            return flags

        try:
            reg_date = datetime.strptime(vendor.registration_date, "%Y-%m-%d")
        except (ValueError, TypeError):
            return flags

        age_days = (datetime.now() - reg_date).days
        if age_days < RECENT_REGISTRATION_DAYS:
            flags.append(VendorRiskFlag(
                label="Recently Registered Company",
                severity=Severity.MEDIUM,
                detail=(
                    f"Company registered {age_days} days ago "
                    f"(threshold: {RECENT_REGISTRATION_DAYS} days). "
                    "May be a front for bid rigging."
                ),
                category="registration",
            ))

        return flags

    def _check_known_shells(self, vendor: VendorProfile) -> List[VendorRiskFlag]:
        """Check against known shell company database."""
        flags: List[VendorRiskFlag] = []
        name_lower = vendor.name.strip().lower()

        for shell in self.known_shells:
            if shell.lower() in name_lower or name_lower in shell.lower():
                flags.append(VendorRiskFlag(
                    label="Known Shell Entity",
                    severity=Severity.CRITICAL,
                    detail=f"Vendor '{vendor.name}' matches or is affiliated with known shell entity '{shell}'.",
                    category="shell",
                ))

        return flags
