"""Tender analysis, parsing, risk scoring, and reporting components.

This package provides TenderExtractor for extracting text from tenders,
TenderParser for LLM-driven parsing, RiskScorer for corruption risk analysis,
ReportGenerator for producing text/HTML/heatmap reports, and VendorIntelligence
for vendor background checks and risk flagging.
"""

from .extractor import TenderExtractor
from .parser import TenderParser
from .scorer import RiskScorer
from .reporter import ReportGenerator
from .vendor_intel import VendorIntelligence, VendorProfile, VendorRiskFlag
