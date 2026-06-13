"""Legal counsel, drafting, and risk-assessment components.

This package provides the Digital Lawyer — VirtualLawyer for legal counsel,
DraftGenerator for complaint drafting, LegalQueryEngine for jurisprudence
lookups, EvidenceChecklist for evidence preservation guidance, and
WhistleblowerRiskAssessment for whistleblower-specific risk analysis.
"""

from .counsel import VirtualLawyer
from .disclaimers import get_disclaimer
from .drafting import DraftGenerator
from .jurisprudence import LegalQueryEngine
from .evidence import EvidenceChecklist
from .risk_assessment import WhistleblowerRiskAssessment
