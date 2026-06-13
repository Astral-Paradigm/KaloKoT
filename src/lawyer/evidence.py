"""Evidence checklist generator — printable step-by-step evidence preservation guide.

Provides a curated set of evidence-preservation steps organised by category
(milestone, specification, budget, evaluation criteria, contract terms, and
general) and maps red-flag IDs to relevant sections so the checklist only
shows what matters for a particular risk report.
"""

from __future__ import annotations

from typing import List, Optional

from ..shared.models import JurisdictionCode, RiskReport
from ..shared.jurisdiction import JurisdictionLoader


# ── Lookup table of evidence-preservation steps ───────────────────────────
# Each entry is a list of (action, detailed description) tuples.

EVIDENCE_STEPS = {
    "timeline": [
        ("Screenshot tender publication date",
         "Capture the official publication page showing the date the tender was issued."),
        ("Screenshot submission deadline",
         "Capture the bid submission deadline from the tender document."),
        ("Save tender document PDF",
         "Download and save the original tender PDF/document before it's taken down."),
        ("Record dates on calendar",
         "Note the publication and deadline dates to calculate the actual bid period."),
    ],
    "specification": [
        ("Screenshot brand/model references",
         "Capture any specific brand names, model numbers, or exclusive references in the specification section."),
        ("Search for equivalents",
         "Document that equivalent products exist with a quick market search."),
        ("Compare with past tenders",
         "Check if the same entity published similar tenders with different specifications."),
    ],
    "budget": [
        ("Screenshot budget/estimated cost",
         "Capture the published estimated cost or budget range."),
        ("Research market rates",
         "Get quotes or published rate analyses for similar work/materials."),
        ("Request cost breakdown",
         "File an RTI request for the detailed cost estimate (see Draft Generator)."),
    ],
    "evaluation_criteria": [
        ("Screenshot evaluation criteria section",
         "Capture the evaluation methodology section — or the lack of one."),
        ("Note scoring weights",
         "Record what weights were assigned to technical vs. financial criteria."),
        ("Record committee members",
         "Note names of evaluation committee members if published."),
    ],
    "terms_and_conditions": [
        ("Screenshot contract terms",
         "Capture payment terms, penalty clauses, and performance guarantees."),
        ("Check for conflict of interest clauses",
         "Note whether the document includes recusal/declaration requirements."),
    ],
    "general": [
        ("Save the full tender document",
         "Download the complete PDF/HTML before the deadline passes."),
        ("Record the procuring entity",
         "Note the full name, address, and contact of the procuring entity."),
        ("Take screenshots of all pages",
         "Use browser screenshots as a backup in case the PDF is later modified."),
        ("Timestamp your evidence",
         "Use a timestamping service or notarized statement to prove evidence integrity."),
        ("Save bidder list if available",
         "If bid opening is public, attend and record the list of bidders."),
        ("Preserve correspondence",
         "Save any emails, clarifications, or communication with the procuring entity."),
        ("Document the process timeline",
         "Create a timeline of events from publication to current date."),
        ("Note witnesses",
         "Record names of anyone else who noticed the irregularities."),
        ("Back up everything off-device",
         "Upload encrypted copies to cloud storage or a trusted contact."),
    ],
}


