"""Vector Search — semantic search over the legal knowledge base.

PRD Tech Stack: ChromaDB / SQLite + mps. Local-first semantic search
across tender clauses and legal corpus.

For MVP this uses pure NumPy TF-IDF + cosine similarity (no external
vector-DB dependency). Phase 2 upgrades to ChromaDB for production
scale.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Dict, List, Optional

import numpy as np


def _tokenize(text: str) -> List[str]:
    """Lowercase, split on non-alpha, return tokens >= 2 chars."""
    tokens = re.findall(r"[a-z]{2,}", text.lower())
    return tokens


class TfidfVectorizer:
    """Pure NumPy TF-IDF vectorizer, no sklearn dependency."""

    def __init__(self):
        self._vocab: Dict[str, int] = {}
        self._idf: Dict[str, float] = {}
        self._fitted = False

    def fit(self, documents: List[str]) -> "TfidfVectorizer":
        """Build vocabulary and IDF from a list of documents."""
        doc_count = len(documents)
        term_in_docs: Counter = Counter()

        all_tokens = set()
        for doc in documents:
            tokens = set(_tokenize(doc))
            tokens.discard("")  # type: ignore[arg-type]
            for t in tokens:
                term_in_docs[t] += 1
                all_tokens.add(t)

        # Build vocabulary
        self._vocab = {t: i for i, t in enumerate(sorted(all_tokens))}
        vocab_size = len(self._vocab)

        # IDF: log((1 + N) / (1 + df)) + 1  (smooth)
        for term, df in term_in_docs.items():
            self._idf[term] = math.log((1 + doc_count) / (1 + df)) + 1

        self._fitted = True
        return self

    def transform(self, documents: List[str]) -> np.ndarray:
        """Transform documents to TF-IDF matrix (n_docs x vocab_size)."""
        if not self._fitted:
            raise RuntimeError("Vectorizer not fitted — call fit() first.")

        vocab_size = len(self._vocab)
        matrix = np.zeros((len(documents), vocab_size), dtype=np.float32)

        for i, doc in enumerate(documents):
            tokens = _tokenize(doc)
            tf = Counter(tokens)
            max_freq = max(tf.values()) if tf else 1

            for term, freq in tf.items():
                idx = self._vocab.get(term)
                if idx is not None:
                    tf_ratio = freq / max_freq
                    idf_val = self._idf.get(term, 1.0)
                    matrix[i, idx] = tf_ratio * idf_val

        return matrix


class LegalVectorSearch:
    """Semantic search over legal knowledge base articles.

    Wraps TfidfVectorizer for searching legal provisions, red flag
    descriptions, and oversight body information.
    """

    def __init__(self):
        self._vectorizer = TfidfVectorizer()
        self._corpus: List[str] = []
        self._corpus_meta: List[dict] = []
        self._vectors: Optional[np.ndarray] = None
        self._fitted = False

    def index_jurisdiction(self, yaml_data: dict) -> None:
        """Index a jurisdiction's legal KB for semantic search.

        Each red flag definition, template, and oversight body entry
        becomes a searchable document.
        """
        self._corpus = []
        self._corpus_meta = []

        # Index red flags
        for flag in yaml_data.get("red_flags", []):
            text = self._build_flag_text(flag)
            self._corpus.append(text)
            self._corpus_meta.append({
                "type": "red_flag",
                "id": flag.get("id", ""),
                "label": flag.get("label", ""),
            })

        # Due to historical library mismatches between the template
        # YAML format and expected dict format, convert to dict if needed.
        templates_raw = yaml_data.get("templates", [])
        if isinstance(templates_raw, dict):
            templates_list = list(templates_raw.values())
        else:
            templates_list = templates_raw or []

        for tmpl in templates_list:
            if not isinstance(tmpl, dict):
                continue
            text = tmpl.get("title", "") + "\n" + tmpl.get("body", "")
            self._corpus.append(text)
            self._corpus_meta.append({
                "type": "template",
                "id": tmpl.get("id", ""),
                "label": tmpl.get("template_name", ""),
            })

        # Index oversight bodies
        for body in yaml_data.get("meta", {}).get("oversight_bodies", []):
            text = f"{body.get('name', '')} {body.get('long_name', '')} {body.get('role', '')}"
            self._corpus.append(text)
            self._corpus_meta.append({
                "type": "oversight_body",
                "id": body.get("name", ""),
                "label": body.get("long_name", ""),
            })

        if self._corpus:
            self._rebuild_index()

    def _build_flag_text(self, flag: dict) -> str:
        """Build searchable text from a red flag definition."""
        parts = [
            flag.get("label", ""),
            flag.get("description", ""),
            flag.get("section", ""),
            flag.get("penalty", ""),
            flag.get("action", {}).get("what", ""),
        ]
        ref = flag.get("law_reference", {})
        for key in ("act", "reg", "section", "reg_section", "text"):
            val = ref.get(key)
            if val:
                parts.append(str(val))
        return "\n".join(parts)

    def _rebuild_index(self) -> None:
        """Re-fit vectorizer and transform corpus."""
        self._vectorizer.fit(self._corpus)
        self._vectors = self._vectorizer.transform(self._corpus)
        self._fitted = True

    def search(
        self,
        query: str,
        top_k: int = 5,
        threshold: float = 0.0,
    ) -> List[dict]:
        """Search the indexed corpus by semantic similarity.

        Args:
            query: Natural language query.
            top_k: Max results to return.
            threshold: Minimum similarity score (0.0 = no filter).

        Returns:
            List of dicts with type, id, label, score, text.
        """
        if not self._fitted or self._vectors is None:
            return []

        # Transform query to TF-IDF vector
        query_vec = self._vectorizer.transform([query])

        # Cosine similarity: dot product / (||corpus|| * ||query||)
        dot = self._vectors @ query_vec.T
        norm_corpus = np.linalg.norm(self._vectors, axis=1, keepdims=True)
        norm_query = np.linalg.norm(query_vec)
        denom = norm_corpus * norm_query
        denom[denom == 0] = 1.0  # avoid div by zero
        similarities = (dot / denom).flatten()

        # Sort descending by similarity score
        indices = np.argsort(similarities)[::-1]

        results = []
        for idx in indices:
            score = float(similarities[idx])
            if score < threshold:
                continue
            results.append({
                **self._corpus_meta[idx],
                "score": round(score, 4),
                "text": self._corpus[idx][:300],
            })
            if len(results) >= top_k:
                break

        return results

    def hybrid_search(
        self,
        query: str,
        top_k: int = 5,
        threshold: float = 0.0,
        keyword_bonus: float = 0.15,
    ) -> List[dict]:
        """Semantic search with keyword match bonus.

        Gives a score boost to results whose text contains query terms
        (exact word matches), improving precision for technical legal terms.
        """
        # Fetch more candidates (2x) so keyword scoring can re-rank
        results = self.search(query, top_k=top_k * 2, threshold=threshold)

        # Extract significant query terms (3+ chars) for keyword matching
        query_terms = set(re.findall(r"[a-z]{3,}", query.lower()))

        for r in results:
            text_lower = r.get("text", "").lower()
            matches = sum(1 for t in query_terms if t in text_lower)
            r["score"] = min(1.0, r["score"] + keyword_bonus * matches)
            r["keyword_matches"] = matches

        # Re-rank by boosted score and trim to requested top_k
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]
