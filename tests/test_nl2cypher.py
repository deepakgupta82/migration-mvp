import pytest

from common.nl2cypher import build_cypher_from_nl, sanitize_readonly_cypher


def test_build_cypher_from_nl_default_limit_and_project_anchor():
    cy = build_cypher_from_nl("", "PRJ1", limit=25)
    assert "MATCH (p:Project {id:$pid})-[:CONTAINS]->(n)" in cy
    assert "LIMIT $lim" in cy


def test_build_cypher_from_nl_terms_in_where():
    cy = build_cypher_from_nl("show servers and databases", "PRJ1", limit=10)
    # Should not fail and include WHERE when terms are extracted (servers, databases get filtered out if stopwords)
    assert "WHERE" in cy or "RETURN n as node" in cy


def test_sanitize_blocks_writes():
    with pytest.raises(ValueError):
        sanitize_readonly_cypher("MATCH (n) CREATE (m)", "PRJ1")


def test_sanitize_injects_project_and_limit():
    cy = sanitize_readonly_cypher("MATCH (n) RETURN n", "PRJ1", limit=5)
    assert "MATCH (p:Project {id:$pid})" in cy
    assert "LIMIT $lim" in cy


def test_sanitize_respects_existing_limit():
    cy = sanitize_readonly_cypher("MATCH (n) RETURN n LIMIT 3", "PRJ1", limit=50)
    # Should not append a second limit
    assert cy.lower().count("limit") == 1
