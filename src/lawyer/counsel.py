"""Virtual Lawyer — the main counsel engine."""

from __future__ import annotations

from typing import Optional

from ..shared.models import (
    CounselRequest, CounselResponse, JurisdictionCode, LegalArticle,
)
from ..shared.llm import LLMClient
from ..shared.jurisdiction import JurisdictionLoader
from .jurisprudence import LegalQueryEngine
from .disclaimers import get_disclaimer
from .drafting import DraftGenerator
from .evidence import EvidenceChecklist
from .risk_assessment import WhistleblowerRiskAssessment


COUNSEL_SYSTEM_PROMPT = """You are a helpful Digital Lawyer who explains legal matters in simple, everyday language. No legalese — speak like a helpful friend who knows the law.

YOUR ROLE:
1. Answer legal questions about government tenders and corruption
2. Cite specific laws when relevant (constitution, procurement acts)
3. Explain what the user can do — in plain steps
4. Help draft complaints, reports, RTI requests

ALWAYS:
- Use simple language an ordinary person would understand
- If the constitution or law supports something, say "According to the Constitution of Nepal..."
- If you don't know the exact law, say so — never make up legal citations
- Be practical: tell users exactly what to do next
- Keep answers short and to the point
- End with a helpful offer like "Would you like me to draft a complaint?" or "Should I explain more?"

You have access to legal context from the Constitution of Nepal and procurement laws. 
Base your answers on that context. If the context is empty, say you need more information 
rather than making things up."""


