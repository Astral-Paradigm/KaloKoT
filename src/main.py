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

# Load .env from project root
try:
    from dotenv import load_dotenv
    dotenv_path = Path(__file__).resolve().parent.parent / ".env"
    if dotenv_path.exists():
        load_dotenv(dotenv_path)
except ImportError:
    pass

# Ensure project root is in sys.path so imports work consistently
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml

from src.analyzer import TenderExtractor, TenderParser, RiskScorer, ReportGenerator
from src.lawyer import VirtualLawyer, EvidenceChecklist
from src.shared.llm import LLMClient
from src.shared.jurisdiction import JurisdictionLoader
from src.shared.chunker import DocumentChunker, DocumentChunk
from src.shared.chunking import chunk_constitution
from src.shared.chroma_store import ChromaLegalStore


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
        import gradio.themes as grt
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

    # Initialize ChromaDB with Constitution of Nepal
    chroma_store = ChromaLegalStore(
        persist_dir=str(Path.home() / ".justice_chromadb")
    )
    constitution_path = Path(__file__).resolve().parent.parent / "docs" / "legal" / "np_constitution.yaml"
    if constitution_path.exists():
        try:
            with open(constitution_path) as f:
                constitution_data = yaml.safe_load(f)
            if constitution_data and "parts" in constitution_data:
                count = chroma_store.index_constitution(constitution_data)
                print(f"   ⚖️ Constitution indexed: {count} clauses")
        except Exception as e:
            print(f"   ⚠️ Constitution indexing skipped: {e}")
    else:
        print("   ℹ️ Constitution file not found at {constitution_path}")

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
        """Answer a legal question — grounded in constitution law via ChromaDB."""
        if not question.strip():
            return "Ask a question about the tender's legal implications."

        # Search the Constitution via ChromaDB
        constitution_context = ""
        try:
            if chroma_store.count() > 0:
                search_results = chroma_store.search(question, top_k=4)
                if search_results:
                    constitution_context = chroma_store.get_search_context(search_results)
        except Exception:
            pass

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

        # Pass constitution context to the lawyer
        response = lawyer.counsel(request, constitution_context=constitution_context)

        # Return just the clean answer — no formal sections for non-tech users
        answer = response.answer.strip()

        # Only add a brief disclaimer in a footer
        if response.disclaimer:
            answer += f"\n\n—\n{response.disclaimer[:200]}"

        return answer

    # Build UI
    mascot_html_path = Path(__file__).resolve().parent / "ui" / "mascot.html"
    mascot_html = ""
    if mascot_html_path.exists():
        with open(mascot_html_path) as f:
            mascot_html = f.read()

    with gr.Blocks(title="OpenTender + Counsel") as ui:
        gr.Markdown("# 🛡️ OpenTender + Counsel")
        gr.Markdown("Upload a government tender document — get a corruption risk report *and* chat with a Digital Lawyer about legal next steps.")

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

        with gr.Tab("⚖️ Digital Lawyer"):
            with gr.Row(equal_height=True):
                with gr.Column(scale=1, min_width=320):
                    # Mascot container
                    mascot_component = gr.HTML(value=mascot_html, label="Digital Lawyer")
                    mascot_status = gr.Markdown("**Status:** Ready")
                with gr.Column(scale=2):
                    gr.Markdown("Ask the Digital Lawyer about legal next steps for your tender.")
                    chatbot = gr.Chatbot(
                        label="Conversation",
                        height=420,
                    )
                    with gr.Row():
                        question_input = gr.Textbox(
                            label="Your Question",
                            placeholder="Type your question here and press Enter or click Ask...",
                            lines=2,
                            scale=4,
                        )
                        ask_btn = gr.Button("💬 Ask", variant="primary", size="lg", scale=1)
                    chat_history = gr.State([])

                    def update_mascot_status(question):
                        if not question.strip():
                            return "**Status:** Ready", None
                        return "**Status:** ⚖️ Thinking… analyzing legal framework", None

                    def respond_and_record(question, history):
                        if not question.strip():
                            return history, history, "**Status:** Ready"

                        answer = counsel_question(question)

                        if not answer or len(answer) < 10 or "error" in answer.lower():
                            status = "**Status:** Ready to help"
                        else:
                            status = "**Status:** ⚖️ Speaking — providing legal analysis"

                        history.append((question, answer))
                        return history, history, status

                    ask_btn.click(
                        fn=update_mascot_status,
                        inputs=[question_input],
                        outputs=[mascot_status, gr.State()],
                    ).then(
                        fn=respond_and_record,
                        inputs=[question_input, chat_history],
                        outputs=[chat_history, chatbot, mascot_status],
                    ).then(
                        fn=lambda: "",
                        inputs=None,
                        outputs=[question_input],
                    )

                    # Also submit on Enter
                    question_input.submit(
                        fn=update_mascot_status,
                        inputs=[question_input],
                        outputs=[mascot_status, gr.State()],
                    ).then(
                        fn=respond_and_record,
                        inputs=[question_input, chat_history],
                        outputs=[chat_history, chatbot, mascot_status],
                    ).then(
                        fn=lambda: "",
                        inputs=None,
                        outputs=[question_input],
                    )

        with gr.Tab("📋 Evidence Checklist"):
            with gr.Row():
                checklist_report_id = gr.Textbox(label="Report ID (from Analyze tab)", placeholder="Paste report ID here")
                checklist_jurisdiction = gr.Dropdown(
                    label="Jurisdiction",
                    choices=["np", "ke", "za", "ng", "bd"],
                    value="np",
                )
            checklist_btn = gr.Button("📋 Generate Checklist", variant="primary")
            checklist_output = gr.Markdown(label="Evidence Checklist")
            # Checklist endpoint - simplified version using mock
            # In production this calls the API
            gr.Markdown("_Upload a tender and get a report ID above, then generate an evidence checklist here._")

        with gr.Tab("📄 Export Complaint"):
            with gr.Row():
                draft_title = gr.Textbox(label="Complaint Title", placeholder="e.g., Complaint regarding tender X")
                draft_jurisdiction = gr.Dropdown(
                    label="Jurisdiction", choices=["np", "ke", "za", "ng", "bd"], value="np"
                )
            draft_body = gr.Textbox(label="Complaint Body", lines=8, placeholder="Paste the complaint text generated by the Digital Lawyer...")
            draft_template = gr.Dropdown(
                label="Template",
                choices=["", "standard", "detailed", "urgent"],
                value="",
            )
            export_btn = gr.Button("💾 Export as .txt", variant="primary")
            export_output = gr.File(label="Download")

        gr.Markdown("---")
        gr.Markdown(
            "⚠️ **Disclaimer:** This is an AI-assisted tool for informational purposes. "
            "It does not constitute legal advice. Consult a qualified attorney for legal action."
        )

    ui.launch(server_name="127.0.0.1", server_port=7860, theme=grt.Soft())


