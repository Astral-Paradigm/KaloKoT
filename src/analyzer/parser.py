"""Tender document parser — uses LLM to extract structured data from raw text.

The parser sends raw tender text (from PDF/HTML extraction) to an LLM client
along with a strict JSON schema, then maps the response into the domain models
(TenderDocument, TenderSectionData, etc.).
"""

from __future__ import annotations

from ..shared.models import (
    TenderDocument,
    TenderSection,
    TenderSectionData,
)
from ..shared.llm import LLMClient

# ── System prompt for the LLM parser ──────────────────────────────────

PARSER_SYSTEM_PROMPT = """You are a government procurement document parser. Your job is to:
1. Read a raw tender document (PDF text or HTML)
2. Extract structured information
3. Split into sections: details, specification, budget, timeline, evaluation_criteria, terms_and_conditions
4. Return a clean JSON object

Rules:
- Extract exact values where present (do not fabricate)
- If a field is not found, set it to null
- For estimated_value, include both the number and currency
- Section content should be the raw relevant text, not a summary
- Page ranges are optional — omit if unknown

Respond ONLY with a valid JSON object matching the requested schema."""

# ── JSON schema enforced on the LLM output ────────────────────────────

PARSER_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "reference_no": {"type": "string"},
        "procuring_entity": {"type": "string"},
        "estimated_value": {"type": "string"},
        "currency": {"type": "string"},
        "publication_date": {"type": "string"},
        "submission_deadline": {"type": "string"},
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "section": {"type": "string"},
                    "heading": {"type": "string"},
                    "content": {"type": "string"},
                    "page_range": {"type": "string"},
                },
                "required": ["section", "heading", "content"],
            },
        },
    },
    "required": ["title", "sections"],
}


class TenderParser:
    """Parse tender document text into a structured TenderDocument.

    Args:
        llm: An LLMClient instance used to call the underlying model
            with structured output (JSON-mode) support.
    """

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def parse(self, raw_text: str) -> TenderDocument:
        """Parse raw tender text into a structured TenderDocument.

        The raw text is sent to the LLM with the parser system prompt and
        output schema.  The returned JSON is then mapped to domain objects.

        Args:
            raw_text: The full plain-text content of a tender document
                (extracted via TenderExtractor).

        Returns:
            A fully populated TenderDocument with parsed sections.
        """
        # Truncate very long documents to avoid exceeding LLM context windows
        if len(raw_text) > 100000:
            raw_text = (
                raw_text[:100000]
                + "\n\n[TRUNCATED - document exceeds context limit]"
            )

        user_prompt = (
            f"Parse the following government tender document:\n\n"
            f"{raw_text}\n\n"
            f"Extract all fields specified in the schema. Return JSON only."
        )

        result = self.llm.generate_structured(
            system_prompt=PARSER_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            output_schema=PARSER_OUTPUT_SCHEMA,
            temperature=0.1,
        )

        # Convert raw section dicts from the LLM to typed TenderSectionData objects
        sections = []
        for s in result.get("sections", []):
            try:
                section_enum = TenderSection(s.get("section"))
            except ValueError:
                # Skip sections whose name doesn't match any known TenderSection
                continue
            sections.append(
                TenderSectionData(
                    section=section_enum,
                    heading=s.get("heading", ""),
                    content=s.get("content", ""),
                    page_range=s.get("page_range"),
                )
            )

        return TenderDocument(
            title=result.get("title", "Untitled Tender"),
            reference_no=result.get("reference_no"),
            procuring_entity=result.get("procuring_entity"),
            estimated_value=result.get("estimated_value"),
            currency=result.get("currency"),
            publication_date=result.get("publication_date"),
            submission_deadline=result.get("submission_deadline"),
            sections=sections,
            raw_text=raw_text,
        )
