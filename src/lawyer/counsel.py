"""Virtual Lawyer — the main counsel engine for KaloKoT.

Orchestrates legal counsel by combining jurisdiction-specific legal context,
AI-generated (LLM) or rule-based responses, compliance risk analysis, complaint
draft generation, and evidence checklists.  All public methods are consumed by
the FastAPI layer in src/api.py.
"""

from __future__ import annotations

from typing import Optional

from ..shared.models import (
    CounselRequest, CounselResponse, JurisdictionCode,
)
from ..shared.llm import LLMClient
from ..shared.jurisdiction import JurisdictionLoader
from .jurisprudence import LegalQueryEngine
from .disclaimers import get_disclaimer
from .drafting import DraftGenerator
from .evidence import EvidenceChecklist
from .risk_assessment import WhistleblowerRiskAssessment


# ── LLM system prompt ──────────────────────────────────────────────────────

COUNSEL_SYSTEM_PROMPT = """You are the Digital Lawyer persona of KaloKoT — an AI legal companion for everyday Nepali citizens. You talk like a wise, friendly chamber judge who uses simple, clear language. You NEVER use legalese, and ALWAYS speak in short paragraphs.

CORE RULE — OUTPUT FORMAT:
- Always give a SHORT SUMMARY (3-5 sentences max) on first response
- Use **bold section titles** (markdown-style) to organize information
- Write in clean, easy English that a common person understands
- You are the mascot persona — warm, reassuring, like a wise owl in a robe
- Only give more detail if the user says "tell me more" or asks for specifics

**LANGUAGE RULE — CITATIONS IN NEPALI:**
When you cite or quote articles from the Constitution of Nepal, you MUST present them in **Nepali (Devanagari script)** alongside the English translation. The constitution text provided in context is in Nepali — use it directly.

Format for citations:
> **Article 16 (अनुच्छेद १६)** — Right to Live with Dignity (गरिमापूर्ण जीवनको अधिकार)
> "प्रत्येक व्यक्तिको गरिमापूर्ण जीवनको अधिकार हुनेछ।" (Every person shall have the right to live with dignity.)

YOUR KNOWLEDGE:
You are well-versed in ALL areas of Nepali law, including:
1. **Constitutional Rights** — Constitution of Nepal 2072, fundamental rights
2. **Consumer Rights** — Consumer Protection Act 2075, right to quality goods
3. **Corporate & Employment Law** — Labour Act 2074, wages, workplace safety
4. **Criminal Law** — Muluki Ain (National Code)
5. **Property & Land Law** — Land Act 2021, tenancy, inheritance
6. **Procurement & Anti-Corruption** — Public Procurement Act 2063, CIAA
7. **Family Law** — marriage, divorce, child custody
8. **Cyber Law** — Electronic Transactions Act 2063
9. **Tax & Banking** — Income Tax Act 2058, Nepal Rastra Bank
10. **RTI & Transparency** — Right to Information Act 2064

HOW TO STRUCTURE YOUR ANSWER:
**Summary** → (1-2 sentences on the core answer)
**Your Rights** → (brief explanation in plain terms)
**What You Can Do** → (1-2 specific actions, offices to visit, forms to file)

ALWAYS:
- Start simply: "According to Nepali law..."
- If you don't know, say so — never make up legal citations
- Keep it SHORT — 150 words or fewer unless asked for more
- End with one useful offer like "Want me to draft a complaint letter?"

You have access to legal context from the Constitution of Nepal. Base answers on that context when available.
"""

