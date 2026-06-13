"""Shared Pydantic data models for OpenTender + Counsel.

All request/response types used across the system live here:
tender risk analysis, legal counsel, complaint drafts, and vendor assessments.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


# ── Enums ────────────────────────────────────────────────────────────

class JurisdictionCode(str, Enum):
    """Supported legal jurisdictions."""
    NEPAL = "np"
    UNKNOWN = "unknown"


class TenderSection(str, Enum):
    """Known sections within a tender document."""
    DETAILS = "details"
    SPECIFICATION = "specification"
    BUDGET = "budget"
    TIMELINE = "timeline"
    EVALUATION_CRITERIA = "evaluation_criteria"
    TERMS = "terms_and_conditions"


class Severity(str, Enum):
    """Severity level for a flagged clause in a tender."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskLevel(str, Enum):
    """Overall risk indicator for a tender or vendor."""
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


# ── Tender / Risk Analysis ───────────────────────────────────────────

class TenderSectionData(BaseModel):
    """One parsed section from a tender document."""
    section: TenderSection
    heading: str
    content: str
    page_range: Optional[str] = None


class TenderDocument(BaseModel):
    """Structured representation of a parsed tender document."""
    title: str
    reference_no: Optional[str] = None
    procuring_entity: Optional[str] = None
    estimated_value: Optional[str] = None
    currency: Optional[str] = None
    publication_date: Optional[str] = None
    submission_deadline: Optional[str] = None
    sections: List[TenderSectionData] = Field(default_factory=list)
    raw_text: str = ""


class FlaggedClause(BaseModel):
    """A specific clause in the tender that raises a red flag."""
    red_flag_id: str
    label: str
    severity: Severity
    description: str                               # what was found
    location: str                                  # e.g. "Section 7.3, Page 12"
    excerpt: str                                   # actual text from the tender
    law_reference: Optional[str] = None
    risk_reason: str = ""                          # WHY it's a corruption risk
    suggestion: str = ""


class RiskReport(BaseModel):
    """Complete risk analysis for a tender."""
    tender: TenderDocument
    overall_risk: RiskLevel
    section_scores: dict[str, RiskLevel] = Field(default_factory=dict)
    flagged_clauses: List[FlaggedClause] = Field(default_factory=list)
    summary: str = ""


# ── Legal & Counsel ──────────────────────────────────────────────────

class LegalArticle(BaseModel):
    """A specific law/regulation article from the legal corpus."""
    jurisdiction: JurisdictionCode
    article_id: str
    label: str
    description: str
    source: str                                    # e.g. "Public Procurement Act 2063, Section 18"
    text: str
    penalty: Optional[str] = None
    action: str = ""
    report_template: Optional[str] = None


class CounselRequest(BaseModel):
    """Request to the Virtual Lawyer."""
    tender_context: str                            # tender summary / red flags
    question: str
    jurisdiction: JurisdictionCode = JurisdictionCode.UNKNOWN
    risk_report: Optional[RiskReport] = None


class CounselResponse(BaseModel):
    """Response from the Virtual Lawyer."""
    answer: str
    citations: List[LegalArticle] = Field(default_factory=list)
    suggested_actions: List[str] = Field(default_factory=list)
    template_name: Optional[str] = None
    template_content: Optional[str] = None
    disclaimer: str = ""


class ComplaintDraft(BaseModel):
    """A generated complaint / FOIA / RTI draft."""
    title: str
    jurisdiction: JurisdictionCode
    body: str
    template_name: str
    instructions: str = ""


# ── Vendor & Risk Assessment ─────────────────────────────────────────

class VendorAssessment(BaseModel):
    """Vendor / contractor risk assessment result."""
    vendor_name: str
    overall_risk: RiskLevel
    flags: list = Field(default_factory=list)
    registration_age_days: Optional[int] = None
    pep_signal: bool = False


class RiskAssessmentResult(BaseModel):
    """Whistleblower personal risk assessment outcome."""
    jurisdiction: str
    overall_risk: str
    summary: str
    anonymity: dict = Field(default_factory=dict)
    witness_protection: dict = Field(default_factory=dict)
    legal_protections: list = Field(default_factory=list)
    recommended_channels: list = Field(default_factory=list)
    retaliation_indicators: list = Field(default_factory=list)
    precaution_steps: list = Field(default_factory=list)
    critical_warning: Optional[str] = None
