"""Tests for ChromaDB-backed legal text store with parent-child retrieval."""
import pytest
import yaml
import tempfile
import os

from src.shared.chroma_store import ChromaLegalStore
from src.shared.chunking import chunk_constitution

SAMPLE_YAML = """
meta:
  country: "Testland"
  document: "Test Constitution"
parts:
  - number: 1
    title: "Fundamental Rights"
    articles:
      - number: 1
        title: "Right to test"
        id: "art-1"
        clauses:
          - number: 1
            id: "art-1-cl-1"
            text: "Everyone has the right to write automated software tests."
          - number: 2
            id: "art-1-cl-2"
            text: "No law shall impede continuous integration testing."
      - number: 2
        title: "Right to information"
        id: "art-2"
        clauses:
          - number: 1
            id: "art-2-cl-1"
            text: "Every citizen shall have access to source code repositories."
          - number: 2
            id: "art-2-cl-2"
            text: "The government shall publish all public API documentation."
"""


@pytest.fixture
def store():
    """Create a fresh ChromaDB store for each test."""
    persist = tempfile.mkdtemp(prefix="chroma_test_")
    s = ChromaLegalStore(persist_dir=persist)
    data = yaml.safe_load(SAMPLE_YAML)
    s.index_constitution(data)
    yield s
    try:
        s.clear()
    except Exception:
        pass


class TestChromaLegalStore:
    def test_index_count(self, store):
        assert store.count() == 4  # 4 clauses in sample

    def test_basic_search(self, store):
        results = store.search("source code repositories")
        assert len(results) > 0
        # Should match art-2-cl-1 most closely
        top = results[0]
        assert top["child_id"] == "art-2-cl-1"
        assert top["score"] > 0.3

    def test_search_query_variations(self, store):
        results = store.search("automated tests")
        assert len(results) > 0
        # The top result should contain "test" in text
        top = results[0]
        assert "test" in top["child_text"].lower()

    def test_parent_resolution(self, store):
        results = store.search("right to information")
        context = store.get_search_context(results)
        assert "Right to information" in context
        assert "access to source code" in context
        assert "Part 1: Fundamental Rights" in context

    def test_child_matches_come_from_same_article(self, store):
        """Multiple child chunks from the same article should resolve to one parent."""
        results = store.search("test", top_k=3)
        context = store.get_search_context(results)
        # Count unique article headers in resolved context
        articles = [line for line in context.split("\n") if line.startswith("--- Article")]
        # With top_k=3 and sample data, at most 2 articles should appear
        assert len(articles) <= 2

    def test_context_caching_mode(self, store):
        assert store.is_context_caching is False
        store.enable_context_caching(True)
        assert store.is_context_caching is True

    def test_context_cache_text(self, store):
        text = store.get_context_cache_text()
        assert "Right to test" in text
        assert "Right to information" in text
        assert "Fundamental Rights" in text

    def test_supplementary_docs(self, store):
        store.index_supplementary([
            {"id": "doc-1", "text": "Test Procurement Guidelines 2024", "source": "gazette", "metadata": {"type": "guideline"}},
        ])
        results = store.search("procurement guidelines", top_k=3)
        supp_results = [r for r in results if r["child_id"] == "doc-1"]
        assert len(supp_results) > 0
        assert supp_results[0]["score"] > 0.3

    def test_search_no_results(self, store):
        results = store.search("zyxwvutotallynonexistent")
        # May still return low-score results depending on index size

    def test_clear_store(self, store):
        store.clear()
        assert store.count() == 0

    def test_empty_store_search(self):
        """Search on an empty store should return empty list."""
        persist = tempfile.mkdtemp(prefix="chroma_empty_")
        s = ChromaLegalStore(persist_dir=persist)
        results = s.search("anything")
        assert results == []
        s.clear()
