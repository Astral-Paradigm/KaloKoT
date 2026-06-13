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
import json
import os
import sys
import uuid
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Dict, Optional

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
import logging
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

# Rate limiting
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

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

# Configure logging
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("justice_api")

from src.analyzer import TenderExtractor, RiskScorer, ReportGenerator, VendorIntelligence, VendorProfile
from src.lawyer import VirtualLawyer, EvidenceChecklist
from src.lawyer.drafting import DraftGenerator
from src.lawyer.risk_assessment import WhistleblowerRiskAssessment
from src.shared.jurisdiction import JurisdictionLoader
from src.shared.llm import LLMClient, FallbackLLMClient, create_llm_client
from src.shared.chunking import chunk_constitution, get_all_parent_texts
from src.shared.chroma_store import ChromaLegalStore
from src.shared.pdf_generator import generate_complaint_pdf, generate_analysis_report_pdf
from src.shared.models import (
    ComplaintDraft, CounselRequest, CounselResponse,
    JurisdictionCode, RiskReport, TenderDocument,
)
from src.shared.tts import speak_text, clean_for_tts
from src.shared.vector_search import LegalVectorSearch

# ── Application Setup ─────────────────────────────────────────────────────────

app = FastAPI(
    title="OpenTender + Counsel API",
    description="Procurement corruption risk analyzer and virtual lawyer for public procurement documents.",
    version="1.0.0",
)

# ── Rate Limiting ──────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:8080,http://127.0.0.1:8080,http://localhost:8000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Global Instance Cache ─────────────────────────────────────────────────────
# Lazy-initialized singletons shared across endpoints to avoid redundant setup

_instances: dict = {}  # Holds lazy-init'd clients (loader, scorer, llm, lawyer, ...)
_report_cache: Dict[str, RiskReport] = {}  # In-memory store for generated risk reports (keyed by short UUID)


# ── Startup ────────────────────────────────────────────────────────────────────

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


def _get_llm(provider: Optional[str] = None) -> LLMClient | FallbackLLMClient | None:
    """Get or create an LLMClient using the unified factory.

    If a provider is specified, create a new client for that provider.
    Falls back to pre-loaded Phi model for backup when primary is unavailable.
    Otherwise return the cached default client.
    """
    if provider:
        return create_llm_client(provider=provider)
    if "llm" not in _instances:
        _instances["llm"] = create_llm_client()
    return _instances["llm"]


def _resolve_jurisdiction(jurisdiction: str) -> JurisdictionCode:
    """Resolve a jurisdiction string to JurisdictionCode enum."""
    j = jurisdiction.strip().lower()
    if j in ("unknown", ""):
        return JurisdictionCode.NEPAL
    for code in JurisdictionCode:
        if code.value == j or code.name.lower() == j:
            return code
    return JurisdictionCode.NEPAL


def _get_lawyer(provider: Optional[str] = None) -> VirtualLawyer:
    """Get or create a VirtualLawyer.

    If a provider is specified, create a new lawyer with that LLM provider.
    Otherwise return the cached default lawyer.
    """
    if provider:
        return VirtualLawyer(_get_loader(), _get_llm(provider=provider))
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
        _instances["vendor_intel"] = VendorIntelligence(loader=_get_loader())
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
    """Lazy-init the ChromaDB store and auto-index the Constitution of Nepal on first call."""
    if "chroma_store" not in _instances:
        store = ChromaLegalStore()
        # Auto-index the Constitution of Nepal into ChromaDB on startup
        loader = _get_loader()
        try:
            import yaml
            const_path = Path(__file__).resolve().parent.parent / "docs" / "legal" / "np_constitution.yaml"
            if const_path.exists():
                with open(const_path) as f:
                    const_data = yaml.safe_load(f)
                n = store.index_constitution(const_data)
                logger.info(f"Indexed {n} constitution chunks")
        except Exception as e:
            logger.warning(f"Constitution index: {e}")
        _instances["chroma_store"] = store
    return _instances["chroma_store"]


# ── Helper: Build TenderDocument with optional jurisdiction hint ──────────────


def _analyze_text(text: str, title: str = "Uploaded Tender") -> RiskReport:
    """Extract → score → return risk report from raw text."""
    loader = _get_loader()
    scorer = _get_scorer()

    # Auto-detect jurisdiction from content (e.g. mentions of "Nepal", "CIAA", etc.)
    jurisdiction = loader.detect_jurisdiction_from_text(text)
    tender = TenderDocument(title=title, raw_text=text)
    report = scorer.score(tender)
    return report


