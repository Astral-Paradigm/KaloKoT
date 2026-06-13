"""Whistleblower Risk Assessment — personal risk appraisal for whistleblowers.

PRD Layer 2: "Risk Assessment — honest appraisal of personal risk if you
blow the whistle (retaliation likelihood, anonymity options, witness
protection where available)."

Per-jurisdiction guidance based on legal protections, transparency
indices, and documented retaliation patterns.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List

from ..shared.models import JurisdictionCode


class RetaliationRisk(str, Enum):
    """Enumeration of overall retaliation-risk levels."""
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    EXTREME = "extreme"


class AnonymityOption(str, Enum):
    """Degrees of anonymity available to a whistleblower."""
    NAMED = "named"            # Must reveal identity to file
    PSEUDONYMOUS = "pseudo"    # Can use pseudonym but may be identified
    ANONYMOUS = "anonymous"    # Truly anonymous channels exist
    PROTECTED = "protected"    # Legal whistleblower protections and secure channels


class WitnessProtection(str, Enum):
    """Levels of witness-protection available."""
    NONE = "none"
    LIMITED = "limited"        # Basic police protection available
    PROGRAM = "program"        # Formal witness protection program exists


class WhistleblowerRiskAssessment:
    """Assess personal risk for a whistleblower in a given jurisdiction.

    Maintains a static dictionary of per-jurisdiction data covering overall
    risk, anonymity options, witness-protection status, legal protections,
    recommended reporting channels, retaliation indicators, and precaution
    steps.  Currently only Nepal (``np``) is populated.
    """

    def __init__(self):
        # ── Per-jurisdiction risk profiles ─────────────────────────────────
        self._jurisdiction_data: Dict[str, dict] = {
            "np": {
                "country": "Nepal",
                "overall_risk": RetaliationRisk.HIGH,
                "summary": (
                    "Nepal has constitutional protections for whistleblowers but "
                    "enforcement is weak. Retaliation — including job termination, "
                    "harassment, and physical threats — is documented. The CIAA and "
                    "National Human Rights Commission provide limited protection."
                ),
                "anonymity": AnonymityOption.PSEUDONYMOUS,
                "anonymity_detail": (
                    "CIAA accepts anonymous complaints, but effective investigation "
                    "often requires your identity. Consider using a lawyer or "
                    "intermediary as a buffer."
                ),
                "witness_protection": WitnessProtection.LIMITED,
                "witness_protection_detail": (
                    "Nepal has no formal witness protection law (as of 2026). "
                    "In high-profile cases, CIAA or police may offer informal "
                    "protection. The Witness Protection Bill has been proposed but "
                    "not enacted."
                ),
                "legal_protections": [
                    "Constitution of Nepal 2015, Article 47 — Right to information",
                    "Anti-Corruption Act 2019, §38 — Protection of informants",
                    "CIAA may keep complainant identity confidential (§38)",
                    "National Human Rights Commission Act 2068 — Protection against retaliation",
                ],
                "recommended_channels": [
                    {"channel": "CIAA Anonymous Complaint", "risk": RetaliationRisk.LOW,
                     "note": "File through CIAA website or toll-free helpline 1660-00-52525"},
                    {"channel": "Named Complaint to CIAA", "risk": RetaliationRisk.MODERATE,
                     "note": "Most effective; identity protected under §38 but not guaranteed"},
                    {"channel": "Media / NGO Intermediary", "risk": RetaliationRisk.LOW,
                     "note": "Work through a journalist or anti-corruption NGO (e.g., Transparency International Nepal)"},
                    {"channel": "Internal Whistleblowing", "risk": RetaliationRisk.HIGH,
                     "note": "Report within the procuring entity — highest retaliation risk"},
                ],
                "retaliation_indicators": [
                    "Sudden transfer or reassignment",
                    "Negative performance reviews following complaint",
                    "Harassment or intimidation from colleagues/supervisors",
                    "Threats of legal action (defamation, breach of confidentiality)",
                    "Physical threats or surveillance",
                ],
                "precaution_steps": [
                    "1. DOCUMENT EVERYTHING — Keep copies of all evidence off-site (encrypted USB, cloud)",
                    "2. USE SECURE COMMUNICATION — Signal/ProtonMail for sensitive communications",
                    "3. CONSULT A LAWYER — Get legal advice before filing",
                    "4. USE AN INTERMEDIARY — An NGO or journalist can buffer retaliation",
                    "5. TIMESTAMP EVIDENCE — Use trusted timestamp services or notarize copies",
                    "6. HAVE AN EXIT PLAN — Know your rights and have a contingency if employment is affected",
                    "7. CONTACT AN EMBASSY — If foreign national, your embassy may offer consular protection",
                ],
            },
        }

    def assess(
        self,
        jurisdiction: JurisdictionCode,
        is_government_employee: bool = False,
        has_evidence_copies: bool = False,
    ) -> dict:
        """Generate a risk assessment for the given jurisdiction.

        Optionally adjusts overall risk upward for government employees, and
        appends a critical warning when the user has not secured off-site
        evidence copies.

        Args:
            jurisdiction: The jurisdiction to assess.
            is_government_employee: Whether the whistleblower is a govt employee
                (elevates risk from HIGH to EXTREME).
            has_evidence_copies: Whether the user has evidence backed up off-site.

        Returns:
            A dict with keys: jurisdiction, overall_risk, summary, anonymity,
            witness_protection, legal_protections, recommended_channels,
            retaliation_indicators, precaution_steps, and optionally
            critical_warning.
        """
        data = self._jurisdiction_data.get(jurisdiction.value)
        if not data:
            return self._unknown_jurisdiction()

        overall = data["overall_risk"]

        # Government employees face elevated risk in high-risk jurisdictions
        if is_government_employee and overall == RetaliationRisk.HIGH:
            overall = RetaliationRisk.EXTREME

        assessment = {
            "jurisdiction": data["country"],
            "overall_risk": overall.value,
            "summary": data["summary"],
            "anonymity": {
                "level": data["anonymity"].value,
                "detail": data["anonymity_detail"],
            },
            "witness_protection": {
                "level": data["witness_protection"].value,
                "detail": data["witness_protection_detail"],
            },
            "legal_protections": data["legal_protections"],
            "recommended_channels": [
                {**ch, "risk": ch["risk"].value}
                for ch in data["recommended_channels"]
            ],
            "retaliation_indicators": data["retaliation_indicators"],
            "precaution_steps": data["precaution_steps"],
            "is_government_employee": is_government_employee,
            "has_evidence_copies": has_evidence_copies,
        }

        if not has_evidence_copies:
            assessment["critical_warning"] = (
                "You do NOT have copies of evidence stored safely off-site. "
                "Secure copies before filing any complaint — documents have "
                "been known to disappear from government offices after a "
                "whistleblower complaint is filed."
            )

        return assessment

    def _unknown_jurisdiction(self) -> dict:
        """Return a generic conservative assessment when no data exists."""
        return {
            "jurisdiction": "Unknown",
            "overall_risk": RetaliationRisk.HIGH.value,
            "summary": (
                "Jurisdiction-specific risk data is not available. "
                "General precautions apply. Consult a local human rights "
                "organization before proceeding."
            ),
            "anonymity": {
                "level": AnonymityOption.NAMED.value,
                "detail": "Unclear — consult a local attorney or NGO.",
            },
            "witness_protection": {
                "level": WitnessProtection.NONE.value,
                "detail": "No data available for this jurisdiction.",
            },
            "legal_protections": [
                "Check local whistleblower protection laws.",
                "Consult a human rights organization.",
            ],
            "recommended_channels": [
                {"channel": "Local Anti-Corruption Body", "risk": "moderate",
                 "note": "Identify the appropriate oversight body first."},
                {"channel": "Media / NGO", "risk": "low",
                 "note": "Work through an intermediary for initial disclosure."},
            ],
            "retaliation_indicators": [
                "Job termination or demotion",
                "Harassment or intimidation",
                "Legal threats (defamation suits)",
            ],
            "precaution_steps": [
                "1. Secure all evidence in multiple locations",
                "2. Use encrypted communications (Signal/ProtonMail)",
                "3. Consult a lawyer before filing",
                "4. Identify support organizations in your country",
                "5. Document everything with timestamps",
            ],
            "is_government_employee": False,
            "has_evidence_copies": False,
        }

    def list_jurisdictions(self) -> List[str]:
        """Return list of jurisdiction keys that have risk data loaded."""
        return list(self._jurisdiction_data.keys())