def main():
    parser = argparse.ArgumentParser(description="OpenTender + Counsel")
    parser.add_argument("--file", "-f", help="Path to tender PDF/txt file for CLI analysis")
    parser.add_argument("--url", "-u", help="URL to tender document for CLI analysis")
    parser.add_argument("--no-llm", action="store_true", help="Skip LLM calls (rule-based only)")
    parser.add_argument("--ui", action="store_true", default=False, help="Launch Gradio UI")
    parser.add_argument("--api", action="store_true", default=False, help="Launch FastAPI backend")
    parser.add_argument("--provider", "-p", default=None,
                        choices=["phi", "gemini", "anthropic", "openrouter", "openai"],
                        help="LLM provider (default: auto-detect from env)")
    parser.add_argument("--phi-model", default=None,
                        help="Phi model name (default: microsoft/Phi-3-mini-4k-instruct)")

    args = parser.parse_args()

    if args.file:
        run_cli(args.file, no_llm=args.no_llm, provider=args.provider,
                phi_model=args.phi_model)
    elif args.api:
        from src.api import main as api_main
        api_main()
    elif args.ui:
        run_ui(provider=args.provider, phi_model=args.phi_model)
    else:
        # Default: launch Gradio UI
        run_ui(provider=args.provider, phi_model=args.phi_model)


if __name__ == "__main__":
    main()