# ── Endpoints ─────────────────────────────────────────────────────────────────

# ── Service Information ──

@app.get("/")
async def root():
    """Return API metadata and a directory of all available endpoints."""
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
    """Simple liveness probe — returns {'status': 'ok'} when the server is running."""
    return {"status": "ok"}


@app.get("/providers", summary="List available LLM providers and their status")
async def list_providers():
    """Return status of all LLM providers (configured, Phi loading state)."""
    return {
        "providers": {
            "gemini": bool(os.environ.get("GEMINI_API_KEY")),
            "anthropic": bool(os.environ.get("ANTHROPIC_API_KEY")),
            "openai": bool(os.environ.get("OPENAI_API_KEY")),
            "openrouter": bool(os.environ.get("OPENROUTER_API_KEY")),
        },
    }


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


# ── Tender Analysis ──

_MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20 MB

_IMAGE_MAGIC_PREFIXES = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG": "image/png",
    b"GIF87a": "image/gif",
    b"GIF89a": "image/gif",
    b"RIFF": "image/webp",
    b"BM": "image/bmp",
}


def _validate_image_magic(data: bytes) -> None:
    header = data[:16]
    for magic in _IMAGE_MAGIC_PREFIXES:
        if header.startswith(magic):
            return
    raise HTTPException(status_code=400, detail="File content does not match image type")


@app.post("/analyze", summary="Upload a tender file for analysis")
@limiter.limit("20/minute")
async def analyze_file(request: Request, file: UploadFile = File(...)):
    """Upload a tender document (PDF, TXT, HTML, or Image) and get a corruption risk analysis.

    Supported formats:
    - Text: PDF, TXT, HTML, HTM
    - Images: JPEG, PNG, GIF, WebP (text extracted via Gemini vision OCR)
    """
    raw = await file.read()
    if len(raw) > _MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="File too large — max 20 MB")

    content_type = file.content_type or ""
    filename = (file.filename or "").lower()
    ext = Path(filename).suffix.lower()

    # Detect image by MIME type or extension — images require Gemini OCR for text extraction
    image_mimes = {"image/jpeg", "image/png", "image/gif", "image/webp", "image/bmp"}
    image_exts = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}

    if content_type in image_mimes or ext in image_exts:
        # Verify magic bytes match the claimed image type
        _validate_image_magic(raw)
        # Map extension to MIME for Gemini
        mime_map = {
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".png": "image/png", ".gif": "image/gif",
            ".webp": "image/webp", ".bmp": "image/bmp",
        }
        try:
            llm = _get_llm()
            if not llm:
                raise HTTPException(status_code=502, detail="LLM not configured — set GEMINI_API_KEY in .env")
            text = llm.extract_text_from_image(raw, mime_type=mime_map.get(ext, "image/png"))
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=500, detail="OCR extraction failed")
    else:
        # Treat as plain text — decode with fallback for non-UTF-8 bytes
        text = raw.decode("utf-8", errors="replace")

    # Run the core analysis pipeline (extract → score → RiskReport)
    report = _analyze_text(text, title=filename or "Uploaded Tender")
    # Generate a short unique ID so the report can be retrieved later
    report_id = uuid.uuid4().hex
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
                "risk_reason": c.risk_reason,
                "suggestion": c.suggestion,
            }
            for c in report.flagged_clauses
        ],
    }


@app.post("/analyze-text", summary="Submit tender text for analysis")
@limiter.limit("30/minute")
async def analyze_text(request: Request, text: str = Form(...), title: str = Form("Uploaded Tender")):
    """Submit tender document text directly and get a corruption risk analysis."""
    report = _analyze_text(text, title=title)
    report_id = uuid.uuid4().hex
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
                "risk_reason": c.risk_reason,
                "suggestion": c.suggestion,
            }
            for c in report.flagged_clauses
        ],  # end flagged_clauses
    }  # end /analyze-text response


# ── Report Retrieval ──

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
                "risk_reason": c.risk_reason,
                "suggestion": c.suggestion,
            }
            for c in report.flagged_clauses
        ],
        "full_report": reporter.generate_text(report),
    }


# ── API Key Management ──


