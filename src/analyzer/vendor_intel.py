"""Vendor/Contractor Intelligence — cross-reference bidders against risk indicators.

PRD Layer 1: cross-reference winning bidders against past awards,
shell company registries, and politically exposed persons (PEPs).

For MVP this uses rule-based detection (name patterns, registration
age heuristics, keyword signals) with no external API dependency.
Phase 2 adds live OpenCorporates / PEP data integration.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import List, Optional, Tuple

from ..shared.models import RiskLevel, Severity


# ── Shell Company Indicators ────────────────────────────────────────

SHELL_KEYWORDS: List[str] = [
    "enterprises",
    "trading",
    "general trading",
    "import export",
    "services",
    "consultancy",
    "logistics",
    "suppliers",
]

SHELL_PATTERNS: List[str] = [
    r"\b(offshore|shell|nominee)\s+(company|entity|firm)\b",
    r"\b(registered\s+agent|virtual\s+office)\b",
    r"\b(P\.?O\.?\s*Box)\s+\d+",
]

# Companies registered fewer than this many days ago are flagged as recent
RECENT_REGISTRATION_DAYS = 180


# ── PEP Name Signals ────────────────────────────────────────────────
# Loaded dynamically from jurisdiction YAML to avoid hardcoding per-country data.
# See docs/legal/<jurisdiction>.yaml under meta.pep_indicators.


# ── Vendor Model & Risk Assessment ──────────────────────────────────

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
    """A specific risk indicator for a vendor.

    Attributes:
        label: Short human-readable name (e.g. "PO Box Address Only").
        severity: One of LOW / MEDIUM / HIGH / CRITICAL.
        detail: Longer explanation of the finding.
        category: One of "shell", "pep", "registration", "past_award".
    """

    def __init__(
        self, label: str, severity: Severity, detail: str, category: str
    ):
        self.label = label
        self.severity = severity
        self.detail = detail
        self.category = category

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "severity": self.severity.value,
            "detail": self.detail,
            "category": self.category,
        }


class VendorIntelligence:
    """Analyse vendor/bidder risk profiles.

    Args:
        known_shells: Optional list of known shell-entity names to
            cross-reference during assessment.
        loader: Optional JurisdictionLoader to load PEP indicators from YAML.
    """

    def __init__(
        self, known_shells: Optional[List[str]] = None, loader=None
    ):
        self.known_shells = known_shells or []
        self._loader = loader
        self._pep_title_signals: List[str] = []
        self._pep_surnames: List[str] = []
        self._load_pep_data()

    def assess(
        self, vendor: VendorProfile
    ) -> Tuple[RiskLevel, List[VendorRiskFlag]]:
        """Run all checks against a vendor profile and produce a risk verdict.

        Args:
            vendor: The VendorProfile to assess.

        Returns:
            A tuple of (overall_risk_level, list_of_risk_flags).
        """
        flags: List[VendorRiskFlag] = []

        flags.extend(self._check_shell_indicators(vendor))
        flags.extend(self._check_pep_connection(vendor))
        flags.extend(self._check_registration_age(vendor))
        flags.extend(self._check_known_shells(vendor))

        # Aggregate: any CRITICAL or HIGH flag → RED;
        # any MEDIUM → YELLOW; otherwise GREEN.
        if any(
            f.severity in (Severity.CRITICAL, Severity.HIGH)
            for f in flags
        ):
            overall = RiskLevel.RED
        elif any(f.severity == Severity.MEDIUM for f in flags):
            overall = RiskLevel.YELLOW
        else:
            overall = RiskLevel.GREEN

        return overall, flags

    def _load_pep_data(self) -> None:
        """Load PEP indicators from jurisdiction YAML or fall back to defaults."""
        if self._loader is not None:
            try:
                from ..shared.models import JurisdictionCode
                data = self._loader.load_yaml(JurisdictionCode.NEPAL)
                meta = data.get("meta", {})
                pep = meta.get("pep_indicators", {})
                self._pep_title_signals = [s.lower() for s in pep.get("title_signals", [])]
                self._pep_surnames = [s.lower() for s in pep.get("surname_database", [])]
            except Exception:
                pass
        # Fallback defaults if YAML not available
        if not self._pep_title_signals:
            self._pep_title_signals = [
                "minister", "secretary", "mp", "member of parliament",
                "hon'ble", "honorable", "ex-minister", "former minister",
                "mayor", "chairperson", "commissioner", "advisor",
            ]
        if not self._pep_surnames:
            self._pep_surnames = [
                "ojha", "thapa", "bhattarai", "pokharel", "khanal",
                "koirala", "neupane", "aryal", "regmi", "sharma",
                "pandey", "bhandari", "sigdel", "basnet", "khadka",
                "dahal", "karki", "subedi", "chapagain",
            ]

    # ── Individual checks ───────────────────────────────────────────

    def _check_shell_indicators(
        self, vendor: VendorProfile
    ) -> List[VendorRiskFlag]:
        """Detect shell company indicators from name, address, and patterns.

        Checks for:
        - PO-box-only addresses (no physical location)
        - Generic company names with multiple vague keywords
        - Known shell phrases (offshore, nominee, registered agent, etc.)
        """
        flags: List[VendorRiskFlag] = []
        name_lower = vendor.name.lower()

        # PO Box only — no physical street address
        if vendor.address and re.search(
            r"\bP\.?O\.?\s*Box\s+\d+", vendor.address, re.IGNORECASE
        ):
            flags.append(
                VendorRiskFlag(
                    label="PO Box Address Only",
                    severity=Severity.MEDIUM,
                    detail=(
                        f"Vendor {vendor.name} lists only a PO Box "
                        "as address."
                    ),
                    category="shell",
                )
            )

        # Generic trading/services suffix with no sector specificity
        generic_count = sum(
            1 for kw in SHELL_KEYWORDS if kw in name_lower
        )
        if generic_count >= 2:
            flags.append(
                VendorRiskFlag(
                    label="Generic Company Name — Possible Shell",
                    severity=Severity.MEDIUM,
                    detail=(
                        f"Company name '{vendor.name}' contains "
                        "multiple generic terms."
                    ),
                    category="shell",
                )
            )

        # Regex-based shell patterns in the company name
        for pat in SHELL_PATTERNS:
            if re.search(pat, name_lower):
                flags.append(
                    VendorRiskFlag(
                        label="Shell Pattern Detected in Name",
                        severity=Severity.HIGH,
                        detail=(
                            f"Name '{vendor.name}' matches shell "
                            f"indicator pattern: {pat}"
                        ),
                        category="shell",
                    )
                )

        return flags

    def _check_pep_connection(
        self, vendor: VendorProfile
    ) -> List[VendorRiskFlag]:
        """Check if vendor name or directors match PEP signals.

        Two-pass approach:
        1. Title-based matching (e.g. 'Minister', 'MP', 'Honorable').
        2. Surname-based heuristic matching against known political families.
        """
        flags: List[VendorRiskFlag] = []
        all_names = [vendor.name] + list(vendor.directors)

        for name in all_names:
            name_lower = name.lower()

            # Title-based PEP signals (e.g. "Dr. Minister X")
            for title in self._pep_title_signals:
                if title in name_lower:
                    flags.append(
                        VendorRiskFlag(
                            label="Politically Exposed Person Signal",
                            severity=Severity.HIGH,
                            detail=(
                                f"Name '{name}' contains PEP title "
                                f"indicator '{title}'."
                            ),
                            category="pep",
                        )
                    )

            # Surname-based heuristic matching
            for surname in self._pep_surnames:
                if surname in name_lower:
                    flags.append(
                        VendorRiskFlag(
                            label="Surname Matches Known Political Family",
                            severity=Severity.LOW,
                            detail=(
                                f"Name '{name}' shares surname "
                                f"'{surname}' with known political "
                                "figures."
                            ),
                            category="pep",
                        )
                    )

        return flags

    def _check_registration_age(
        self, vendor: VendorProfile
    ) -> List[VendorRiskFlag]:
        """Flag recently registered companies (potential fronts).

        Companies registered within the last RECENT_REGISTRATION_DAYS
        are considered suspicious.
        """
        flags: List[VendorRiskFlag] = []
        if not vendor.registration_date:
            return flags

        try:
            reg_date = datetime.strptime(
                vendor.registration_date, "%Y-%m-%d"
            )
        except (ValueError, TypeError):
            # Unparseable date — skip this check silently
            return flags

        age_days = (datetime.now() - reg_date).days
        if age_days < RECENT_REGISTRATION_DAYS:
            flags.append(
                VendorRiskFlag(
                    label="Recently Registered Company",
                    severity=Severity.MEDIUM,
                    detail=(
                        f"Company registered {age_days} days ago "
                        f"(threshold: {RECENT_REGISTRATION_DAYS} days). "
                        "May be a front for bid rigging."
                    ),
                    category="registration",
                )
            )

        return flags

    def _check_known_shells(
        self, vendor: VendorProfile
    ) -> List[VendorRiskFlag]:
        """Cross-reference the vendor name against a known shell database.

        Performs substring matching (vendor in shell, shell in vendor)
        to catch slight name variations.
        """
        flags: List[VendorRiskFlag] = []
        name_lower = vendor.name.strip().lower()

        for shell in self.known_shells:
            shell_lower = shell.lower()
            if shell_lower in name_lower or name_lower in shell_lower:
                flags.append(
                    VendorRiskFlag(
                        label="Known Shell Entity",
                        severity=Severity.CRITICAL,
                        detail=(
                            f"Vendor '{vendor.name}' matches or is "
                            f"affiliated with known shell entity "
                            f"'{shell}'."
                        ),
                        category="shell",
                    )
                )

        return flags