class VirtualLawyer:
    """The Virtual Lawyer engine — handles counsel requests and generates responses.

    Flows through jurisdiction resolution → legal context retrieval →
    LLM or template-based response → optional draft generation → action
    extraction.  Every public method is consumed by the FastAPI server.
    """

    def __init__(self, loader: JurisdictionLoader, llm: Optional[LLMClient] = None):
        """Initialise the Virtual Lawyer with jurisdiction data and an optional LLM client.

        Args:
            loader: Jurisdiction loader providing legal corpus, red-flag data, templates.
            llm: Optional LLM client.  When None, rule-based fallback responses are used.
        """
        self.loader = loader
        self.llm = llm
        self.query_engine = LegalQueryEngine(loader)
        self.draft_generator = DraftGenerator(loader, llm)
        self.evidence = EvidenceChecklist()
        self.risk = WhistleblowerRiskAssessment()

    def counsel(self, request: CounselRequest,
                constitution_context: str = "",
                chat_history: Optional[list[dict]] = None) -> CounselResponse:
        """Process a counsel request and return a complete response.

        Pipeline:
          1. Resolve jurisdiction  (auto-detect if UNKNOWN)
          2. Query legal articles  (keyword-based relevance from the red-flag corpus)
          3. Append jurisdiction-specific disclaimer
          4. Detect whether the user wants a complaint *draft*
          5. Generate answer  (LLM-driven or rule-based fallback)
          6. If draft requested, append draft document body
          7. Extract up to 8 suggested actions from legal articles

        Args:
            request: Counsel request containing question, tender context, risk report.
            constitution_context: Optional Nepali Constitution article text.
            chat_history: Previous conversation messages [{role, text}, ...].

        Returns:
            A CounselResponse with answer text, citations, actions, and disclaimer.
        """
        # ── 1. Resolve jurisdiction ────────────────────────────────────────
        jurisdiction = request.jurisdiction
        if jurisdiction == JurisdictionCode.UNKNOWN:
            detected = self.loader.detect_jurisdiction_from_text(request.tender_context)
            if detected != JurisdictionCode.UNKNOWN:
                jurisdiction = detected

        # ── 2. Retrieve relevant legal articles (keyword-matched) ──────────
        legal_articles = self.query_engine.find_relevant_articles(
            jurisdiction, request.question
        )

        # ── 3. Disclaimer ──────────────────────────────────────────────────
        disclaimer = get_disclaimer(jurisdiction)

        # ── 4. Detect whether user wants a complaint / RTI draft ───────────
        draft_phrases = [
            "draft", "write a complaint", "generate complaint", "file a report",
            "write a letter", "complaint letter", "rti request", "foia",
            "bikin laporan", "buat pengaduan", "surat", "模板", "起草",
        ]
        wants_draft = any(phrase in request.question.lower() for phrase in draft_phrases)

        # ── 5. Build chat history context ──────────────────────────────────
        chat_context = ""
        if chat_history:
            lines = []
            for msg in chat_history[-8:]:
                label = "User" if msg.get("role") == "user" else "Lawyer"
                lines.append(f"{label}: {msg.get('text', '')[:500]}")
            chat_context = "\n".join(lines)

        # ── 6. Generate answer ─────────────────────────────────────────────
        if self.llm:
            legal_context = self._build_legal_context(jurisdiction, legal_articles)
            risk_context = self._build_risk_context(request)

            user_prompt = (
                f"Tender Information:\n{request.tender_context[:3000]}\n\n"
                f"Risk Analysis Summary:\n{risk_context}\n\n"
                f"Legal Context:\n{legal_context}\n\n"
                + (f"Constitution of Nepal (relevant articles):\n{constitution_context[:4000]}\n\n"
                    if constitution_context else "")
                + (f"Conversation History:\n{chat_context}\n\n"
                    if chat_context else "")
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
            answer = self._rule_based_response(request, jurisdiction, legal_articles)

        # ── 6. Generate draft if the user asked for one ────────────────────
        template_name = None
        template_content = None
        if wants_draft:
            draft = self.draft_generator.generate_complaint(request)
            template_name = draft.template_name
            template_content = draft.body
            answer += f"\n\n{'='*60}\nDRAFT DOCUMENT\n{'='*60}\n\n{draft.body}"
            answer += f"\n\n{draft.instructions}"

        # ── 7. Extract suggested actionable steps ──────────────────────────
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
        """Build a condensed legal-context string to inject into the LLM prompt.

        If no articles matched, falls back to the full jurisdiction legal
        context from the loader (truncated at 4 000 characters).

        Args:
            jurisdiction: The resolved jurisdiction code.
            articles: Relevant legal articles from the query engine.

        Returns:
            Formatted text block of laws, penalties and report templates.
        """
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
        """Build a condensed risk-analysis string for the LLM prompt.

        Summarises the overall risk level and top 5 flagged clauses (with
        severity) from the optional risk report attached to the request.

        Args:
            request: The counsel request, possibly containing a risk report.

        Returns:
            Text block describing risks, or a short "none available" message.
        """
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
        """Fallback answer when no LLM client is available.

        Produces a structured, template-based answer that describes the
        jurisdiction, lists matching legal provisions with penalties and
        actions, and enumerates suggested next steps.

        Args:
            request: The original counsel request (used only for context).
            jurisdiction: The resolved jurisdiction.
            articles: Legal articles matched against the question.

        Returns:
            Plain-text answer string.
        """
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
        """Extract up to 8 actionable steps from legal articles and oversight metadata.

        Collects oversight-body reporting channels and article-specific
        actions (file complaints, pursue templates).  Deduplicates via a set.

        Args:
            jurisdiction: The resolved jurisdiction.
            articles: Relevant legal articles.

        Returns:
            List of action-description strings (max 8).
        """
        actions = set()

        # Add oversight-body reporting channels from jurisdiction metadata
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

        return list(actions)[:8]  # Cap at 8 items
