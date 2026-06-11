"""Document chunker for RAG — splits tender PDF text into semantically meaningful chunks."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class DocumentChunk:
    text: str
    chunk_id: str = ""
    source: str = ""
    page_number: Optional[int] = None
    section: Optional[str] = None
    heading: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.chunk_id:
            self.chunk_id = str(uuid.uuid4())[:8]


class DocumentChunker:
    """Split tender documents into overlapping chunks for RAG retrieval.

    Supports three strategies:
      - ``by_pages``    — split on ``--- Page N ---`` markers
      - ``by_sections`` — split on parsed ``TenderSection`` boundaries
      - ``recursive``   — generic recursive character splitting
    """

    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 64):
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self._separators = ["\n\n", "\n", ". ", " ", ""]

    # ------------------------------------------------------------------
    # Public chunking strategies
    # ------------------------------------------------------------------

    def chunk_by_pages(self, text: str, source: str = "") -> List[DocumentChunk]:
        """Split on page markers (``--- Page N ---``)."""
        page_pattern = re.compile(r"--- Page (\d+) ---")
        parts = page_pattern.split(text)

        chunks: List[DocumentChunk] = []
        for i in range(1, len(parts) - 1, 2):
            page_num = int(parts[i])
            page_text = parts[i + 1].strip()
            if not page_text:
                continue
            page_sub_chunks = self._recursive_split(page_text)
            for sc in page_sub_chunks:
                chunks.append(DocumentChunk(
                    text=sc,
                    source=source,
                    page_number=page_num,
                    section="page",
                ))
        return chunks

    def chunk_by_sections(self, sections_data: list, source: str = "") -> List[DocumentChunk]:
        """Chunk by parsed tender sections — one chunk per section."""
        chunks: List[DocumentChunk] = []
        for sd in sections_data:
            text = sd.content.strip()
            if not text:
                continue
            sub_chunks = self._recursive_split(text)
            for sc in sub_chunks:
                chunks.append(DocumentChunk(
                    text=sc,
                    source=source,
                    section=sd.section.value if hasattr(sd.section, "value") else str(sd.section),
                    heading=sd.heading,
                ))
        return chunks

    def chunk_text(self, text: str, source: str = "",
                   metadata: Optional[dict] = None) -> List[DocumentChunk]:
        """Generic recursive chunking without page/section structure."""
        raw_chunks = self._recursive_split(text)
        return [
            DocumentChunk(text=t, source=source, metadata=metadata or {})
            for t in raw_chunks
        ]

    def chunk_document(self, text: str, source: str = "") -> List[DocumentChunk]:
        """Auto-detect best strategy: try pages, then sections, fallback recursive."""
        if re.search(r"--- Page \d+ ---", text):
            return self.chunk_by_pages(text, source)
        return self.chunk_text(text, source)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _recursive_split(self, text: str) -> List[str]:
        """Recursively split text trying separators from longest to shortest."""
        if not text:
            return []
        if self._measure(text) <= self.chunk_size:
            return [text]

        for sep in self._separators:
            if sep == "":
                break
            parts = text.split(sep)
            if len(parts) <= 1:
                continue
            break
        else:
            parts = list(text)

        chunks: List[str] = []
        buffer = ""
        for part in parts:
            candidate = buffer + (sep if buffer else "") + part
            if self._measure(candidate) <= self.chunk_size:
                buffer = candidate
            else:
                if buffer:
                    chunks.append(buffer.strip())
                overlap_text = self._take_overlap(part)
                buffer = overlap_text + part if overlap_text else part

        if buffer:
            chunks.append(buffer.strip())

        return chunks

    def _measure(self, text: str) -> int:
        """Approximate token count (chars ÷ 4 for English text)."""
        return max(1, len(text) // 4) if text else 0

    def _take_overlap(self, text: str) -> str:
        """Take trailing chars from text to serve as overlap window."""
        overlap_chars = self.chunk_overlap * 4
        return text[-overlap_chars:] if len(text) > overlap_chars else ""


class ChunkEmbedder:
    """Thin wrapper that embeds chunks using the Phi model's hidden states.

    For offline RAG you will need a dedicated embedding model
    (e.g. ``sentence-transformers/all-MiniLM-L6-v2``).  This stub
    shows where to plug it in.
    """

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None

    def embed(self, chunks: List[DocumentChunk]) -> List[tuple[DocumentChunk, list[float]]]:
        """Return list of (chunk, embedding_vector) pairs."""
        if self._model is None:
            self._load_model()
        texts = [c.text for c in chunks]
        vectors = self._model.encode(texts, show_progress_bar=False)
        return list(zip(chunks, vectors.tolist()))

    def _load_model(self):
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
        except ImportError:
            raise ImportError(
                "sentence-transformers not installed. Run: pip install sentence-transformers"
            )
