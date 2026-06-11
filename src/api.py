"""FastAPI backend for OpenTender + Counsel.

Provides REST endpoints for tender analysis, legal counsel,
evidence checklists, and complaint draft export.

Run with:
    python -m src.api
    # or
    uvicorn src.api:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import io
import os
import sys
import uuid
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Dict, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Load .env
try:
    from dotenv import load_dotenv
    dotenv_path = Path(__file__).resolve().parent.parent / ".env"
    if dotenv_path.exists():
        load_dotenv(dotenv_path)
except ImportError:
    pass

from src.analyzer import TenderExtractor, RiskScorer, ReportGenerator, VendorIntelligence, VendorProfile
from src.lawyer import VirtualLawyer, EvidenceChecklist
from src.lawyer.drafting import DraftGenerator
from src.lawyer.risk_assessment import WhistleblowerRiskAssessment
from src.shared.jurisdiction import JurisdictionLoader
from src.shared.llm import LLMClient
from src.shared.chunking import chunk_constitution, get_all_parent_texts
from src.shared.chroma_store import ChromaLegalStore
from src.shared.pdf_generator import generate_complaint_pdf, generate_analysis_report_pdf
from src.shared.models import (
    ComplaintDraft, CounselRequest, CounselResponse,
    JurisdictionCode, RiskReport, TenderDocument,
)
from src.shared.tts import speak_text
from src.shared.vector_search import LegalVectorSearch

# ── Application Setup ─────────────────────────────────────────────────────────

app = FastAPI(
    title="OpenTender + Counsel API",
    description="Procurement corruption risk analyzer and virtual lawyer for public procurement documents.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Global Instance Cache ─────────────────────────────────────────────────────

_instances: dict = {}
_report_cache: Dict[str, RiskReport] = {}


def _get_loader() -> JurisdictionLoader:
    if "loader" not in _instances:
        _instances["loader"] = JurisdictionLoader()
    return _instances["loader"]


def _get_extractor() -> TenderExtractor:
    if "extractor" not in _instances:
        _instances["extractor"] = TenderExtractor()
    return _instances["extractor"]


def _get_scorer() -> RiskScorer:
    if "scorer" not in _instances:
        _instances["scorer"] = RiskScorer()
    return _instances["scorer"]


def _get_reporter() -> ReportGenerator:
    if "reporter" not in _instances:
        _instances["reporter"] = ReportGenerator()
    return _instances["reporter"]


def _get_llm() -> Optional[LLMClient]:
    if "llm" not in _instances:
        provider = os.environ.get("LLM_DEFAULT_PROVIDER", "")
        model = os.environ.get("LLM_DEFAULT_MODEL", "")
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if provider == "openai" and api_key:
            _instances["llm"] = LLMClient(provider="openai", model=model or "gpt-4o-mini")
        elif os.environ.get("GEMINI_API_KEY"):
            _instances["llm"] = LLMClient(provider="gemini")
        elif os.environ.get("OPENROUTER_API_KEY"):
            _instances["llm"] = LLMClient(provider="openrouter")
        elif os.environ.get("ANTHROPIC_API_KEY"):
            _instances["llm"] = LLMClient(provider="anthropic")
        else:
            _instances["llm"] = None
    return _instances["llm"]


def _get_lawyer() -> VirtualLawyer:
    if "lawyer" not in _instances:
        _instances["lawyer"] = VirtualLawyer(_get_loader(), _get_llm())
    return _instances["lawyer"]


def _get_draft_generator() -> DraftGenerator:
    if "draft_generator" not in _instances:
        _instances["draft_generator"] = DraftGenerator(_get_loader(), _get_llm())
    return _instances["draft_generator"]


def _get_checklist() -> EvidenceChecklist:
    if "checklist" not in _instances:
        _instances["checklist"] = EvidenceChecklist(_get_loader())
    return _instances["checklist"]


def _get_vendor_intel() -> VendorIntelligence:
    if "vendor_intel" not in _instances:
        _instances["vendor_intel"] = VendorIntelligence()
    return _instances["vendor_intel"]


def _get_risk_assessment() -> WhistleblowerRiskAssessment:
    if "risk_assessment" not in _instances:
        _instances["risk_assessment"] = WhistleblowerRiskAssessment()
    return _instances["risk_assessment"]


def _get_legal_search() -> LegalVectorSearch:
    if "legal_search" not in _instances:
        _instances["legal_search"] = LegalVectorSearch()
    return _instances["legal_search"]


def _get_chroma_store() -> ChromaLegalStore:
    if "chroma_store" not in _instances:
        store = ChromaLegalStore()
        # Auto-index the Constitution of Nepal
        loader = _get_loader()
        try:
            import yaml
            const_path = Path(__file__).resolve().parent.parent / "docs" / "legal" / "np_constitution.yaml"
            if const_path.exists():
                with open(const_path) as f:
                    const_data = yaml.safe_load(f)
                n = store.index_constitution(const_data)
                print(f"  Indexed {n} constitution chunks")
        except Exception as e:
            print(f"  Constitution index: {e}")
        _instances["chroma_store"] = store
    return _instances["chroma_store"]


# ── Helper: Build TenderDocument with optional jurisdiction hint ──────────────


def _analyze_text(text: str, title: str = "Uploaded Tender") -> RiskReport:
    """Extract → score → return risk report from raw text."""
    loader = _get_loader()
    scorer = _get_scorer()

    jurisdiction = loader.detect_jurisdiction_from_text(text)
    tender = TenderDocument(title=title, raw_text=text)
    report = scorer.score(tender)
    return report


# ── Endpoints ─────────────────────────────────────────────────────────────────


@app.get("/")
async def root():
    return {
        "name": "OpenTender + Counsel API",
        "version": "1.0.0",
        "endpoints": {
            "POST /analyze": "Upload a tender file for analysis",
            "POST /analyze-text": "Submit tender text for analysis",
            "GET /report/{report_id}": "Get a cached report",
            "POST /counsel": "Ask the Virtual Lawyer a question",
            "POST /checklist": "Generate evidence preservation checklist",
            "POST /export-draft": "Export a complaint draft as .txt",
            "POST /vendor-intel": "Assess vendor/contractor risk (shell, PEP, registration)",
            "POST /risk-assessment": "Whistleblower personal risk assessment",
            "POST /legal-search": "Semantic search over legal knowledge base",
            "GET /jurisdictions": "List available legal jurisdictions",
            "POST /constitution-search": "Semantic search over Constitution of Nepal (ChromaDB + parent-child)",
            "GET /constitution-context": "Get full Constitution text for Gemini context caching",
            "GET /health": "Health check",
        },
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/jurisdictions")
async def list_jurisdictions():
    """List all available legal knowledge base jurisdictions."""
    loader = _get_loader()
    jurisdictions = []
    for code in JurisdictionCode:
        if code == JurisdictionCode.UNKNOWN:
            continue
        try:
            meta = loader.get_meta(code)
            jurisdictions.append({
                "code": code.value,
                "country": meta.get("country", code.value),
                "last_reviewed": meta.get("last_reviewed"),
                "oversight_bodies": [
                    {"name": b.get("name"), "role": b.get("role")}
                    for b in meta.get("oversight_bodies", [])
                ],
            })
        except FileNotFoundError:
            pass
    return {"jurisdictions": jurisdictions}


@app.post("/analyze", summary="Upload a tender file for analysis")
async def analyze_file(file: UploadFile = File(...)):
    """Upload a tender document (PDF, TXT, HTML) and get a corruption risk analysis."""
    raw = await file.read()
    text = raw.decode("utf-8", errors="replace")
    report = _analyze_text(text, title=file.filename or "Uploaded Tender")
    report_id = uuid.uuid4().hex[:12]
    _report_cache[report_id] = report

    return {
        "report_id": report_id,
        "overall_risk": report.overall_risk.value,
        "summary": report.summary,
        "section_scores": {k: v.value for k, v in report.section_scores.items()},
        "flagged_clauses": [
            {
                "id": c.red_flag_id,
                "label": c.label,
                "severity": c.severity.value,
                "description": c.description,
                "location": c.location,
                "suggestion": c.suggestion,
            }
            for c in report.flagged_clauses
        ],
    }


@app.post("/analyze-text", summary="Submit tender text for analysis")
async def analyze_text(text: str = Form(...), title: str = Form("Uploaded Tender")):
    """Submit tender document text directly and get a corruption risk analysis."""
    report = _analyze_text(text, title=title)
    report_id = uuid.uuid4().hex[:12]
    _report_cache[report_id] = report

    return {
        "report_id": report_id,
        "overall_risk": report.overall_risk.value,
        "summary": report.summary,
        "section_scores": {k: v.value for k, v in report.section_scores.items()},
        "flagged_clauses": [
            {
                "id": c.red_flag_id,
                "label": c.label,
                "severity": c.severity.value,
                "description": c.description,
                "location": c.location,
                "suggestion": c.suggestion,
            }
            for c in report.flagged_clauses
        ],
    }


@app.get("/report/{report_id}", summary="Get cached analysis report")
async def get_report(report_id: str):
    """Retrieve a previously generated report by its ID."""
    if report_id not in _report_cache:
        raise HTTPException(status_code=404, detail="Report not found")
    report = _report_cache[report_id]
    reporter = _get_reporter()
    return {
        "report_id": report_id,
        "overall_risk": report.overall_risk.value,
        "summary": report.summary,
        "section_scores": {k: v.value for k, v in report.section_scores.items()},
        "flagged_clauses": [
            {
                "id": c.red_flag_id,
                "label": c.label,
                "severity": c.severity.value,
                "description": c.description,
                "location": c.location,
                "suggestion": c.suggestion,
            }
            for c in report.flagged_clauses
        ],
        "full_report": reporter.generate_text(report),
    }


@app.post("/counsel", summary="Ask the Virtual Lawyer a question")
async def counsel(
    question: str = Form(...),
    tender_context: str = Form(""),
    jurisdiction: str = Form("unknown"),
    report_id: Optional[str] = Form(None),
):
    """Ask the Virtual Lawyer about a tender's legal implications."""
    loader = _get_loader()
    lawyer = _get_lawyer()

    jcode = JurisdictionCode.UNKNOWN
    for code in JurisdictionCode:
        if code.value == jurisdiction.lower():
            jcode = code
            break

    context = tender_context
    if report_id and report_id in _report_cache:
        report = _report_cache[report_id]
        context = f"{report.tender.title or 'Tender'}\n{report.summary}\n\n{context}"

    request = CounselRequest(
        tender_context=context,
        question=question,
        jurisdiction=jcode,
    )

    response = lawyer.counsel(request)
    return {
        "answer": response.answer,
        "citations": [
            {"source": c.source, "description": c.description}
            for c in response.citations
        ],
        "suggested_actions": response.suggested_actions,
        "disclaimer": response.disclaimer,
        "template_name": response.template_name,
    }


