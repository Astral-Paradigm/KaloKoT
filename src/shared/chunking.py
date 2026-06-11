"""Hierarchical chunking for legal text — parent-child linking.

Legal text (constitutions, statutes) has a deep hierarchy:
  Part -> Article -> Clause -> SubClause

Standard flat chunking breaks this hierarchy. This module:
- Scans the structured YAML hierarchy
- Creates *child chunks* (individual clauses) for vector matching
- Creates *parent chunks* (full articles) for context delivery
- Links each child to its parent via stable IDs

When ChromaDB matches a child chunk, the system retrieves
the full parent article for Gemini context.
"""

from __future__ import annotations

from typing import Dict, List, Optional, TypedDict


class Chunk(TypedDict, total=False):
    """A single chunk in the hierarchy."""
    chunk_id: str                     # Unique ID (e.g. "art-24-cl-3")
    text: str                         # The chunk text content
    parent_id: str                    # ID of the parent chunk (e.g. "art-24")
    root_id: str                      # ID of the root article
    level: str                        # "part" | "article" | "clause" | "subclause"
    depth: int                        # 0=part, 1=article, 2=clause, 3=subclause
    title: str                        # Human-readable title
    part_number: int                  # Part number
    part_title: str                   # Part title
    article_number: Optional[int]     # Article number (if applicable)
    article_title: Optional[str]       # Article title (if applicable)
    path: List[str]                   # Breadcrumb path for display


class ParentChunk(TypedDict, total=False):
    """A parent chunk — the full text of a legal article."""
    parent_id: str
    full_text: str
    child_ids: List[str]
    title: str
    part_number: int
    part_title: str
    article_number: int
    article_title: str


def chunk_constitution(yaml_data: dict) -> Dict[str, List[Chunk]]:
    """Chunk a constitution YAML into hierarchical chunks.

    Args:
        yaml_data: Parsed constitution YAML with 'parts' list.

    Returns:
        dict with 'children' (individual clause chunks for vector matching)
        and 'parents' (full article text for context).
    """
    children: List[Chunk] = []
    parents: List[ParentChunk] = []

    parts = yaml_data.get("parts", [])
    for part in parts:
        part_number = part.get("number", 0)
        part_title = part.get("title", "")

        for article in part.get("articles", []):
            article_number = article.get("number")
            article_title = article.get("title", "")
            art_id = article.get("id", f"art-{article_number}")

            clauses = article.get("clauses", [])

            # Build the full article text for parent chunk
            article_header = f"Article {article_number}: {article_title}"
            clause_texts: List[str] = []
            for clause in clauses:
                clause_texts.append(clause.get("text", ""))

            full_article_text = f"{article_header}\n\n" + "\n".join(
                f"({c.get('number')}) {c.get('text')}"
                for c in clauses
            )

            # Collect child IDs
            child_ids: List[str] = []
            for clause in clauses:
                clause_id = clause.get("id", f"{art_id}-cl-{clause.get('number')}")
                child_ids.append(clause_id)

                # Build breadcrumb
                path = [
                    f"Part {part_number}: {part_title}",
                    article_header,
                    f"Clause {clause.get('number')}",
                ]

                child: Chunk = {
                    "chunk_id": clause_id,
                    "text": clause.get("text", ""),
                    "parent_id": art_id,
                    "root_id": art_id,
                    "level": "clause",
                    "depth": 2,
                    "title": f"Article {article_number}, Clause {clause.get('number')}",
                    "part_number": part_number,
                    "part_title": part_title,
                    "article_number": article_number,
                    "article_title": article_title,
                    "path": path,
                }
                children.append(child)

                # Also index sub-clauses if present
                sub_clauses = clause.get("sub_clauses", [])
                for sub in sub_clauses:
                    sub_id = sub.get("id", f"{clause_id}-sub-{sub.get('number')}")
                    sub_path = path + [f"Sub-clause {sub.get('number')}"]
                    child_ids.append(sub_id)

                    sub_child: Chunk = {
                        "chunk_id": sub_id,
                        "text": sub.get("text", ""),
                        "parent_id": art_id,
                        "root_id": art_id,
                        "level": "subclause",
                        "depth": 3,
                        "title": f"Article {article_number}, Clause {clause.get('number')}, Sub-clause {sub.get('number')}",
                        "part_number": part_number,
                        "part_title": part_title,
                        "article_number": article_number,
                        "article_title": article_title,
                        "path": sub_path,
                    }
                    children.append(sub_child)

            parent: ParentChunk = {
                "parent_id": art_id,
                "full_text": full_article_text,
                "child_ids": child_ids,
                "title": article_header,
                "part_number": part_number,
                "part_title": part_title,
                "article_number": article_number or 0,
                "article_title": article_title,
            }
            parents.append(parent)

    return {"children": children, "parents": parents}


def resolve_parents(
    matched_child_ids: List[str],
    children: List[Chunk],
    parents: List[ParentChunk],
) -> List[ParentChunk]:
    """Resolve full parent articles from matched child chunk IDs.

    For each matched child, find its parent article and return
    the deduplicated list of parent chunks with their full text.

    This is the key "Parent-Child Retrieval" step: vector search
    matches small chunks, but Gemini gets the full article.
    """
    parent_ids_seen: set = set()
    resolved: List[ParentChunk] = []

    child_lookup: Dict[str, Chunk] = {c["chunk_id"]: c for c in children}
    parent_lookup: Dict[str, ParentChunk] = {p["parent_id"]: p for p in parents}

    for child_id in matched_child_ids:
        child = child_lookup.get(child_id)
        if not child:
            continue
        parent_id = child.get("parent_id", "")
        if not parent_id or parent_id in parent_ids_seen:
            continue
        parent_ids_seen.add(parent_id)
        parent = parent_lookup.get(parent_id)
        if parent:
            resolved.append(parent)

    return resolved


def get_all_parent_texts(parents: List[ParentChunk]) -> str:
    """Join multiple parent articles into a single context string."""
    if not parents:
        return ""
    sections = []
    for p in parents:
        header = f"--- {p['title']} (Part {p['part_number']}: {p['part_title']}) ---"
        sections.append(f"{header}\n{p['full_text']}")
    return "\n\n".join(sections)
