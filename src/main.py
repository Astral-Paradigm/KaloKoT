"""OpenTender + Counsel — Main entry point.

Usage:
    python src/main.py                    # Launch Gradio UI
    python src/main.py --file tender.pdf  # CLI analysis mode
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.analyzer import TenderExtractor, TenderParser, RiskScorer, ReportGenerator
from src.lawyer import VirtualLawyer, EvidenceChecklist
from src.shared.llm import LLMClient
from src.shared.jurisdiction import JurisdictionLoader
from src.shared.chunker import DocumentChunker, DocumentChunk


def get_llm(provider: str | None = None,
            phi_model: str | None = None) -> LLMClient | None:
    """Initialize LLM client from provider flag or available API keys."""
    if provider == "phi":
        return LLMClient(provider="phi", model=phi_model)
    if os.environ.get("GEMINI_API_KEY"):
        return LLMClient(provider="gemini", model="gemini-2.5-flash")
    elif os.environ.get("OPENROUTER_API_KEY"):
        return LLMClient(provider="openrouter", model="anthropic/claude-sonnet-4")
    elif os.environ.get("ANTHROPIC_API_KEY"):
        return LLMClient(provider="anthropic", model="claude-sonnet-4-20250514")
    return None


def run_cli(file_path: str, no_llm: bool = False,
            provider: str | None = None, phi_model: str | None = None):
    """Run analysis in CLI mode."""
    print("🛡️  OpenTender + Counsel — Procurement Corruption Analyzer\n")

    # Initialize
    llm = None if no_llm else get_llm(provider, phi_model)
    if not llm and not no_llm:
        print("⚠️  No API keys found. Running in rule-based mode (no LLM).")
        print("   Set GEMINI_API_KEY, OPENROUTER_API_KEY, or ANTHROPIC_API_KEY in .env\n")

    extractor = TenderExtractor()
    parser = TenderParser(llm) if llm else TenderParser.__new__(TenderParser)
    scorer = RiskScorer()
    reporter = ReportGenerator()
    loader = JurisdictionLoader()
    chunker = DocumentChunker()

    # Extract
    print(f"📄 Extracting: {file_path}")
    raw_text = extractor.from_file(file_path)
    print(f"   {len(raw_text)} characters extracted\n")

    # Parse
    if llm:
        print("🧠 Parsing with LLM...")
        tender = parser.parse(raw_text)
    else:
        print("⚠️  LLM required for parsing. Using raw text fallback.")
        from src.shared.models import TenderDocument
        tender = TenderDocument(
            title=Path(file_path).stem,
            raw_text=raw_text,
        )

    # Score
    print("🔍 Scoring corruption risk...")
    report = scorer.score(tender)

    # Detect jurisdiction
    jurisdiction = loader.detect_jurisdiction_from_text(raw_text)
    if jurisdiction.value != "unknown":
        meta = loader.get_meta(jurisdiction)
        print(f"🌍 Detected jurisdiction: {meta.get('country', jurisdiction.value)}")
    else:
        print("🌍 Jurisdiction not detected from document text.")

    # Generate report
    print("\n" + reporter.generate_heatmap(report))
    print(reporter.generate_text(report))

    # Evidence checklist
    print("\n📋 Generate evidence preservation checklist? (y/N): ", end="")
    try:
        ans = input().strip().lower()
    except (EOFError, KeyboardInterrupt):
        ans = ""
    if ans in ("y", "yes"):
        checklist = EvidenceChecklist(loader)
        print("\n" + checklist.generate(report, jurisdiction))

    # Counsel mode if user asks questions
    print("\n📋 Type a question for the Virtual Lawyer, or press Enter to skip.")
    print("   Examples: 'Is it illegal?', 'How do I report this?', 'Draft a complaint'\n")
    while True:
        try:
            question = input("❓ > ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not question:
            break

        if llm:
            lawyer = VirtualLawyer(loader, llm)
            from src.shared.models import CounselRequest

            # Build RAG context from chunked document
            chunks = chunker.chunk_text(tender.raw_text[:15000], source=tender.title)
            rag_context = "\n\n---\n\n".join(
                f"[chunk {c.chunk_id}] {c.text[:600]}"
                for c in chunks[:8]
            )
            full_context = (
                f"{tender.title}\n{report.summary}\n\n"
                f"RELEVANT DOCUMENT EXCERPTS:\n{rag_context}"
            )

            response = lawyer.counsel(CounselRequest(
                tender_context=full_context,
                question=question,
                jurisdiction=jurisdiction,
                risk_report=report,
            ))
            print(f"\n{response.answer}\n")
            if response.citations:
                print("Citations:")
                for c in response.citations:
                    print(f"  📜 {c.source}")
            if response.suggested_actions:
                print("\nSuggested actions:")
                for a in response.suggested_actions:
                    print(f"  • {a}")
            print()
        else:
            print("LLM required for counsel mode. Set API key and re-run.\n")


def run_ui(provider: str | None = None, phi_model: str | None = None):
    """Launch the Gradio UI."""
    try:
        import gradio as gr
    except ImportError:
        print("Gradio not installed. Run: pip install gradio")
        sys.exit(1)

    llm = get_llm(provider, phi_model)
    loader = JurisdictionLoader()
    extractor = TenderExtractor()
    parser = TenderParser(llm) if llm else None
    scorer = RiskScorer()
    reporter = ReportGenerator()
    lawyer = VirtualLawyer(loader, llm) if llm else VirtualLawyer(loader)
    chunker = DocumentChunker()

    # UI state
    tender_cache = {}

    def analyze_tender(file, url):
        """Analyze uploaded file or URL."""
        try:
            if file is not None:
                text = extractor.from_file(file.name)
            elif url:
                text = extractor.from_url(url)
            else:
                return "Please upload a file or enter a URL.", ""

            # Parse with LLM or fallback
            if parser:
                tender = parser.parse(text)
            else:
                from src.shared.models import TenderDocument
                tender = TenderDocument(title="Uploaded Tender", raw_text=text)

            # Score
            report = scorer.score(tender)
            tender_cache["report"] = report

            # Detect jurisdiction
            jurisdiction = loader.detect_jurisdiction_from_text(text)
            tender_cache["jurisdiction"] = jurisdiction
            tender_cache["tender_text"] = text[:3000]

            text_report = reporter.generate_text(report)
            html_report = reporter.generate_html(report)

            return text_report, html_report
        except Exception as e:
            return f"Error: {e}", ""

    def counsel_question(question):
        """Answer a legal question."""
        if not question.strip():
            return "Ask a question about the tender's legal implications."
        if "report" not in tender_cache:
            return "Please analyze a tender first."

        report = tender_cache["report"]
        jurisdiction = tender_cache["jurisdiction"]

        # Build RAG context from chunked document
        raw = tender_cache.get("tender_text", "")
        chunks = chunker.chunk_text(raw, source="uploaded_tender")
        rag_context = "\n\n---\n\n".join(
            f"[chunk {c.chunk_id}] {c.text[:600]}"
            for c in chunks[:8]
        )
        full_context = (
            f"{report.tender.title}\n{report.summary}\n\n"
            f"RELEVANT DOCUMENT EXCERPTS:\n{rag_context}"
        )

        from src.shared.models import CounselRequest
        request = CounselRequest(
            tender_context=full_context,
            question=question,
            jurisdiction=jurisdiction,
            risk_report=report,
        )

        response = lawyer.counsel(request)

        result = response.answer
        if response.citations:
            result += "\n\n📚 Citations:\n" + "\n".join(
                f"• {c.source}: {c.description[:100]}" for c in response.citations
            )
        if response.suggested_actions:
            result += "\n\n📋 Suggested Actions:\n" + "\n".join(
                f"• {a}" for a in response.suggested_actions
            )
        result += f"\n\n{response.disclaimer}"
        return result

    # Build UI
    with gr.Blocks(title="OpenTender + Counsel", theme=gr.themes.Soft()) as ui:
        gr.Markdown("# 🛡️ OpenTender + Counsel")
        gr.Markdown("Upload a government tender document — get a corruption risk report *and* chat with a Virtual Lawyer about what to do.")

        with gr.Tab("📄 Analyze Tender"):
            with gr.Row():
                file_input = gr.File(label="Upload Tender PDF", file_types=[".pdf", ".txt", ".html"])
                url_input = gr.Textbox(label="Or Tender URL", placeholder="https://example.com/tender.pdf")
            analyze_btn = gr.Button("🔍 Analyze", variant="primary")
            with gr.Row():
                text_output = gr.Textbox(label="Analysis Report", lines=20, max_lines=30)
                html_output = gr.HTML(label="HTML Report")

            analyze_btn.click(
                fn=analyze_tender,
                inputs=[file_input, url_input],
                outputs=[text_output, html_output],
            )

        with gr.Tab("⚖️ Virtual Lawyer"):
            gr.Markdown("Ask the Virtual Lawyer about legal next steps.")
            question_input = gr.Textbox(
                label="Your Question",
                placeholder="e.g., Is it illegal to have only 3 days for bids? How do I report this? Draft a complaint to KPK.",
                lines=3,
            )
            ask_btn = gr.Button("💬 Ask", variant="primary")
            answer_output = gr.Markdown(label="Response")

            ask_btn.click(
                fn=counsel_question,
                inputs=[question_input],
                outputs=[answer_output],
            )

        gr.Markdown("---")
        gr.Markdown(
            "⚠️ **Disclaimer:** This is an AI-assisted tool for informational purposes. "
            "It does not constitute legal advice. Consult a qualified attorney for legal action."
        )

    ui.launch(server_name="127.0.0.1", server_port=7860)


def main():
    parser = argparse.ArgumentParser(description="OpenTender + Counsel")
    parser.add_argument("--file", "-f", help="Path to tender PDF/txt file for CLI analysis")
    parser.add_argument("--url", "-u", help="URL to tender document for CLI analysis")
    parser.add_argument("--no-llm", action="store_true", help="Skip LLM calls (rule-based only)")
    parser.add_argument("--ui", action="store_true", default=True, help="Launch Gradio UI (default)")
    parser.add_argument("--provider", "-p", default=None,
                        choices=["phi", "gemini", "anthropic", "openrouter"],
                        help="LLM provider (default: auto-detect from env)")
    parser.add_argument("--phi-model", default=None,
                        help="Phi model name (default: microsoft/Phi-3-mini-4k-instruct)")

    args = parser.parse_args()

    if args.file:
        run_cli(args.file, no_llm=args.no_llm, provider=args.provider,
                phi_model=args.phi_model)
    elif args.url:
        print("URL extraction requires Gradio UI for interactive use. Launching UI...")
        run_ui(provider=args.provider, phi_model=args.phi_model)
    else:
        run_ui(provider=args.provider, phi_model=args.phi_model)


if __name__ == "__main__":
    main()