class VirtualLawyer:
    """The Virtual Lawyer engine — handles counsel requests and generates responses."""

    def __init__(self, loader: JurisdictionLoader, llm: Optional[LLMClient] = None):
        self.loader = loader
        self.llm = llm
        self.query_engine = LegalQueryEngine(loader)
        self.draft_generator = DraftGenerator(loader, llm)
        self.evidence = EvidenceChecklist()
        self.risk = WhistleblowerRiskAssessment()

    def counsel(self, request: CounselRequest,
                constitution_context: str = "") -> CounselResponse:
        """Process a counsel request and return a response."""
        # 1. Resolve jurisdiction
        jurisdiction = request.jurisdiction
        if jurisdiction == JurisdictionCode.UNKNOWN:
            # Try to detect from tender text
            detected = self.loader.detect_jurisdiction_from_text(request.tender_context)
            if detected != JurisdictionCode.UNKNOWN:
                jurisdiction = detected

        # 2. Get legal context
        legal_articles = self.query_engine.find_relevant_articles(
            jurisdiction, request.question
        )

        # 3. Get disclaimer
        disclaimer = get_disclaimer(jurisdiction)

        # 4. Check if user is asking for a complaint draft
        wants_draft = any(phrase in request.question.lower() for phrase in [
            "draft", "write a complaint", "generate complaint", "file a report",
            "write a letter", "complaint letter", "rti request", "foia",
            "bikin laporan", "buat pengaduan", "surat", "模板", "起草",
        ])

        # 5. Generate response
        if self.llm:
            # Build context for LLM
            legal_context = self._build_legal_context(jurisdiction, legal_articles)
            risk_context = self._build_risk_context(request)

            user_prompt = (
                f"Tender Information:\n{request.tender_context[:3000]}\n\n"
                f"Risk Analysis Summary:\n{risk_context}\n\n"
                f"Legal Context:\n{legal_context}\n\n"
                + (f"Constitution of Nepal (relevant articles):\n{constitution_context[:4000]}\n\n"
                    if constitution_context else "")
                + f"User Question: {request.question}\n\n"
                f"Jurisdiction: {jurisdiction.value}\n\n"
            )

            if wants_draft:
                user_prompt += (
                    "\n\nThe user is requesting a legal document draft. "
                    "Generate the draft document directly in your response, then also "
                    "explain how to file it."
                )

            answer = self.llm.generate(
                system_prompt=COUNSEL_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                temperature=0.3,
                max_tokens=4096,
            )
        else:
            # No LLM — rule-based response
            answer = self._rule_based_response(request, jurisdiction, legal_articles)

        # 6. Generate draft if requested
        template_name = None
        template_content = None
        if wants_draft:
            draft = self.draft_generator.generate_complaint(request)
            template_name = draft.template_name
            template_content = draft.body
            answer += f"\n\n{'='*60}\nDRAFT DOCUMENT\n{'='*60}\n\n{draft.body}"
            answer += f"\n\n{draft.instructions}"

        # 7. Extract suggested actions
        suggested_actions = self._extract_actions(jurisdiction, legal_articles)

        return CounselResponse(
            answer=answer,
            citations=legal_articles,
            suggested_actions=suggested_actions,
            template_name=template_name,
            template_content=template_content,
            disclaimer=disclaimer,
        )

    def _build_legal_context(self, jurisdiction: JurisdictionCode,
                             articles: list) -> str:
        """Build a condensed legal context for LLM prompt."""
        if not articles:
            context = self.loader.build_legal_context(jurisdiction)
            if len(context) > 4000:
                context = context[:4000] + "\n...[truncated]"
            return context

        lines = [f"=== Relevant Laws for {jurisdiction.value} ==="]
        for art in articles:
            lines.append(f"\n- {art.source}: {art.description[:200]}")
            if art.penalty:
                lines.append(f"  Penalty: {art.penalty}")
            if art.action:
                lines.append(f"  Action: {art.action}")
            if art.report_template:
                lines.append(f"  Template: {art.report_template}")

        return "\n".join(lines)

    def _build_risk_context(self, request: CounselRequest) -> str:
        """Build risk summary for LLM context."""
        if not request.risk_report:
            return "No risk analysis available."

        report = request.risk_report
        lines = [
            f"Overall Risk: {report.overall_risk.upper()}",
            f"Red Flags: {len(report.flagged_clauses)}",
        ]
        for flag in report.flagged_clauses[:5]:
            lines.append(f"  - [{flag.severity.upper()}] {flag.label}: {flag.description[:150]}")
        if len(report.flagged_clauses) > 5:
            lines.append(f"  ... and {len(report.flagged_clauses) - 5} more")

        return "\n".join(lines)

    def _rule_based_response(self, request: CounselRequest,
                              jurisdiction: JurisdictionCode,
                              articles: list) -> str:
        """Fallback response when no LLM is available."""
        # Provide a structured, template-based answer
        parts = []

        if jurisdiction == JurisdictionCode.UNKNOWN:
            parts.append(
                "I need to know the jurisdiction/country for this tender. "
                "Which country is this tender from? Nepal?"
            )
            return "\n\n".join(parts)

        parts.append(f"Jurisdiction: {self.loader.get_meta(jurisdiction).get('country', jurisdiction.value)}")

        if not articles:
            parts.append(
                "I couldn't find specific legal articles matching your question in "
                "my knowledge base. Your query may touch on areas outside procurement law "
                "or require a more specialized legal corpus. "
                "Consider consulting a local attorney."
            )
        else:
            parts.append(f"Found {len(articles)} relevant legal provision(s):")
            for art in articles:
                parts.append(f"\n📜 {art.source}")
                parts.append(f"   {art.description}")
                if art.penalty:
                    parts.append(f"   ⚖️ Penalty: {art.penalty}")
                if art.action:
                    parts.append(f"   📋 Action: {art.action}")

            parts.append("\n---")
            parts.append("To proceed, you can:")
            for act in self._extract_actions(jurisdiction, articles):
                parts.append(f"• {act}")

        return "\n".join(parts)

    def _extract_actions(self, jurisdiction: JurisdictionCode,
                         articles: list) -> list:
        """Extract actionable steps from legal articles."""
        actions = set()

        # Add oversight body info
        try:
            meta = self.loader.get_meta(jurisdiction)
            for body in meta.get("oversight_bodies", []):
                name = body.get("name", "")
                role = body.get("role", "")
                actions.add(f"Report to {name} ({role})")
        except (FileNotFoundError, KeyError):
            pass

        # Add article-specific actions
        for art in articles:
            if art.action:
                actions.add(art.action)
            if art.report_template:
                actions.add(f"Use the '{art.report_template}' template to file a formal complaint")

        return list(actions)[:8]  # Limit to top 8