@app.post("/checklist", summary="Generate evidence checklist")
async def generate_checklist(report_id: str = Form(...),
                              jurisdiction: str = Form("unknown")):
    """Generate an evidence preservation checklist based on a risk report."""
    if report_id not in _report_cache:
        raise HTTPException(status_code=404, detail="Report not found")

    report = _report_cache[report_id]
    jcode = JurisdictionCode.UNKNOWN
    for code in JurisdictionCode:
        if code.value == jurisdiction.lower():
            jcode = code
            break

    checklist = _get_checklist()
    text = checklist.generate(report, jcode)
    return PlainTextResponse(text)


@app.post("/export-draft", summary="Export complaint draft as .txt")
async def export_draft(
    title: str = Form(...),
    body: str = Form(...),
    jurisdiction: str = Form("unknown"),
    template_name: str = Form(""),
    instructions: str = Form(""),
):
    """Export a complaint draft as a downloadable .txt file."""
    jcode = JurisdictionCode.UNKNOWN
    for code in JurisdictionCode:
        if code.value == jurisdiction.lower():
            jcode = code
            break

    draft = ComplaintDraft(
        title=title,
        jurisdiction=jcode,
        body=body,
        template_name=template_name or "",
        instructions=instructions or "Review with a qualified attorney before filing.",
    )

    generator = _get_draft_generator()
    text = generator.export_txt(draft)

    return PlainTextResponse(
        text,
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{title.replace(" ", "_")}.txt"'},
    )


