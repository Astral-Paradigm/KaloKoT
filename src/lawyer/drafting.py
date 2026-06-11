"""Complaint/RTI/FOIA draft generator."""

from __future__ import annotations

from typing import Optional

from ..shared.models import JurisdictionCode, ComplaintDraft, CounselRequest
from ..shared.jurisdiction import JurisdictionLoader
from ..shared.llm import LLMClient


DRAFTING_SYSTEM_PROMPT = """You are a legal document drafting assistant specializing in public procurement complaints, 
whistleblower reports, and RTI/FOIA requests. You have access to a legal knowledge base 
with jurisdiction-specific templates.

Your job:
1. Given a user's description of a procurement violation and the relevant jurisdiction,
2. Generate a complete, ready-to-file legal document.
3. Follow the structure and language conventions of that jurisdiction.

Rules:
- Use the jurisdiction's templates as a base structure
- Fill in specific details from the user's complaint
- Keep the language formal and professional
- Include placeholders [in brackets] for user-specific fields
- Add practical filing instructions at the bottom
- Clearly note: "This is a DRAFT. Review with a qualified attorney before filing."

Output format: plain text document with clear section headings."""


class DraftGenerator:
    """Generate complaint/RTI/whistleblower drafts."""

    def __init__(self, loader: JurisdictionLoader, llm: Optional[LLMClient] = None):
        self.loader = loader
        self.llm = llm

    def generate_complaint(self, request: CounselRequest) -> ComplaintDraft:
        """Generate a complaint draft based on the counsel request."""
        if self.llm:
            return self._generate_with_llm(request)
        else:
            return self._generate_from_template(request)

    def _generate_with_llm(self, request: CounselRequest) -> ComplaintDraft:
        """Use LLM to generate a tailored complaint draft."""
        # Get jurisdiction context
        jurisdiction = request.jurisdiction
        legal_context = self.loader.build_legal_context(
            jurisdiction,
            flagged_ids=[f.red_flag_id for f in (request.risk_report.flagged_clauses
                                                 if request.risk_report else [])]
            if request.risk_report else None
        )

        # Get available templates
        templates = self.loader.get_templates(jurisdiction)
        template_names = [t.get("template_name") or t.get("name") or t.get("id", "?")
                          for t in templates]

        user_prompt = (
            f"I need a legal document regarding a procurement violation.\n\n"
            f"Jurisdiction: {jurisdiction.value}\n\n"
            f"Tender Description: {request.tender_context[:2000]}\n\n"
            f"User's Specific Question/Request: {request.question}\n\n"
            f"Available Templates: {', '.join(template_names)}\n\n"
            f"Legal Context:\n{legal_context[:3000]}\n\n"
            f"Please generate the most appropriate legal document based on the user's request. "
            f"If the user didn't specify a document type, generate a complaint letter to the "
            f"appropriate oversight body."
        )

        draft_text = self.llm.generate(
            system_prompt=DRAFTING_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.3,
            max_tokens=4096,
        )

        return ComplaintDraft(
            title=f"Complaint Draft — {request.tender_context[:50]}..."
            if len(request.tender_context) > 50
            else f"Complaint Draft — {request.tender_context}",
            jurisdiction=jurisdiction,
            body=draft_text,
            template_name="llm_generated",
            instructions="Review carefully with a qualified attorney before filing.",
        )

    def _generate_from_template(self, request: CounselRequest) -> ComplaintDraft:
        """Fallback: generate from YAML template."""
        jurisdiction = request.jurisdiction

        # Determine which template to use
        question_lower = request.question.lower()

        # Detect intent
        if "kpk" in question_lower or "ciaa" in question_lower or "anti-corruption" in question_lower:
            template_name = "complaint_ciaa"
        elif "rti" in question_lower or "right to information" in question_lower or "foia" in question_lower or "information" in question_lower:
            template_name = "rti_request"
        elif "appeal" in question_lower or "disqualif" in question_lower:
            template_name = "appeal_review_committee"
        elif "ppmo" in question_lower:
            template_name = "complaint_ppmo"
        else:
            template_name = "complaint_ciaa"

        # Load template from YAML
        template = self.loader.get_template_by_name(jurisdiction, template_name)

        if template and isinstance(template, dict):
            body = template.get("body", "")
            if template_name == "rti_request":
                title = "Right to Information Request"
            else:
                title = template.get("title", f"Complaint ({jurisdiction.value})")
        else:
            # Try to find by iterating
            templates = self.loader.get_templates(jurisdiction)
            for t in templates:
                # templates is a list of dicts from red_flag action references
                pass
            body = "Template not available. Run with LLM client enabled."
            title = "Complaint Draft"

        return ComplaintDraft(
            title=title,
            jurisdiction=jurisdiction,
            body=body,
            template_name=template_name,
            instructions="Fill in the [bracketed] fields with your specific details. "
                         "Review with a qualified attorney before filing.",
        )
