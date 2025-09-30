"""
NL→Cypher helper utilities (template-first, constrained, project-scoped).

This module avoids LLM dependencies by using simple heuristics to produce a
reasonable read-only Cypher given natural language, and also provides a
sanitizer for user-provided Cypher to enforce read-only and project scoping.

Functions:
- build_cypher_from_nl(nl: str, project_id: str) -> str
- sanitize_readonly_cypher(cypher: str, project_id: str) -> str
"""
from __future__ import annotations

import re
from typing import Optional


FORBIDDEN = re.compile(r"\b(merge|create|delete|detach|set\s+\w|call\s+db\.ms|apoc\.periodic|apoc\.do|apoc\.load)\b", re.IGNORECASE)


def _extract_terms(nl: str) -> list[str]:
    nl = (nl or "").strip()
    toks = re.findall(r"[a-zA-Z0-9_.:-]+", nl)
    # Drop common stop words
    stop = {"and", "or", "the", "with", "show", "list", "find", "get", "all", "of", "for", "in"}
    return [t for t in toks if t.lower() not in stop and len(t) >= 2][:5]


def build_cypher_from_nl(nl: str, project_id: str, limit: int = 50) -> str:
    """Heuristic, safe, project-scoped read-only Cypher.

    Strategy: perform a case-insensitive name/label/property substring search for any of the
    extracted terms within the project's subgraph. Results are nodes plus optional immediate
    relationships for context.
    """
    terms = _extract_terms(nl)
    # Default to show top nodes in the project if no terms
    if not terms:
        return (
            "MATCH (p:Project {id:$pid})-[:CONTAINS]->(n) "
            "RETURN n as node LIMIT $lim"
        )
    conds = ["(toLower(n.name) CONTAINS toLower($t{}))".format(i) for i in range(len(terms))]
    where_clause = " OR ".join(conds)
    return (
        "MATCH (p:Project {id:$pid})-[:CONTAINS]->(n) "
        f"WHERE {where_clause} "
        "OPTIONAL MATCH (n)-[r]->(m) "
        "RETURN n as node, collect(distinct {type:type(r), to:id(m)})[0..10] as out_rels "
        "LIMIT $lim"
    )


def sanitize_readonly_cypher(cypher: str, project_id: str, limit: Optional[int] = 100) -> str:
    """Clamp arbitrary Cypher to read-only and ensure project scoping.

    - Rejects dangerous keywords (merge/create/delete/detach/set ...)
    - If query lacks a project match, injects one.
    - Appends a LIMIT if none present (to protect the DB).
    """
    c = (cypher or "").strip()
    if FORBIDDEN.search(c):
        raise ValueError("Forbidden write operation in Cypher")
    # Ensure MATCH (p:Project {id:$pid}) anchor
    if "Project {id:$pid}" not in c:
        c = "MATCH (p:Project {id:$pid}) " + c
    # Ensure LIMIT
    if limit is not None and re.search(r"\blimit\b", c, flags=re.IGNORECASE) is None:
        c = c.rstrip(";") + f" LIMIT $lim"
    return c
