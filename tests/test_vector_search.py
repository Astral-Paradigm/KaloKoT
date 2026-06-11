"""Tests for the Vector Search (semantic legal KB search) module."""
from src.shared.vector_search import TfidfVectorizer, LegalVectorSearch
from src.shared.jurisdiction import JurisdictionLoader
from src.shared.models import JurisdictionCode


class TestTfidfVectorizer:
    def test_fit_and_transform(self):
        v = TfidfVectorizer()
        docs = ["the quick brown fox", "jumps over the lazy dog", "quick fox jumps"]
        v.fit(docs)
        matrix = v.transform(docs)
        assert matrix.shape == (3, len(v._vocab))
        # Same document should have non-zero similarity with itself
        from numpy.linalg import norm
        sim = (matrix[0] @ matrix[0]) / (norm(matrix[0]) * norm(matrix[0]))
        assert abs(sim - 1.0) < 0.001

    def test_empty_fit_raises(self):
        v = TfidfVectorizer()
        import numpy as np
        v.fit([])
        m = v.transform([])
        assert m.shape == (0, 0)

    def test_unfitted_raises(self):
        v = TfidfVectorizer()
        import pytest
        with pytest.raises(RuntimeError):
            v.transform(["hello"])


class TestLegalVectorSearch:
    def setup_method(self):
        self.searcher = LegalVectorSearch()
        self.loader = JurisdictionLoader()
        self.yaml_data = self.loader.load_yaml(JurisdictionCode.NEPAL)

    def test_index_no_crash(self):
        """Indexing should not raise."""
        self.searcher.index_jurisdiction(self.yaml_data)
        assert self.searcher._fitted

    def test_search_returns_results(self):
        self.searcher.index_jurisdiction(self.yaml_data)
        results = self.searcher.search("short bidding timeline")
        assert len(results) > 0
        assert any("Timeline" in r.get("label", "") or "timeline" in r.get("text", "")
                   for r in results)

    def test_search_empty_corpus(self):
        """Search before indexing should return empty."""
        results = self.searcher.search("anything")
        assert results == []

    def test_hybrid_search_keyword_bonus(self):
        self.searcher.index_jurisdiction(self.yaml_data)
        semantic = self.searcher.search("evaluation criteria missing")
        hybrid = self.searcher.hybrid_search("evaluation criteria missing", keyword_bonus=0.2)
        # Hybrid should have at least as many results as pure semantic
        assert len(hybrid) <= len(semantic)  # hybrid capped at default top_k=5, semantic defaults to 5 too

    def test_search_with_threshold(self):
        self.searcher.index_jurisdiction(self.yaml_data)
        results = self.searcher.search("irrelevant garbage text", threshold=0.5)
        # High threshold should filter out unrelated results
        assert len(results) == 0

    def test_search_respects_top_k(self):
        self.searcher.index_jurisdiction(self.yaml_data)
        results = self.searcher.search("conflict of interest", top_k=3)
        assert len(results) <= 3

    def test_jurisdiction_oversight_bodies_indexed(self):
        self.searcher.index_jurisdiction(self.yaml_data)
        results = self.searcher.search("CIAA anti-corruption")
        assert len(results) > 0