@app.post("/set-api-key", summary="Store an API key for a provider in the server cache")
@limiter.limit("60/minute")
async def set_api_key(
    request: Request,
    provider: str = Form(...),
    api_key: str = Form(...),
):
    """Store a provider API key in the server's memory cache for the session duration."""
    _instances[f"api_key_{provider}"] = api_key
    logger.info(f"API key stored for provider: {provider}")
    return {"status": "ok", "provider": provider}


def _get_llm_with_key(provider: str, api_key: Optional[str] = None) -> LLMClient | FallbackLLMClient | None:
    """Create an LLM client using a provided API key or fall back to auto-detect."""
    if not provider:
        return _get_llm()

    effective_key = api_key or _instances.get(f"api_key_{provider}") or os.environ.get(f"{provider.upper()}_API_KEY")

    if effective_key:
        return create_llm_client(provider=provider, api_key=effective_key)

    return None


# ── Legal Counsel ──

@app.post("/counsel", summary="Ask the Virtual Lawyer a question")
@limiter.limit("30/minute")
async def counsel(
    request: Request,
    question: str = Form(...),
    tender_context: str = Form(""),
    jurisdiction: str = Form("unknown"),
    report_id: Optional[str] = Form(None),
    provider: Optional[str] = Form(None),
    api_key: Optional[str] = Form(None),
    chat_history: Optional[str] = Form(""),
):
    """Ask the Virtual Lawyer about a tender's legal implications."""
    loader = _get_loader()

    # Use the new key-aware LLM getter
    llm = _get_llm_with_key(provider or "", api_key=api_key)
    if llm:
        lawyer = VirtualLawyer(loader, llm)
    else:
        if provider and provider not in ("none", "rule", "rule-based"):
            return {"answer": f"The {provider} provider is not configured. Set the API key in the provider selector or in .env.", "citations": [], "suggested_actions": [], "disclaimer": "", "template_name": None}
        if provider == "rule-based":
            lawyer = VirtualLawyer(loader, None)
        else:
            lawyer = _get_lawyer()

    # Resolve jurisdiction string to enum
    jcode = _resolve_jurisdiction(jurisdiction)

    # If the user provided a report_id, prepend the cached report summary as context
    context = tender_context
    if report_id and report_id in _report_cache:
        report = _report_cache[report_id]
        context = f"{report.tender.title or 'Tender'}\n{report.summary}\n\n{context}"

    # Search the Constitution via ChromaDB (semantic retrieval) — mirrors main.py
    constitution_context = ""
    try:
        store = _get_chroma_store()
        if store.count() > 0:
            search_results = store.search(question, top_k=4)
            if search_results:
                constitution_context = store.get_search_context(search_results)
    except Exception:
        pass

    counsel_req = CounselRequest(
        tender_context=context,
        question=question,
        jurisdiction=jcode,
    )

    # Parse chat history JSON if provided
    parsed_history: list[dict] = []
    if chat_history:
        try:
            parsed_history = json.loads(chat_history)
        except (json.JSONDecodeError, TypeError):
            pass

    # Pass constitution context and chat history to the lawyer
    try:
        response = lawyer.counsel(counsel_req, constitution_context=constitution_context, chat_history=parsed_history)
    except Exception:
        logger.warning("LLM counsel failed (quota/rate-limit), falling back to rule-based")
        fallback = VirtualLawyer(loader, None)
        response = fallback.counsel(counsel_req, constitution_context=constitution_context, chat_history=parsed_history)
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


# ── Evidence & Drafting ──

@app.post("/checklist", summary="Generate evidence checklist")
@limiter.limit("20/minute")
async def generate_checklist(request: Request,
                              report_id: str = Form(...),
                              jurisdiction: str = Form("unknown")):
    """Generate an evidence preservation checklist based on a risk report."""
    if report_id not in _report_cache:
        raise HTTPException(status_code=404, detail="Report not found")

    report = _report_cache[report_id]
    jcode = _resolve_jurisdiction(jurisdiction)

    checklist = _get_checklist()
    text = checklist.generate(report, jcode)
    return PlainTextResponse(text)


