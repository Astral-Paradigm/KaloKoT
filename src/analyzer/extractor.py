"""PDF/text extraction from tender documents."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Optional

import requests


class TenderExtractor:
    """Extract text from tender PDFs or URLs."""

    def __init__(self, use_marker: bool = False):
        self.use_marker = use_marker

    def from_file(self, path: str) -> str:
        """Extract text from a local PDF file."""
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
        else:
            raise ValueError(f"Unsupported file type: {ext}")

    def from_url(self, url: str) -> str:
        """Download a PDF or HTML page and extract text."""
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()

        content_type = resp.headers.get("content-type", "")
        if "pdf" in content_type:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(resp.content)
                tmp_path = tmp.name
            try:
                return self._extract_pdf(tmp_path)
            finally:
                Path(tmp_path).unlink(missing_ok=True)
        else:
            return resp.text

    def _extract_pdf(self, path: str) -> str:
        """Extract text from a PDF using PyMuPDF (fitz)."""
        try:
            import fitz
        except ImportError:
            raise ImportError("PyMuPDF not installed. Run: pip install PyMuPDF")

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
        """Extract text from an HTML file."""
        try:
            from html.parser import HTMLParser
        except ImportError:
            raise ImportError("HTML parser not available.")

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        class TextExtractor(HTMLParser):
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
                if tag in ("p", "br", "h1", "h2", "h3", "h4", "h5", "h6", "li"):
                    self.result.append("\n")
            def handle_data(self, data):
                if not self.skip:
                    self.result.append(data)

        parser = TextExtractor()
        parser.feed(content)
        return "".join(parser.result)

    def from_any(self, source: str) -> str:
        """Auto-detect if source is a URL or a file path and extract."""
        if source.startswith(("http://", "https://")):
            return self.from_url(source)
        else:
            return self.from_file(source)
