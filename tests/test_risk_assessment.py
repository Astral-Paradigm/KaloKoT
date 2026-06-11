"""Tests for the Whistleblower Risk Assessment module."""
from src.lawyer.risk_assessment import WhistleblowerRiskAssessment
from src.shared.models import JurisdictionCode


class TestWhistleblowerRisk:
    def setup_method(self):
        self.assessor = WhistleblowerRiskAssessment()

    def test_nepal_assessment_basic(self):
        result = self.assessor.assess(JurisdictionCode.NEPAL)
        assert result["jurisdiction"] == "Nepal"
        assert result["overall_risk"] in ("high", "extreme")
        assert result["anonymity"]["level"] in ("pseudo", "anonymous")
        assert len(result["legal_protections"]) > 0
        assert len(result["recommended_channels"]) > 0
        assert len(result["precaution_steps"]) > 0

    def test_government_employee_risk_increases(self):
        normal = self.assessor.assess(JurisdictionCode.NEPAL)
        employee = self.assessor.assess(JurisdictionCode.NEPAL, is_government_employee=True)
        assert employee["is_government_employee"] is True

    def test_missing_evidence_warning(self):
        result = self.assessor.assess(JurisdictionCode.NEPAL, has_evidence_copies=False)
        assert "critical_warning" in result
        assert "copies of evidence" in result["critical_warning"].lower()

    def test_has_evidence_no_warning(self):
        result = self.assessor.assess(JurisdictionCode.NEPAL, has_evidence_copies=True)
        assert "critical_warning" not in result

    def test_unknown_jurisdiction_fallback(self):
        result = self.assessor.assess(JurisdictionCode.UNKNOWN)
        assert result["jurisdiction"] == "Unknown"
        assert result["overall_risk"] == "high"
        assert result["witness_protection"]["level"] == "none"

    def test_retaliation_indicators_present(self):
        result = self.assessor.assess(JurisdictionCode.NEPAL)
        assert len(result["retaliation_indicators"]) > 0