@app.post("/export-draft", summary="Export complaint draft as .txt")
@limiter.limit("20/minute")
async def export_draft(
    request: Request,
    title: str = Form(...),
    body: str = Form(...),
    jurisdiction: str = Form("unknown"),
    template_name: str = Form(""),
    instructions: str = Form(""),
):
    """Export a complaint draft as a downloadable .txt file using the jurisdiction-specific template engine."""
    # Resolve jurisdiction string to enum for template selection
    jcode = _resolve_jurisdiction(jurisdiction)

    # Build the draft model and render via the DraftGenerator
    draft = ComplaintDraft(
        title=title,
        jurisdiction=jcode,
        body=body,
        template_name=template_name or "",
        instructions=instructions or "Review with a qualified attorney before filing.",
    )

    generator = _get_draft_generator()
    text = generator.export_txt(draft)

    # Return as a downloadable plain-text file
    return PlainTextResponse(
        text,
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{title.replace(" ", "_")}.txt"'},
    )


# ── Vendor & Risk Assessment ──

@app.post("/vendor-intel", summary="Assess vendor/contractor risk")
@limiter.limit("30/minute")
async def vendor_intelligence(
    request: Request,
    vendor_name: str = Form(...),
    registration_number: Optional[str] = Form(None),
    registration_date: Optional[str] = Form(None),
    directors: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
):
    """Assess a vendor/contractor for shell company indicators, PEP connections, and registration risk."""
    # Parse comma-separated directors string into a list
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


@app.post("/risk-assessment")
@limiter.limit("30/minute")
async def whistleblower_risk(
    request: Request,
    jurisdiction: str = Form(...),
    is_government_employee: bool = Form(False),
    has_evidence_copies: bool = Form(False),
):
    """Assess personal risk if you blow the whistle on procurement corruption.

    Provides jurisdiction-specific retaliation likelihood, anonymity options,
    witness protection availability, and precaution steps.
    """
    jcode = _resolve_jurisdiction(jurisdiction)
    assessor = _get_risk_assessment()
    # Runs jurisdiction-specific analysis: retaliation likelihood, anonymity, witness protection
    result = assessor.assess(jcode, is_government_employee, has_evidence_copies)
    return result


# ── Legal Knowledge Search ──

@app.post("/legal-search")
@limiter.limit("30/minute")
async def legal_search(
    request: Request,
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

    jcode = _resolve_jurisdiction(jurisdiction)

    # Load YAML data for the selected jurisdiction and run hybrid search
    try:
        yaml_data = loader.load_yaml(jcode)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Jurisdiction '{jurisdiction}' not found")

    searcher.index_jurisdiction(yaml_data)
    # Combines keyword (TF-IDF) and semantic (embedding) scoring
    results = searcher.hybrid_search(query, top_k=top_k, threshold=threshold)
    return {"query": query, "jurisdiction": jurisdiction, "results": results}


# ── Constitution (Nepal) Search ──

@app.post("/constitution-search", summary="Search Constitution of Nepal via ChromaDB")
@limiter.limit("30/minute")
async def constitution_search(
    request: Request,
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
    # Search child-level clause chunks; optionally resolve up to parent Articles
    raw_results = store.search(query, top_k=top_k)

    context = ""
    if resolve_parents:
        # Assemble full Article/Part context around matched clauses
        context = store.get_search_context(raw_results)

    return {
        "query": query,
        "results": [
            {
                "child_id": r["child_id"],
                "child_text": r["child_text"],
                "score": r["score"],
                "parent_id": r.get("parent_id", ""),
                "parent_title": r.get("parent_title", ""),
                "part_title": r.get("part_title", ""),
                "path": r.get("path", []),
            }
            for r in raw_results
        ],
        "context": context if resolve_parents else "",
    }


@app.get("/constitution-context", response_class=PlainTextResponse)
@limiter.limit("60/minute")
async def constitution_context(request: Request):
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
@limiter.limit("10/minute")
async def text_to_speech(request: Request, text: str = Form(...)):
    """Convert text to speech using ElevenLabs with a deep male voice (Adam)."""
    # Strip markdown/formatting so TTS doesn't read "star star Article 24 star star"
    clean_text = clean_for_tts(text)
    audio = speak_text(clean_text)
    if audio is None:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "TTS unavailable",
                "reason": "ELEVENLABS_API_KEY not set or ElevenLabs request failed",
                "fix": "Add ELEVENLABS_API_KEY=<your_key> to .env file in the project root",
            },
        )
    from fastapi.responses import StreamingResponse
    return StreamingResponse(audio, media_type="audio/mpeg")


# ── Complaint Drafting ─────────────────────────────────────────────────────────


