"""Jurisdiction loader — loads legal knowledge base YAML files."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from .models import JurisdictionCode, LegalArticle


LEGAL_DIR = Path(__file__).resolve().parent.parent.parent / "docs" / "legal"


class JurisdictionLoader:
    """Loads and queries legal knowledge base YAML files per jurisdiction."""

    def __init__(self, legal_dir: Optional[Path] = None):
        self.legal_dir = legal_dir or LEGAL_DIR
        self._cache: Dict[str, dict] = {}

    def _load(self, code: str) -> dict:
        """Load a jurisdiction YAML file, cached."""
        if code in self._cache:
            return self._cache[code]

        path = self.legal_dir / f"{code}.yaml"
        if not path.exists():
            raise FileNotFoundError(f"Legal corpus not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        self._cache[code] = data
        return data

    def list_jurisdictions(self) -> List[dict]:
        """Return list of available jurisdictions with metadata."""
        results = []
        for path in sorted(self.legal_dir.glob("*.yaml")):
            data = self._load(path.stem)
            meta = data.get("meta", {})
            results.append({
                "code": path.stem,
                "country": meta.get("country", "Unknown"),
                "last_reviewed": meta.get("last_reviewed", "Unknown"),
            })
        return results

    def get_meta(self, jurisdiction: JurisdictionCode) -> dict:
        """Get jurisdiction metadata."""
        data = self._load(jurisdiction.value)
        meta = data.get("meta", {})
        return meta

    def get_red_flags(self, jurisdiction: JurisdictionCode) -> List[dict]:
        """Get all red flag definitions for a jurisdiction."""
        data = self._load(jurisdiction.value)
        return data.get("red_flags", [])

    def get_templates(self, jurisdiction: JurisdictionCode) -> List[dict]:
        """Get all report templates for a jurisdiction."""
        data = self._load(jurisdiction.value)
        return data.get("templates", [])

    def get_template_by_name(self, jurisdiction: JurisdictionCode,
                             template_name: str) -> Optional[dict]:
        """Get a specific template by its key name."""
        data = self._load(jurisdiction.value)
        templates = data.get("templates", {})
        return templates.get(template_name)

    def find_matching_red_flags(self, jurisdiction: JurisdictionCode,
                                risk_report_flagged_ids: List[str]) -> List[dict]:
        """Return full red flag definitions matching flagged clause IDs."""
        all_flags = self.get_red_flags(jurisdiction)
        matched = []
        for flag in all_flags:
            if flag.get("id") in risk_report_flagged_ids:
                matched.append(flag)
        return matched

    def build_legal_context(self, jurisdiction: JurisdictionCode,
                            flagged_ids: Optional[List[str]] = None) -> str:
        """Build a legal context summary string for LLM prompts.

        Includes relevant red flags + their law references.
        """
        if jurisdiction == JurisdictionCode.UNKNOWN:
            return "Jurisdiction not specified. Check user for location."

        try:
            flags = self.get_red_flags(jurisdiction)
        except FileNotFoundError:
            return f"Legal corpus for {jurisdiction.value} not yet available."

        if flagged_ids:
            flags = [f for f in flags if f.get("id") in flagged_ids]

        meta = self.get_meta(jurisdiction)
        lines = [
            f"=== Jurisdiction: {meta.get('country', 'Unknown')} ===",
            f"Last reviewed: {meta.get('last_reviewed', 'Unknown')}",
            f"Disclaimer: {meta.get('disclaimer', 'See source files.')}",
            "",
            "Oversight Bodies:",
        ]

        for body in meta.get("oversight_bodies", []):
            name = body.get("name", "")
            role = body.get("role", "")
            website = body.get("website", "")
            lines.append(f"  - {name}: {role}")
            if website:
                lines.append(f"    Website: {website}")

        lines.append("")
        lines.append("Relevant Legal Provisions:")

        for flag in flags:
            ref = flag.get("law_reference", {})
            lines.append(f"\n  [{flag.get('id')}] {flag.get('label')}")
            lines.append(f"  Severity: {flag.get('severity', 'unknown')}")
            lines.append(f"  Description: {flag.get('description', '')}")
            act = ref.get("act") or ref.get("reg", "")
            section = ref.get("section") or ref.get("article", "")
            if act:
                lines.append(f"  Source: {act}, {section}" if section else f"  Source: {act}")
            if ref.get("text"):
                lines.append(f"  Text: {ref.get('text')}")
            if flag.get("penalty"):
                lines.append(f"  Penalty: {flag.get('penalty')}")
            action = flag.get("action", {})
            if action.get("what"):
                lines.append(f"  Recommended action: {action.get('what')}")
                if action.get("deadline"):
                    lines.append(f"  Deadline: {action.get('deadline')}")
                if action.get("template"):
                    lines.append(f"  Template: {action.get('template')}")

        return "\n".join(lines)

    def get_disclaimer(self, jurisdiction: JurisdictionCode) -> str:
        """Get the legal disclaimer for a jurisdiction."""
        try:
            meta = self.get_meta(jurisdiction)
            return meta.get("disclaimer", "Consult a qualified local attorney for legal advice.")
        except (FileNotFoundError, KeyError):
            return (
                "This AI-powered legal guidance is for informational purposes only. "
                "It does not constitute legal advice. Consult a qualified attorney "
                "for advice specific to your situation."
            )

    def detect_jurisdiction_from_text(self, text: str) -> JurisdictionCode:
        """Heuristic detection of jurisdiction from tender text."""
        text_lower = text.lower()

        # Nepal indicators
        nepal_signals = [
            "nepal", "kathmandu", "ppmo", "nrs.", "npr", "nrs", "singhadurbar",
            "public procurement monitoring office", "ciaa",
            "ward no.", "gaupalika", "nagar palika", "nepali",
        ]
        nepal_score = sum(1 for s in nepal_signals if s in text_lower)

        if nepal_score >= 2:
            return JurisdictionCode.NEPAL

        return JurisdictionCode.UNKNOWN
