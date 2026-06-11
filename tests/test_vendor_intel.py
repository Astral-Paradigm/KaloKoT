"""Tests for the Vendor Intelligence module."""
from src.analyzer.vendor_intel import VendorIntelligence, VendorProfile


class TestVendorIntel:
    def test_clean_vendor_no_flags(self):
        v = VendorProfile(
            name="Kathmandu Construction Pvt Ltd",
            registration_number="C-12345",
            registration_date="2020-01-15",
            directors=["Ram Acharya", "Hari Gurung"],
            address="Kathmandu, Nepal",
        )
        intel = VendorIntelligence()
        overall, flags = intel.assess(v)
        assert overall.value == "green"
        assert len(flags) == 0

    def test_po_box_only_is_medium(self):
        v = VendorProfile(
            name="Quick Trading",
            registration_number="C-99999",
            address="P.O. Box 1234",
        )
        intel = VendorIntelligence()
        overall, flags = intel.assess(v)
        assert any("PO Box" in f.label for f in flags)
        assert any(f.category == "shell" for f in flags)

    def test_recent_registration_flagged(self):
        from datetime import datetime
        recent = datetime.now().strftime("%Y-%m-%d")
        v = VendorProfile(
            name="New Company",
            registration_number="C-NEW-1",
            registration_date=recent,
            address="Kathmandu",
        )
        intel = VendorIntelligence()
        overall, flags = intel.assess(v)
        assert any("Recently Registered" in f.label for f in flags)
        assert any(f.category == "registration" for f in flags)

    def test_pep_title_signal(self):
        v = VendorProfile(
            name="Ex-Minister Enterprises",
            directors=["Former Minister Baburam Thapa"],
            address="Lalitpur",
        )
        intel = VendorIntelligence()
        overall, flags = intel.assess(v)
        assert any("Politically Exposed" in f.label for f in flags)
        assert any(f.category == "pep" for f in flags)

    def test_known_shell_critical(self):
        v = VendorProfile(name="Shell Corp Ltd", address="Kathmandu")
        intel = VendorIntelligence(known_shells=["Shell Corp Ltd"])
        overall, flags = intel.assess(v)
        assert any("Known Shell" in f.label for f in flags)
        assert any(f.severity.value == "critical" for f in flags)
