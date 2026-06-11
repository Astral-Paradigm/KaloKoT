"""Disclaimers for the Virtual Lawyer — jurisdiction-specific + generic."""

from ..shared.models import JurisdictionCode


STANDARD_DISCLAIMER = (
    "⚠️ AI-GENERATED LEGAL GUIDANCE — NOT LEGAL ADVICE ⚠️\n"
    "This Virtual Lawyer is an AI assistant trained on procurement law knowledge bases. "
    "It provides INFORMATIONAL guidance only and does NOT constitute legal advice, "
    "create an attorney-client relationship, or substitute for qualified legal counsel. "
    "Laws vary by jurisdiction, are subject to change, and their application depends on "
    "specific facts. Always consult a qualified attorney licensed in your jurisdiction "
    "before taking legal action.\n\n"
    "By using this service, you acknowledge:\n"
    "1. This is not a law firm or legal representation\n"
    "2. Your information is processed locally and not stored server-side\n"
    "3. You are solely responsible for decisions made based on this information\n"
    "4. Whistleblower protections vary — understand your local laws before reporting"
)


JURISDICTION_DISCLAIMERS = {
    JurisdictionCode.NEPAL: (
        "Nepal-specific disclaimer:\n"
        "Nepali procurement law is governed by the Public Procurement Act 2063 (2007), "
        "Public Procurement Regulations 2064 (2008), and PPMO circulars. These laws are "
        "subject to amendment. This AI's knowledge of Nepali law was last reviewed on "
        "June 11, 2026. Always verify current provisions with the PPMO website (ppmo.gov.np) "
        "or consult a lawyer licensed by the Nepal Bar Council.\n\n"
        "Whistleblower note: Nepal's Good Governance (Management & Operation) Act 2064 "
        "provides certain protections for good-faith complainants. However, implementation "
        "varies. Consider anonymous reporting channels."
    ),
}


def get_disclaimer(jurisdiction: JurisdictionCode = JurisdictionCode.UNKNOWN) -> str:
    """Get the appropriate disclaimer for the jurisdiction."""
    parts = [STANDARD_DISCLAIMER]
    specific = JURISDICTION_DISCLAIMERS.get(jurisdiction)
    if specific:
        parts.append("")
        parts.append(specific)
    return "\n".join(parts)
