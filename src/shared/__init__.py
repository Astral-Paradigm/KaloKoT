"""Shared domain models, utilities, and retrieval components.

This package provides the common data models (tenders, reports, legal articles),
document chunking and embedding utilities, vector search for legal texts,
and the ChromaDB-backed legal store used throughout the system.
"""

from .models import (
    JurisdictionCode, TenderSection, Severity, RiskLevel,
    TenderSectionData, TenderDocument, FlaggedClause,
    RiskReport, LegalArticle, CounselRequest, CounselResponse,
    ComplaintDraft, VendorAssessment, RiskAssessmentResult,
)
from .chunker import DocumentChunker, DocumentChunk, ChunkEmbedder
from .vector_search import LegalVectorSearch, TfidfVectorizer
from .chunking import chunk_constitution, resolve_parents, get_all_parent_texts
from .chroma_store import ChromaLegalStore
