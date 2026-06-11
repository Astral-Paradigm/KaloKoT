"""ChromaDB-backed legal text store with hierarchical parent-child retrieval.

Stores *child chunks* (individual clauses) as vector embeddings
for semantic matching. On retrieval, resolves the *parent article*
(full uninterrupted legal text) for LLM context.

This implements the Hierarchical/Parent-Child chunking strategy:
  ChromaDB matches small chunks → system resolves parent articles
  → full parent text passed to LLM (Gemini context cache).

Also supports "Context Caching" mode: pre-load the full constitution
into the LLM's context window and use ChromaDB only for supplementary
documents (gazettes, uploaded case PDFs).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, TypedDict

import chromadb
from chromadb.config import Settings
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from .chunking import (
    Chunk,
    ParentChunk,
    chunk_constitution,
    get_all_parent_texts,
    resolve_parents,
)


class SearchResult(TypedDict, total=False):
    """A single search result with parent context."""
    child_id: str
    child_text: str
    score: float
    parent_id: str
    parent_title: str
    part_number: int
    part_title: str
    path: List[str]


class ChromaLegalStore:
    """ChromaDB-backed legal text store with parent-child retrieval.

    Usage:
        store = ChromaLegalStore()
        store.index_constitution(yaml_data)
        results = store.search("right to information")
        context = store.get_search_context(results)  # full parent articles
    """

    def __init__(
        self,
        persist_dir: Optional[str] = None,
        collection_name: str = "justice_constitution",
    ):
        if persist_dir is None:
            persist_dir = str(
                Path.home() / ".justice_system" / "chroma_db"
            )
        os.makedirs(persist_dir, exist_ok=True)

        self._client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection_name = collection_name

        # Drop and recreate to ensure clean state
        try:
            existing = self._client.get_collection(collection_name)
            if existing:
                self._client.delete_collection(collection_name)
        except Exception:
            pass  # doesn't exist yet

        self._collection = self._client.create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
            embedding_function=SentenceTransformerEmbeddingFunction(
                model_name="all-MiniLM-L6-v2"
            ),
        )

        # In-memory cache of parent chunks for fast resolution
        self._parents: Dict[str, ParentChunk] = {}
        self._children: Dict[str, Chunk] = {}

        # Context cache mode: when True, the full constitution text
        # is available via get_full_context() for Gemini pre-loading
        self._full_context: str = ""
        self._context_caching_enabled: bool = False

    # ── Indexing ──────────────────────────────────────────────────

    def index_constitution(self, yaml_data: dict) -> int:
        """Index a constitution YAML into ChromaDB.

        Args:
            yaml_data: Parsed constitution YAML with 'parts' list.

        Returns:
            Number of child chunks indexed.
        """
        result = chunk_constitution(yaml_data)
        children: List[Chunk] = result["children"]
        parents: List[ParentChunk] = result["parents"]

        # Cache in memory
        self._children = {c["chunk_id"]: c for c in children}
        self._parents = {p["parent_id"]: p for p in parents}

        # Build full context for Gemini caching
        self._full_context = get_all_parent_texts(parents)

        if not children:
            return 0

        # Prepare ChromaDB batch insert
        ids: List[str] = []
        documents: List[str] = []
        metadatas: List[dict] = []

        for child in children:
            ids.append(child["chunk_id"])
            documents.append(child["text"])

            meta = {
                "parent_id": child.get("parent_id", ""),
                "level": child.get("level", ""),
                "depth": str(child.get("depth", 0)),
                "part_number": str(child.get("part_number", "")),
                "part_title": child.get("part_title", ""),
                "article_number": str(child.get("article_number", "")),
                "article_title": child.get("article_title", ""),
                "title": child.get("title", ""),
                "path": json.dumps(child.get("path", [])),
            }
            metadatas.append(meta)

        self._collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )

        return len(children)

    def index_supplementary(
        self, documents: List[dict], prefix: str = "supp"
    ) -> int:
        """Index supplementary documents (gazettes, uploaded PDFs).

        Each document dict must have:
            - id: str (unique)
            - text: str (the document content)
            - metadata: dict (optional)

        These are NOT linked to parent articles — they stand alone
        and are returned directly.
        """
        ids: List[str] = []
        texts: List[str] = []
        metadatas: List[dict] = []

        for i, doc in enumerate(documents):
            doc_id = doc.get("id", f"{prefix}-{i}")
            ids.append(doc_id)
            texts.append(doc.get("text", ""))
            meta = {
                "type": "supplementary",
                "source": doc.get("source", "unknown"),
                **doc.get("metadata", {}),
            }
            metadatas.append(meta)

        if ids:
            self._collection.add(ids=ids, documents=texts, metadatas=metadatas)

        return len(ids)

    # ── Search ─────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        top_k: int = 5,
        include_supplementary: bool = True,
    ) -> List[SearchResult]:
        """Semantic search across indexed legal text.

        Returns child chunks matched by vector similarity.
        Use get_search_context() to resolve full parent articles.

        Args:
            query: Natural language query.
            top_k: Max child chunks to return.
            include_supplementary: Include supplementary docs in results.

        Returns:
            List of SearchResult dicts.
        """
        if self._collection.count() == 0:
            return []

        results = self._collection.query(
            query_texts=[query],
            n_results=top_k,
        )

        output: List[SearchResult] = []

        ids_list = results.get("ids", [[]])[0]
        distances = results.get("distances", [[]])[0]
        metadatas_list = results.get("metadatas", [[]])[0]

        for i, child_id in enumerate(ids_list):
            metadata = metadatas_list[i] if i < len(metadatas_list) else {}
            distance = distances[i] if i < len(distances) else 0.0
            score = 1.0 - distance  # cosine distance -> similarity

            # Resolve parent info
            child = self._children.get(child_id, {})
            parent_id = child.get("parent_id", metadata.get("parent_id", ""))

            result: SearchResult = {
                "child_id": child_id,
                "child_text": child.get("text", ""),
                "score": round(score, 4),
                "parent_id": parent_id,
                "parent_title": metadata.get("title", ""),
                "part_number": int(metadata.get("part_number", "0")),
                "part_title": metadata.get("part_title", ""),
                "path": json.loads(metadata.get("path", "[]")),
            }
            output.append(result)

        return output

    def get_search_context(
        self, results: List[SearchResult]
    ) -> str:
        """Resolve matched child chunks to full parent articles.

        Implements the Parent-Child Retrieval strategy:
        ChromaDB matched small chunks → we return the full parent
        articles for LLM context.

        Args:
            results: Output from search().

        Returns:
            Concatenated full text of all unique parent articles.
        """
        matched_child_ids = [r["child_id"] for r in results]
        # We need the full children list and parents list
        children_list = list(self._children.values())
        parents_list = list(self._parents.values())

        resolved = resolve_parents(matched_child_ids, children_list, parents_list)
        return get_all_parent_texts(resolved)

    def get_context_cache_text(self) -> str:
        """Return full constitution text for Gemini context caching.

        When context_caching_enabled=True, the LLM is initialized
        with this text pre-loaded. ChromaDB is then used only for
        supplementary documents.
        """
        return self._full_context

    def enable_context_caching(self, enabled: bool = True) -> None:
        """Enable or disable context caching mode."""
        self._context_caching_enabled = enabled

    @property
    def is_context_caching(self) -> bool:
        return self._context_caching_enabled

    def count(self) -> int:
        """Total chunks in the store."""
        return self._collection.count()

    def clear(self) -> None:
        """Clear all entries from the collection."""
        try:
            self._client.delete_collection(self._collection_name)
        except ValueError:
            pass
        self._collection = self._client.create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
            embedding_function=SentenceTransformerEmbeddingFunction(
                model_name="all-MiniLM-L6-v2"
            ),
        )
        self._parents.clear()
        self._children.clear()
