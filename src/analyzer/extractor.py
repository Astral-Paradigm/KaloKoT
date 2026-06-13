"""PDF/text extraction from tender documents.

Handles local files (PDF, TXT, MD, HTML) and URLs (PDF or HTML pages).
Uses PyMuPDF (fitz) for PDF extraction; HTMLParser for HTML; plain read for text.
Also supports image OCR via Gemini vision.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import requests


class TenderExtractor:
    """Extract text from tender PDFs, local files, or URLs."""

    def __init__(self, use_marker: bool = False):
        # Reserved for future use: marker-based PDF extraction pipeline
        self.use_marker = use_marker

    def from_file(self, path: str) -> str:
        """Extract text from a local file (PDF, TXT, MD, HTML, or Image).

        Args:
            path: Absolute or relative path to the file.

        Returns:
            Extracted plain text content.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the file extension is unsupported.
        """
        path = Path(path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        ext = path.suffix.lower()
        if ext == ".pdf":
            return self._extract_pdf(str(path))
        elif ext in (".txt", ".md"):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        elif ext == ".html":
            return self._extract_html(str(path))
        elif ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"):
            return self._extract_image(str(path))
        else:
            raise ValueError(f"Unsupported file type: {ext}")

    def _extract_image(self, path: str) -> str:
        """Extract text from an image using Gemini vision OCR.

        Args:
            path: Filesystem path to the image.

        Returns:
            Extracted plain text content.
        """
        try:
            from ..shared.llm import create_llm_client
        except ImportError:
            raise ImportError("LLM client not available for image OCR")

        llm = create_llm_client()
        if not llm:
            raise ValueError("No LLM configured — set GEMINI_API_KEY for image OCR")

        mime_map = {
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".png": "image/png", ".gif": "image/gif",
            ".webp": "image/webp", ".bmp": "image/bmp",
        }
        ext = Path(path).suffix.lower()
        mime_type = mime_map.get(ext, "image/png")

        with open(path, "rb") as f:
            image_data = f.read()

        return llm.extract_text_from_image(image_data, mime_type=mime_type)

    def from_url(self, url: str) -> str:
        """Download a PDF or HTML page from a URL and extract its text.

        PDFs are saved to a temporary file, extracted, then cleaned up.
        HTML pages return the raw response text directly.

        Args:
            url: HTTP/HTTPS URL pointing to a PDF or HTML document.

        Returns:
            Extracted plain text content.
        """
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()

        content_type = resp.headers.get("content-type", "")
        if "pdf" in content_type:
            # Save PDF to a temp file so we can reuse the PDF extraction logic
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(resp.content)
                tmp_path = tmp.name
            try:
                return self._extract_pdf(tmp_path)
            finally:
                Path(tmp_path).unlink(missing_ok=True)
        else:
            # Treat non-PDF responses as raw HTML/text
            return resp.text

    def _extract_pdf(self, path: str) -> str:
        """Extract text from a PDF using PyMuPDF (fitz).

        Args:
            path: Filesystem path to the PDF.

        Returns:
            Concatenated text with page-break markers.
        """
        try:
            import fitz
        except ImportError:
            raise ImportError(
                "PyMuPDF not installed. Run: pip install PyMuPDF"
            )

        doc = fitz.open(path)
        lines = []
        for i, page in enumerate(doc, start=1):
            text = page.get_text()
            if text.strip():
                lines.append(f"--- Page {i} ---")
                lines.append(text)
        doc.close()
        return "\n".join(lines)

    def _extract_html(self, path: str) -> str:
        """Extract visible text from an HTML file using Python's HTMLParser.

        Strips <script> and <style> blocks. Inserts newlines after
        block-level tags (p, br, headings, li) for readability.

        Args:
            path: Filesystem path to the HTML file.

        Returns:
            Plain text content of the HTML.
        """
        from html.parser import HTMLParser

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        class TextExtractor(HTMLParser):
            """Inline parser that accumulates visible text, skipping script/style."""

            def __init__(self):
                super().__init__()
                self.result = []
                self.skip = False

            def handle_starttag(self, tag, attrs):
                if tag in ("script", "style"):
                    self.skip = True

            def handle_endtag(self, tag):
                if tag in ("script", "style"):
                    self.skip = False
                # Insert newline after block-level tags for readability
                if tag in ("p", "br", "h1", "h2", "h3", "h4", "h5", "h6", "li"):
                    self.result.append("\n")

            def handle_data(self, data):
                if not self.skip:
                    self.result.append(data)

        parser = TextExtractor()
        parser.feed(content)
        return "".join(parser.result)

    def from_any(self, source: str) -> str:
        """Auto-detect whether *source* is a URL or a file path, then extract.

        Args:
            source: Either an HTTP/HTTPS URL or a local filesystem path.

        Returns:
            Extracted plain text content.
        """
        if source.startswith(("http://", "https://")):
            return self.from_url(source)
        else:
            return self.from_file(source)