@app.post("/vendor-intel", summary="Assess vendor/contractor risk")
async def vendor_intelligence(
    vendor_name: str = Form(...),
    registration_number: Optional[str] = Form(None),
    registration_date: Optional[str] = Form(None),
    directors: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
):
    """Assess a vendor/contractor for shell company indicators, PEP connections, and registration risk."""
    profile = VendorProfile(
        name=vendor_name,
        registration_number=registration_number,
        registration_date=registration_date,
        directors=[d.strip() for d in directors.split(",")] if directors else [],
        address=address,
    )
    intel = _get_vendor_intel()
    overall, flags = intel.assess(profile)
    return {
        "vendor_name": vendor_name,
        "overall_risk": overall.value,
        "flags": [f.to_dict() for f in flags],
        "flag_count": len(flags),
    }


@app.post("/risk-assessment", summary="Whistleblower personal risk assessment")
async def whistleblower_risk(
    jurisdiction: str = Form(...),
    is_government_employee: bool = Form(False),
    has_evidence_copies: bool = Form(False),
):
    """Assess personal risk if you blow the whistle on procurement corruption.

    Provides jurisdiction-specific retaliation likelihood, anonymity options,
    witness protection availability, and precaution steps.
    """
    jcode = JurisdictionCode.UNKNOWN
    for code in JurisdictionCode:
        if code.value == jurisdiction.lower():
            jcode = code
            break
    assessor = _get_risk_assessment()
    result = assessor.assess(jcode, is_government_employee, has_evidence_copies)
    return result