class EvidenceChecklist:
    """Generate evidence preservation checklists for procurement violations.

    Given a :class:`RiskReport`, maps the flagged red-flag IDs to relevant
    evidence categories and produces a printable plain-text checklist.
    Optionally appends jurisdiction-specific reporting channels when a
    :class:`JurisdictionLoader` is available.
    """

    def __init__(self, loader: Optional[JurisdictionLoader] = None):
        """Initialise the checklist generator.

        Args:
            loader: Optional jurisdiction loader; used to inject oversight-body
                reporting channels into the final checklist.
        """
        self.loader = loader

    def generate(self, report: RiskReport,
                 jurisdiction: JurisdictionCode = JurisdictionCode.UNKNOWN) -> str:
        """Generate a complete evidence checklist based on the risk report.

        Only includes sections whose red flags are present in the report,
        plus the universal ``general`` section.  If a jurisdiction loader is
        attached, reporting-channel info is appended.

        Args:
            report: The parsed risk report with flagged_clauses.
            jurisdiction: Jurisdiction code (used for channel metadata).

        Returns:
            A printable plain-text checklist.
        """
        flagged_ids = {f.red_flag_id for f in report.flagged_clauses}
        relevant_sections = self._map_flags_to_sections(flagged_ids)

        lines = [
            "=" * 60,
            "  EVIDENCE PRESERVATION CHECKLIST",
            "=" * 60,
            "",
            "  Before the tender closes or documents are removed, preserve the",
            "  following evidence. Tick off each item as you complete it.",
            "",
        ]

        # ── Section-specific steps ─────────────────────────────────────────
        for section_name, steps in EVIDENCE_STEPS.items():
            if section_name in relevant_sections or section_name == "general":
                lines.append(f"  [{section_name.upper().replace('_', ' ')}]")
                lines.append(f"  {'─' * 50}")
                for action, detail in steps:
                    lines.append(f"  ☐  {action}")
                    lines.append(f"     {detail}")
                lines.append("")

        # ── Jurisdiction-specific reporting channels ───────────────────────
        if jurisdiction != JurisdictionCode.UNKNOWN and self.loader:
            try:
                meta = self.loader.get_meta(jurisdiction)
                lines.append("  [REPORTING CHANNELS]")
                lines.append(f"  {'─' * 50}")
                for body in meta.get("oversight_bodies", []):
                    name = body.get("name", "")
                    role = body.get("role", "")
                    site = body.get("website", "")
                    lines.append(f"  ☐  {name}:")
                    lines.append(f"     {role}")
                    if site:
                        lines.append(f"     Website: {site}")
                lines.append("")
            except (FileNotFoundError, KeyError):
                pass

        # ── Critical warnings ──────────────────────────────────────────────
        lines.extend([
            "  ⚠️  IMPORTANT WARNINGS",
            "  ──────────────────────────────────────────────────",
            "  •  Do NOT delete original documents after taking screenshots.",
            "  •  Screenshots can be modified — save PDFs/originals too.",
            "  •  Timestamp everything (physical notary or digital service).",
            "  •  Encrypt sensitive files before sharing.",
            "  •  If you feel at risk, consult a lawyer before filing.",
            "  •  Anonymous reporting options exist — use them if needed.",
            "",
            "  This checklist is a guide. Consult a qualified attorney for",
            "  advice specific to your situation and jurisdiction.",
            "=" * 60,
        ])

        return "\n".join(lines)

    def _map_flags_to_sections(self, flagged_ids: set) -> set:
        """Map red-flag IDs to evidence-section names.

        Args:
            flagged_ids: Set of red-flag ID strings from the risk report.

        Returns:
            Set of evidence section names (keys of :data:`EVIDENCE_STEPS`).
            Falls back to ``{"general"}`` when no mapping exists.
        """
        mapping = {
            "timeline-too-short": "timeline",
            "single-brand-spec": "specification",
            "vague-spec": "specification",
            "budget-inflation": "budget",
            "opaque-evaluation": "evaluation_criteria",
            "missing-evaluation-section": "evaluation_criteria",
            "conflict-interest-signals": "terms_and_conditions",
            "unusual-contract-terms": "terms_and_conditions",
            "emergency-keywords": "timeline",
            "bid-splitting": "general",
            "single-bidder-award": "evaluation_criteria",
            "shell-company-bidder": "general",
        }
        sections = set()
        for fid in flagged_ids:
            if fid in mapping:
                sections.add(mapping[fid])
        return sections or {"general"}

    def export_txt(self, report: RiskReport,
                   jurisdiction: JurisdictionCode = JurisdictionCode.UNKNOWN,
                   path: Optional[str] = None) -> str:
        """Generate and optionally save the checklist to a .txt file.

        Args:
            report: The risk report to base the checklist on.
            jurisdiction: Jurisdiction for reporting-channel metadata.
            path: Optional filesystem path; parent directories are created.

        Returns:
            The plain-text checklist content.
        """
        content = self.generate(report, jurisdiction)
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
        return content
