"""Tests for hierarchical legal text chunking."""
import yaml
from src.shared.chunking import chunk_constitution, resolve_parents, get_all_parent_texts

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
            text: "Everyone has the right to write tests."
          - number: 2
            id: "art-1-cl-2"
            text: "No law shall impede automated testing."
      - number: 2
        title: "Right to debug"
        id: "art-2"
        clauses:
          - number: 1
            id: "art-2-cl-1"
            text: "Every developer has the right to debug their code."
  - number: 2
    title: "Oversight"
    intro: "Constitutional commissions"
    articles:
      - number: 3
        title: "Testing Commission"
        id: "art-3"
        clauses:
          - number: 1
            id: "art-3-cl-1"
            text: "There shall be an Independent Testing Commission."
          - number: 2
            id: "art-3-cl-2"
            text: "The Commission may investigate test failures."
"""


class TestChunkConstitution:
    def test_chunk_counts(self):
        data = yaml.safe_load(SAMPLE_YAML)
        result = chunk_constitution(data)
        assert len(result["children"]) == 5  # 2 + 1 + 2 clauses
        assert len(result["parents"]) == 3   # 3 articles

    def test_child_chunk_structure(self):
        data = yaml.safe_load(SAMPLE_YAML)
        children = chunk_constitution(data)["children"]

        c = children[0]
        assert c["chunk_id"] == "art-1-cl-1"
        assert c["parent_id"] == "art-1"
        assert c["root_id"] == "art-1"
        assert c["level"] == "clause"
        assert c["depth"] == 2
        assert c["part_number"] == 1
        assert c["part_title"] == "Fundamental Rights"
        assert c["article_number"] == 1
        assert c["article_title"] == "Right to test"
        assert len(c["path"]) == 3

    def test_parent_chunk_structure(self):
        data = yaml.safe_load(SAMPLE_YAML)
        parents = chunk_constitution(data)["parents"]

        p = parents[0]  # Article 1
        assert p["parent_id"] == "art-1"
        assert p["article_number"] == 1
        assert p["part_number"] == 1
        assert "Right to test" in p["full_text"]
        assert "write tests" in p["full_text"]
        assert "automated testing" in p["full_text"]
        assert len(p["child_ids"]) == 2
        assert "art-1-cl-1" in p["child_ids"]
        assert "art-1-cl-2" in p["child_ids"]

    def test_parent_child_link(self):
        data = yaml.safe_load(SAMPLE_YAML)
        result = chunk_constitution(data)
        children = result["children"]
        parents = result["parents"]

        # Match art-1-cl-2 -> should resolve to Article 1
        resolved = resolve_parents(["art-1-cl-2"], children, parents)
        assert len(resolved) == 1
        assert resolved[0]["parent_id"] == "art-1"

    def test_fifth_column_matches(self):
        data = yaml.safe_load(SAMPLE_YAML)
        result = chunk_constitution(data)
        children = result["children"]
        parents = result["parents"]

        # Match all children from Article 1 and Article 3
        # Should deduplicate to 2 unique parents
        resolved = resolve_parents(
            ["art-1-cl-1", "art-1-cl-2", "art-3-cl-1", "art-3-cl-2"],
            children,
            parents,
        )
        assert len(resolved) == 2
        parent_ids = {p["parent_id"] for p in resolved}
        assert parent_ids == {"art-1", "art-3"}

    def test_context_assembly(self):
        data = yaml.safe_load(SAMPLE_YAML)
        result = chunk_constitution(data)
        children = result["children"]
        parents = result["parents"]

        resolved = resolve_parents(["art-1-cl-1", "art-2-cl-1"], children, parents)
        context = get_all_parent_texts(resolved)

        assert "Right to test" in context
        assert "Right to debug" in context
        assert "write tests" in context
        assert "Part 1: Fundamental Rights" in context