@app.post("/legal-search", summary="Semantic search over legal knowledge base")
async def legal_search(
    query: str = Form(...),
    jurisdiction: str = Form("np"),
    top_k: int = Form(5),
    threshold: float = Form(0.0),
):
    """Search the legal knowledge base using semantic similarity.

    Finds relevant red flag definitions, legal provisions, templates, and
    oversight body information matching your query.
    """
    loader = _get_loader()
    searcher = _get_legal_search()

    jcode = JurisdictionCode.UNKNOWN
    for code in JurisdictionCode:
        if code.value == jurisdiction.lower():
            jcode = code
            break

    # Load YAML data and index
    try:
        yaml_data = loader.load_yaml(jcode)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Jurisdiction '{jurisdiction}' not found")

    searcher.index_jurisdiction(yaml_data)
    results = searcher.hybrid_search(query, top_k=top_k, threshold=threshold)
    return {"query": query, "jurisdiction": jurisdiction, "results": results}


@app.post("/constitution-search", summary="Search Constitution of Nepal via ChromaDB")
async def constitution_search(
    query: str = Form(...),
    top_k: int = Form(5),
    resolve_parents: bool = Form(True),
):
    """Semantic search over the Constitution of Nepal using ChromaDB.

    Uses Hierarchical/Parent-Child chunking:
    - ChromaDB matches individual clauses (child chunks)
    - When resolve_parents=True, returns the full Article text for context

    The full constitution can also be pre-loaded into the LLM context
    via the /constitution-context endpoint.
    """
    store = _get_chroma_store()
    raw_results = store.search(query, top_k=top_k)

    context = ""
    if resolve_parents:
        context = store.get_search_context(raw_results)

    return {
        "query": query,
        "results": [
            {
                "clause_id": r["child_id"],
                "clause_text": r["child_text"],
                "score": r["score"],
                "article_title": r.get("parent_title", ""),
                "part_number": r.get("part_number", 0),
                "part_title": r.get("part_title", ""),
                "path": r.get("path", []),
            }
            for r in raw_results
        ],
        "parent_context_length": len(context),
        "parent_context": context if resolve_parents else None,
    }


@app.get("/constitution-context", response_class=PlainTextResponse, summary="Get full Constitution text for LLM context caching")
async def constitution_context():
    """Return the full Constitution of Nepal text for pre-loading into an LLM context window.

    Use this with Gemini Context Caching: load this once into the LLM's
    context window, then use /constitution-search only for supplementary
    materials (gazettes, uploaded case PDFs).
    """
    store = _get_chroma_store()
    text = store.get_context_cache_text()
    return PlainTextResponse(
        content=text,
        headers={"X-Document": "Constitution of Nepal 2015",
                 "X-Total-Chars": str(len(text))}
    )


# ── Text-to-Speech ─────────────────────────────────────────────────────────────


@app.post("/tts", summary="Convert text to speech (ElevenLabs male voice)")
async def text_to_speech(text: str = Form(...)):
    """Convert text to speech using ElevenLabs with a deep male voice (Adam)."""
    audio = speak_text(text)
    if audio is None:
        raise HTTPException(status_code=502, detail="TTS unavailable — check ELEVENLABS_API_KEY")
    from fastapi.responses import StreamingResponse
    return StreamingResponse(audio, media_type="audio/mpeg")


# ── Complaint Drafting ─────────────────────────────────────────────────────────


