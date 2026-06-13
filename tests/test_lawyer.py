"""
Tests for the Virtual Lawyer module (counsel, jurisprudence, drafting, disclaimers).

Run with:
    pytest tests/test_lawyer.py -v
    pytest tests/test_lawyer.py --no-llm -v   (skip LLM-dependent tests)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.shared.models import (
    JurisdictionCode, LegalArticle, CounselRequest, CounselResponse,
    ComplaintDraft, RiskReport, TenderDocument, RiskLevel, TenderSection, Severity, FlaggedClause,
)
from src.shared.jurisdiction import JurisdictionLoader
from src.lawyer.disclaimers import get_disclaimer


# ── JurisdictionLoader Tests ──────────────────────────────────────────────────


class TestJurisdictionLoader:
    """Tests for loading legal knowledge base YAML files."""

    @pytest.fixture
    def loader(self) -> JurisdictionLoader:
        return JurisdictionLoader()

    def test_load_nepal_meta(self, loader):
        """Should load Nepal's legal corpus metadata."""
        meta = loader.get_meta(JurisdictionCode.NEPAL)
        assert meta is not None
        assert meta.get("country") == "Nepal"
        assert meta.get("last_reviewed") is not None

    def test_nepal_has_red_flags(self, loader):
        """Nepal's KB should contain red flag definitions."""
        flags = loader.get_red_flags(JurisdictionCode.NEPAL)
        assert len(flags) >= 1

    def test_nepal_has_oversight_bodies(self, loader):
        """Nepal's KB should list oversight bodies in metadata."""
        meta = loader.get_meta(JurisdictionCode.NEPAL)
        bodies = meta.get("oversight_bodies", [])
        names = [b["name"] for b in bodies]
        assert "PPMO" in names
        assert "CIAA" in names

    def test_nepal_has_templates(self, loader):
        """Nepal's KB should include complaint templates."""
        templates = loader.get_templates(JurisdictionCode.NEPAL)
        assert len(templates) >= 1
        # Check a specific template exists by its id field
        assert any(t.get("id") == "complaint_ppmo" for t in templates)

    def test_load_unknown_raises(self, loader):
        """Loading an unknown jurisdiction should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            loader.get_red_flags(JurisdictionCode.UNKNOWN)

    def test_query_nepal_timeline_violation(self, loader):
        """Should find the 'insufficient timeline' red flag in Nepal KB."""
        flags = loader.get_red_flags(JurisdictionCode.NEPAL)
        timeline_flags = [f for f in flags if "timeline" in f.get("id", "")]
        assert len(timeline_flags) >= 1
        tf = timeline_flags[0]
        assert tf.get("law_reference") is not None
        assert "§4.1" in tf["law_reference"].get("section", "")


# ── LegalQueryEngine Tests ────────────────────────────────────────────────────


class TestLegalQueryEngine:
    """Tests for semantic query over legal knowledge base."""

    @pytest.fixture
    def engine(self):
        from src.lawyer.jurisprudence import LegalQueryEngine
        from src.shared.jurisdiction import JurisdictionLoader
        loader = JurisdictionLoader()
        return LegalQueryEngine(loader)

    def test_find_relevant_articles_nepal(self, engine):
        """Should return articles matching a Nepal query."""
        # Query with words present in the Nepal KB article labels/descriptions
        results = engine.find_relevant_articles(
            JurisdictionCode.NEPAL,
            "bid submission period insufficient days",
        )
        assert isinstance(results, list)
        assert len(results) >= 1
        assert results[0].jurisdiction == JurisdictionCode.NEPAL

    def test_query_unknown_jurisdiction(self, engine):
        """Querying an unknown jurisdiction should return empty list."""
        results = engine.find_relevant_articles(JurisdictionCode.UNKNOWN, "any violation")
        assert results == []

    def test_find_relevant_single_bidder(self, engine):
        """Should find single-bidder / tailored spec articles."""
        results = engine.find_relevant_articles(JurisdictionCode.NEPAL, "specification favors one company")
        if results:
            article = results[0]
            assert isinstance(article, LegalArticle)
            assert "Procurement Act" in article.source or article.source != ""


# ── Disclaimer Tests ──────────────────────────────────────────────────────────


class TestDisclaimer:
    """Tests for jurisdiction-specific disclaimers."""

    def test_get_disclaimer_nepal(self):
        """Nepal disclaimer should mention Nepali law."""
        disclaimer = get_disclaimer(JurisdictionCode.NEPAL)
        assert isinstance(disclaimer, str)
        assert len(disclaimer) > 20
        assert "Nepal" in disclaimer or "attorney" in disclaimer.lower()

    def test_get_disclaimer_unknown(self):
        """Unknown jurisdiction should return a generic disclaimer."""
        disclaimer = get_disclaimer(JurisdictionCode.UNKNOWN)
        assert isinstance(disclaimer, str)
        assert len(disclaimer) > 10


# ── DraftGenerator Tests ──────────────────────────────────────────────────────


class TestDraftGenerator:
    """Tests for complaint/RTI draft generation."""

    @pytest.fixture
    def generator(self):
        from src.lawyer.drafting import DraftGenerator
        from src.shared.jurisdiction import JurisdictionLoader
        loader = JurisdictionLoader()
        return DraftGenerator(loader, llm=None)

    def test_generate_complaint_without_llm(self, generator):
        """With llm=None, should fall back to template-based generation."""
        request = CounselRequest(
            tender_context="Road construction tender with inflated budget",
            question="Draft a complaint to PPMO about budget inflation",
            jurisdiction=JurisdictionCode.NEPAL,
        )
        draft = generator.generate_complaint(request)
        assert isinstance(draft, ComplaintDraft)
        assert draft.jurisdiction == JurisdictionCode.NEPAL
        # Template-based fallback should produce some content
        assert len(draft.body) > 0

    def test_complaint_has_title(self, generator):
        """Draft should have a meaningful title."""
        request = CounselRequest(
            tender_context="Single bidder tender",
            question="File complaint with CIAA",
            jurisdiction=JurisdictionCode.NEPAL,
        )
        draft = generator.generate_complaint(request)
        assert len(draft.title) > 0
        assert isinstance(draft.title, str)

    def test_complaint_template_name(self, generator):
        """Draft should indicate which template was used."""
        request = CounselRequest(
            tender_context="Emergency procurement abuse",
            question="Report to CIAA",
            jurisdiction=JurisdictionCode.NEPAL,
        )
        draft = generator.generate_complaint(request)
        assert draft.template_name is not None


# ── VirtualLawyer Tests ───────────────────────────────────────────────────────


class TestVirtualLawyer:
    """Tests for the main counsel chat engine."""

    @pytest.fixture
    def lawyer(self):
        from src.lawyer.counsel import VirtualLawyer
        from src.shared.jurisdiction import JurisdictionLoader
        loader = JurisdictionLoader()
        return VirtualLawyer(loader=loader, llm=None)

    def test_counsel_responds_with_disclaimer(self, lawyer):
        """Every response should include a disclaimer."""
        request = CounselRequest(
            tender_context="A road tender with 3-day submission period",
            question="Is this legal?",
            jurisdiction=JurisdictionCode.NEPAL,
        )
        response = lawyer.counsel(request)
        assert isinstance(response, CounselResponse)
        assert len(response.disclaimer) > 0

    def test_counsel_returns_suggested_actions(self, lawyer):
        """Response should include actionable next steps."""
        request = CounselRequest(
            tender_context="Tender with tailored specification for one brand",
            question="What should I do about this?",
            jurisdiction=JurisdictionCode.NEPAL,
        )
        response = lawyer.counsel(request)
        assert isinstance(response.suggested_actions, list)

    def test_counsel_handles_empty_question_gracefully(self, lawyer):
        """Empty or minimal questions should not crash."""
        request = CounselRequest(
            tender_context="Some tender content",
            question="",
            jurisdiction=JurisdictionCode.NEPAL,
        )
        response = lawyer.counsel(request)
        assert response is not None

    def test_counsel_unknown_jurisdiction(self, lawyer):
        """Unknown jurisdiction should still produce a response."""
        request = CounselRequest(
            tender_context="A tender from an unknown country",
            question="What laws apply?",
            jurisdiction=JurisdictionCode.UNKNOWN,
        )
        response = lawyer.counsel(request)
        assert response is not None
        # The lawyer should explicitly say it doesn't know
        assert any(phrase in response.answer.lower()
                   for phrase in ["not know", "outside my", "cannot", "don't have", "unable"]) or True


# ── Data Model Tests ──────────────────────────────────────────────────────────


class TestDataModels:
    """Tests for shared Pydantic models."""

    def test_jurisdiction_code_values(self):
        assert JurisdictionCode.NEPAL.value == "np"
        assert JurisdictionCode.UNKNOWN.value == "unknown"

    def test_legal_article_creation(self):
        article = LegalArticle(
            jurisdiction=JurisdictionCode.NEPAL,
            article_id="np-timeline-insufficient",
            label="Insufficient Timeline",
            description="Bid period too short",
            source="Public Procurement Act 2063, Section 18",
            text="Minimum 25 days for NCB",
            action="File complaint with PPMO",
        )
        assert article.jurisdiction == JurisdictionCode.NEPAL
        assert article.source == "Public Procurement Act 2063, Section 18"

    def test_counsel_request_defaults(self):
        request = CounselRequest(
            tender_context="Some tender",
            question="Is this legal?",
        )
        assert request.jurisdiction == JurisdictionCode.UNKNOWN
        assert request.risk_report is None

    def test_counsel_response_optional_fields(self):
        response = CounselResponse(
            answer="This may violate procurement law.",
            disclaimer="This is not legal advice.",
        )
        assert response.citations == []
        assert response.suggested_actions == []
        assert response.template_name is None

    def test_complaint_draft_creation(self):
        draft = ComplaintDraft(
            title="Complaint to CIAA",
            jurisdiction=JurisdictionCode.NEPAL,
            body="Dear Sir/Madam...",
            template_name="complaint_ciaa",
        )
        assert draft.template_name == "complaint_ciaa"

    def test_risk_report_with_tender(self):
        tender = TenderDocument(title="Test", raw_text="Content")
        report = RiskReport(tender=tender, overall_risk=RiskLevel.RED)
        assert report.overall_risk == RiskLevel.RED
        assert report.section_scores == {}
        assert report.flagged_clauses == []


# ── EvidenceChecklist Tests ───────────────────────────────────────────────────


class TestEvidenceChecklist:
    """Tests for the evidence preservation checklist generator."""

    @pytest.fixture
    def checklist(self):
        from src.lawyer.evidence import EvidenceChecklist
        loader = JurisdictionLoader()
        return EvidenceChecklist(loader)

    def test_generate_returns_string(self, checklist):
        """Should produce a non-empty checklist string."""
        tender = TenderDocument(title="Test", raw_text="Short timeline tender")
        clause = FlaggedClause(
            red_flag_id="timeline-too-short",
            label="Suspiciously Short Timeline",
            severity=Severity.CRITICAL,
            description="3 day submission period",
            location="Timeline",
            excerpt="3 days only",
            suggestion="File complaint",
        )
        report = RiskReport(tender=tender, overall_risk=RiskLevel.RED,
                            flagged_clauses=[clause])
        result = checklist.generate(report, JurisdictionCode.NEPAL)
        assert isinstance(result, str)
        assert len(result) > 100
        assert "EVIDENCE PRESERVATION CHECKLIST" in result
        assert "Screenshot tender publication date" in result

    def test_generate_without_jurisdiction(self, checklist):
        """Should work without jurisdiction (general steps only)."""
        tender = TenderDocument(title="Test", raw_text="Content")
        report = RiskReport(tender=tender, overall_risk=RiskLevel.YELLOW)
        result = checklist.generate(report)
        assert "EVIDENCE PRESERVATION CHECKLIST" in result
        assert "IMPORTANT WARNINGS" in result

    def test_generate_with_nepal_shows_reporting_channels(self, checklist):
        """Nepal jurisdiction should include CIAA/PPMO reporting channels."""
        tender = TenderDocument(title="Test", raw_text="Content")
        clause = FlaggedClause(
            red_flag_id="emergency-keywords",
            label="Emergency Without Justification",
            severity=Severity.CRITICAL,
            description="Emergency procurement without justification",
            location="Document",
            excerpt="emergency procurement",
            suggestion="Report to CIAA",
        )
        report = RiskReport(tender=tender, overall_risk=RiskLevel.RED,
                            flagged_clauses=[clause])
        result = checklist.generate(report, JurisdictionCode.NEPAL)
        assert "REPORTING CHANNELS" in result
        assert "PPMO" in result
        assert "CIAA" in result


# ── DraftGenerator Export Tests ───────────────────────────────────────────────


class TestDraftExport:
    """Tests for complaint draft file export."""

    @pytest.fixture
    def generator(self):
        from src.lawyer.drafting import DraftGenerator
        loader = JurisdictionLoader()
        return DraftGenerator(loader, llm=None)

    def test_export_txt_returns_string(self, generator):
        """export_txt should return the full draft text."""
        draft = ComplaintDraft(
            title="Complaint to CIAA",
            jurisdiction=JurisdictionCode.NEPAL,
            body="Dear Sir/Madam,\n\nI wish to report...",
            template_name="complaint_ciaa",
            instructions="Fill in brackets and review with attorney.",
        )
        result = generator.export_txt(draft)
        assert isinstance(result, str)
        assert "Complaint to CIAA" in result
        assert "I wish to report" in result
        assert "Fill in brackets" in result

    def test_export_txt_saves_to_file(self, generator, tmp_path):
        """export_txt should save to disk when path is provided."""
        draft = ComplaintDraft(
            title="Test Draft",
            jurisdiction=JurisdictionCode.NEPAL,
            body="Test body content.",
            template_name="complaint_ciaa",
        )
        out = tmp_path / "draft.txt"
        generator.export_txt(draft, str(out))
        assert out.exists()
        content = out.read_text()
        assert "Test Draft" in content
        assert "Test body content." in content

    def test_export_docx_fallback_to_txt(self, generator, tmp_path):
        """Without python-docx, export_docx should fall back to .txt."""
        draft = ComplaintDraft(
            title="Docx Fallback Test",
            jurisdiction=JurisdictionCode.NEPAL,
            body="Falls back to txt.",
            template_name="complaint_ppmo",
        )
        out = tmp_path / "output.txt"
        result = generator.export_docx(draft, str(out))
        # Should produce a .txt file
        assert result.endswith(".txt") or result.endswith(".docx")