@app.post("/draft-complaint", summary="Draft a formal complaint letter and return PDF")
@limiter.limit("10/minute")
async def draft_complaint(request: Request, name: str = Form(...),
    permanent_address: str = Form(...),
    temporary_address: str = Form(...),
    citizenship_no: str = Form(...),
    phone: str = Form(...),
    email: str = Form(...),
    complaint_description: str = Form(...),
    complaint_date: str = Form(""),
):
    """Draft a formal complaint letter using template matching + LLM personalization.

    Flow:
    1. Compare complaint subject against 16 Nepal complaint template subject_tags
    2. LLM checks if description matches a template's subject
    3. If match: personalize that template with user's info
    4. If no match: LLM generates a fresh letter from scratch
    5. Wraps in downloadable PDF
    """
    llm = _get_llm()
    if not llm:
        raise HTTPException(status_code=502, detail="LLM not configured — set a provider API key in .env")

    # Load templates with subject_tags
    loader = _get_loader()
    try:
        templates = loader.get_templates(JurisdictionCode.NEPAL)
    except Exception:
        templates = []

    # ── Step 1: Let LLM pick the best matching template ──────
    matched_template = None
    if templates:
        template_catalog = "\n".join(
            f"[{t.get('template_name')}] {t.get('title')} — tags: {', '.join(t.get('subject_tags', []))}"
            for t in templates
        )
        match_prompt = (
            f"Read the complaint description below. From this catalog of Nepal legal complaint templates, "
            f"choose the ONE best-matching template_name based on subject_tags. "
            f"If none match well, respond with 'NONE'.\n\n"
            f"Template Catalog:\n{template_catalog}\n\n"
            f"Complaint Description:\n{complaint_description}\n\n"
            f"Answer with ONLY the template_name or 'NONE':"
        )
        try:
            chosen = llm.generate(
                "You match user complaints to the best legal complaint template. Be precise.",
                match_prompt,
                temperature=0.1,
                max_tokens=64,
            )
            chosen = chosen.strip().strip('"').strip("'")
            if chosen and chosen != "NONE":
                for t in templates:
                    if t.get("template_name") == chosen:
                        matched_template = t
                        break
        except Exception:
            pass

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

    if matched_template:
        # ── Step 2: Personalize the matched template ──
        template_body = matched_template.get("body", "")
        filing_body = matched_template.get("filing_body", "the appropriate authority")
        personalization_prompt = (
            f"You are a legal drafting assistant for Nepal. The user's complaint matches "
            f"the '{matched_template['title']}' template. Personalize the template below "
            f"by filling in ALL [bracketed] placeholders with the user's details. "
            f"Use a professional legal tone. Keep the structure of the original template.\n\n"
            f"Filing Body: {filing_body}\n"
            f"Complainant Name: {name}\n"
            f"Permanent Address: {permanent_address}\n"
            f"Temporary Address: {temporary_address}\n"
            f"Citizenship No: {citizenship_no}\n"
            f"Phone: {phone}\n"
            f"Email: {email}\n"
            f"Complaint Description: {complaint_description}\n"
            f"{constitution_context}\n\n"
            f"TEMPLATE BODY:\n{template_body}\n\n"
            f"Output the complete, personalized letter. Replace every [bracket] with the user's "
            f"actual information. Add specific facts from their complaint description. "
            f"Sign off with the complainant's name."
        )
        drafted = llm.generate(
            "You are a legal drafting assistant for Nepal. Personalize complaint letter templates.",
            personalization_prompt,
            temperature=0.3,
            max_tokens=4096,
        )
    else:
        # ── Step 3: Generate fresh from scratch ──
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
            complaint_date=complaint_date,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail="PDF generation failed")

    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        pdf_buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="complaint_letter.pdf"'},
    )


# ── Analysis Report ────────────────────────────────────────────────────────────


@app.post("/analysis-report", summary="Generate a legal analysis report and return PDF")
@limiter.limit("10/minute")
async def analysis_report(request: Request, issue: str = Form(...),):
    """Generate a legal analysis report based on a described issue, return as PDF.

    The LLM analyzes the issue against Nepali law (including constitution)
    and produces a structured report.
    """
    llm = _get_llm()
    if not llm:
        raise HTTPException(status_code=502, detail="LLM not configured — set a provider API key in .env")

    # Search constitution for relevant articles to ground the analysis against Nepali law
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
        raise HTTPException(status_code=500, detail="PDF generation failed")

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