@app.post("/draft-complaint", summary="Draft a formal complaint letter and return PDF")
async def draft_complaint(
    name: str = Form(...),
    permanent_address: str = Form(...),
    temporary_address: str = Form(...),
    citizenship_no: str = Form(...),
    phone: str = Form(...),
    email: str = Form(...),
    complaint_description: str = Form(...),
):
    """Draft a formal complaint letter using the LLM and return as a downloadable PDF.

    Requires complainant info + a description of the issue.
    The LLM drafts a formal legal complaint letter, then it's wrapped in a PDF.
    """
    llm = _get_llm()
    if not llm:
        raise HTTPException(status_code=502, detail="LLM not configured — set a provider API key in .env")

    # Search constitution for relevant articles
    constitution_context = ""
    try:
        store = _get_chroma_store()
        results = store.search(complaint_description, top_k=3)
        if results:
            ctx = store.get_search_context(results)
            if ctx:
                constitution_context = f"\n\nRelevant Constitutional Articles:\n{ctx}"
    except Exception:
        pass

    prompt = (
        f"You are a legal drafting assistant for Nepal. Draft a formal complaint letter "
        f"in English based on the following information. Use a professional legal tone.\n\n"
        f"Complainant Name: {name}\n"
        f"Permanent Address: {permanent_address}\n"
        f"Temporary Address: {temporary_address}\n"
        f"Citizenship No: {citizenship_no}\n"
        f"Phone: {phone}\n"
        f"Email: {email}\n\n"
        f"Complaint Description:\n{complaint_description}\n"
        f"{constitution_context}\n\n"
        f"Write the full complaint letter with: "
        f"1. To: [appropriate authority based on the complaint]\n"
        f"2. Subject line\n"
        f"3. Introduction of complainant\n"
        f"4. Detailed statement of facts\n"
        f"5. Legal basis (cite relevant constitutional articles where applicable)\n"
        f"6. Prayer/relief sought\n"
        f"7. Signature block\n"
        f"8. List of attached evidence/documents"
    )

    drafted = llm.generate(
        "You are a legal drafting assistant for Nepal. Draft formal complaint letters in English.",
        prompt,
    )

    # Generate PDF
    try:
        pdf_buf = generate_complaint_pdf(
            name=name,
            permanent_address=permanent_address,
            temporary_address=temporary_address,
            citizenship_no=citizenship_no,
            phone=phone,
            email=email,
            complaint_text=complaint_description,
            drafted_letter=drafted,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {e}")

    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        pdf_buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="complaint_letter.pdf"'},
    )


# ── Analysis Report ────────────────────────────────────────────────────────────


@app.post("/analysis-report", summary="Generate a legal analysis report and return PDF")
async def analysis_report(
    issue: str = Form(...),
):
    """Generate a legal analysis report based on a described issue, return as PDF.

    The LLM analyzes the issue against Nepali law (including constitution)
    and produces a structured report.
    """
    llm = _get_llm()
    if not llm:
        raise HTTPException(status_code=502, detail="LLM not configured — set a provider API key in .env")

    # Search constitution for relevant articles
    constitution_context = ""
    try:
        store = _get_chroma_store()
        results = store.search(issue, top_k=5)
        if results:
            ctx = store.get_search_context(results)
            if ctx:
                constitution_context = f"\n\nRelevant Constitutional Articles:\n{ctx}"
    except Exception:
        pass

    prompt = (
        f"You are a legal analyst for Nepal. Provide a detailed legal analysis "
        f"of the following issue. Ground your analysis in the Constitution of Nepal 2015 "
        f"and applicable Nepali laws.\n\n"
        f"Issue:\n{issue}\n"
        f"{constitution_context}\n\n"
        f"Structure your analysis as:\n"
        f"1. Summary of the Issue\n"
        f"2. Relevant Legal Provisions (constitution, laws, regulations)\n"
        f"3. Legal Analysis\n"
        f"4. Potential Violations Identified\n"
        f"5. Recommended Actions\n"
        f"6. References (specific articles, sections)"
    )

    analysis = llm.generate(
        "You are a legal analyst for Nepal. Provide detailed legal analysis grounded in Nepali law.",
        prompt,
    )

    # Generate PDF
    try:
        pdf_buf = generate_analysis_report_pdf(
            issue=issue,
            analysis_text=analysis,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {e}")

    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        pdf_buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="legal_analysis_report.pdf"'},
    )


# ── CLI Entry Point ───────────────────────────────────────────────────────────


def main():
    import uvicorn
    port = int(os.environ.get("API_PORT", "8000"))
    host = os.environ.get("API_HOST", "127.0.0.1")
    print(f"🚀 OpenTender + Counsel API running at http://{host}:{port}")
    print(f"📖 Docs available at http://{host}:{port}/docs")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
