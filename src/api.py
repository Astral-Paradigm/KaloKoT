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

from src.analyzer import TenderExtractor, RiskScorer, ReportGenerator
from src.lawyer import VirtualLawyer, EvidenceChecklist
from src.lawyer.drafting import DraftGenerator
from src.shared.jurisdiction import JurisdictionLoader
from src.shared.llm import LLMClient
from src.shared.models import (
    ComplaintDraft, CounselRequest, CounselResponse,
    JurisdictionCode, RiskReport, TenderDocument,
)

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
            "GET /jurisdictions": "List available legal jurisdictions",
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
