"""
LLM-Powered Cypher Query Generator
Converts natural language queries to Cypher queries for Neo4j
"""

import re
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class CypherQuery:
	"""Represents a generated Cypher query"""
	query: str
	parameters: Dict[str, Any]
	confidence: float
	explanation: str

class CypherGenerator:
	"""Generate Cypher queries from natural language using LLM (or fallback patterns)."""

	def __init__(self):
		self.node_types = [
			"Server", "Application", "Database", "Network", "Service",
			"Container", "VM", "LoadBalancer", "Cache", "Queue"
		]
		self.relationship_types = [
			"CONNECTS_TO", "DEPENDS_ON", "HOSTS", "RUNS_ON", "COMMUNICATES_WITH",
			"STORES_DATA_IN", "LOAD_BALANCES", "CACHES_FOR", "QUEUES_FOR"
		]
		self.common_properties = [
			"name", "type", "version", "port", "ip_address", "status",
			"environment", "location", "owner", "criticality"
		]

	def generate_cypher_from_natural_language(self, natural_query: str, llm: Optional[Any] = None) -> CypherQuery:
		"""Convert natural language query to Cypher using an LLM when available, else fallback."""
		if llm is None:
			return self._pattern_based_generation(natural_query)
		try:
			return self._llm_based_generation(natural_query, llm)
		except Exception as e:
			logger.error(f"LLM-based generation failed: {e}")
			return self._pattern_based_generation(natural_query)

	def _llm_based_generation(self, natural_query: str, llm: Any) -> CypherQuery:
		schema_info = self._get_schema_description()
		prompt = f"""
You are a Neo4j Cypher query expert. Convert the following natural language query to a Cypher query.

Database Schema:
{schema_info}

Natural Language Query: "{natural_query}"

Requirements:
1. Generate a valid Cypher query
2. Use appropriate node labels and relationship types from the schema
3. Include relevant WHERE clauses for filtering
4. Use parameters for dynamic values
5. Optimize for performance with appropriate indexes

Response format (JSON):
{{
  "cypher_query": "MATCH (n:NodeType) WHERE n.property = $param RETURN n",
  "parameters": {{"param": "value"}},
  "confidence": 0.95,
  "explanation": "This query finds nodes of type NodeType with specific property value"
}}
"""
		try:
			response = llm.invoke(prompt)
			content = getattr(response, 'content', None) or str(response)
			result = self._parse_llm_response(content)
			query = result.get('cypher_query') or "MATCH (n) RETURN n LIMIT 10"
			if self._validate_cypher_query(query):
				return CypherQuery(
					query=query,
					parameters=result.get('parameters', {}),
					confidence=float(result.get('confidence', 0.8)),
					explanation=result.get('explanation', 'LLM-generated query')
				)
			logger.warning("LLM generated invalid Cypher; using pattern-based fallback")
			return self._pattern_based_generation(natural_query)
		except Exception as e:
			logger.error(f"Error in LLM-based generation: {e}")
			return self._pattern_based_generation(natural_query)

	def _pattern_based_generation(self, natural_query: str) -> CypherQuery:
		q = natural_query.lower()
		m = re.search(r'find all (\w+)', q)
		if m:
			node_type = self._normalize_node_type(m.group(1))
			return CypherQuery(
				query=f"MATCH (n:{node_type}) RETURN n",
				parameters={},
				confidence=0.7,
				explanation=f"Find all nodes of type {node_type}"
			)
		m = re.search(r'find (\w+) connected to (\w+)', q)
		if m:
			s = self._normalize_node_type(m.group(1))
			t = self._normalize_node_type(m.group(2))
			return CypherQuery(
				query=f"MATCH (s:{s})-[r:CONNECTS_TO]->(t:{t}) RETURN s, r, t",
				parameters={},
				confidence=0.8,
				explanation=f"Find {s} nodes connected to {t} nodes"
			)
		m = re.search(r'find (\w+) with (\w+) (.+)', q)
		if m:
			node_type = self._normalize_node_type(m.group(1))
			prop = m.group(2)
			val = m.group(3).strip('"\'')
			return CypherQuery(
				query=f"MATCH (n:{node_type}) WHERE n.{prop} = $value RETURN n",
				parameters={"value": val},
				confidence=0.75,
				explanation=f"Find {node_type} with {prop} = {val}"
			)
		m = re.search(r'find dependencies of (\w+)', q)
		if m:
			node_type = self._normalize_node_type(m.group(1))
			return CypherQuery(
				query=f"MATCH (n:{node_type})-[r:DEPENDS_ON]->(dep) RETURN n, r, dep",
				parameters={},
				confidence=0.8,
				explanation=f"Find dependencies of {node_type} nodes"
			)
		m = re.search(r'find what depends on (\w+)', q)
		if m:
			node_type = self._normalize_node_type(m.group(1))
			return CypherQuery(
				query=f"MATCH (dependent)-[r:DEPENDS_ON]->(n:{node_type}) RETURN dependent, r, n",
				parameters={},
				confidence=0.8,
				explanation=f"Find what depends on {node_type} nodes"
			)
		m = re.search(r'count (\w+)', q)
		if m:
			node_type = self._normalize_node_type(m.group(1))
			return CypherQuery(
				query=f"MATCH (n:{node_type}) RETURN count(n) as count",
				parameters={},
				confidence=0.9,
				explanation=f"Count {node_type} nodes"
			)
		return CypherQuery(
			query="MATCH (n) RETURN n LIMIT 25",
			parameters={},
			confidence=0.3,
			explanation="Default query returning sample nodes"
		)

	def _get_schema_description(self) -> str:
		return f"""
Node Types: {', '.join(self.node_types)}
Relationship Types: {', '.join(self.relationship_types)}
Common Properties: {', '.join(self.common_properties)}

Example Patterns:
- (s:Server)-[:HOSTS]->(a:Application)
- (a:Application)-[:DEPENDS_ON]->(d:Database)
- (lb:LoadBalancer)-[:LOAD_BALANCES]->(s:Server)
- (a:Application)-[:COMMUNICATES_WITH]->(s:Service)
"""

	def _normalize_node_type(self, node_type: str) -> str:
		node_type = node_type.lower()
		mapping = {
			'server': 'Server', 'servers': 'Server',
			'app': 'Application', 'application': 'Application', 'applications': 'Application',
			'db': 'Database', 'database': 'Database', 'databases': 'Database',
			'service': 'Service', 'services': 'Service',
			'network': 'Network', 'container': 'Container', 'containers': 'Container',
			'vm': 'VM', 'vms': 'VM',
			'loadbalancer': 'LoadBalancer', 'load_balancer': 'LoadBalancer',
			'cache': 'Cache', 'queue': 'Queue'
		}
		return mapping.get(node_type, node_type.capitalize())

	def _parse_llm_response(self, response: str) -> Dict[str, Any]:
		try:
			import json
			if response.strip().startswith('{'):
				return json.loads(response)
			cypher_match = re.search(r'cypher_query["\']?\s*:\s*["\']([^"\']+)["\']', response, re.IGNORECASE)
			confidence_match = re.search(r'confidence["\']?\s*:\s*([0-9.]+)', response, re.IGNORECASE)
			explanation_match = re.search(r'explanation["\']?\s*:\s*["\']([^"\']+)["\']', response, re.IGNORECASE)
			return {
				'cypher_query': cypher_match.group(1) if cypher_match else "MATCH (n) RETURN n LIMIT 10",
				'parameters': {},
				'confidence': float(confidence_match.group(1)) if confidence_match else 0.5,
				'explanation': explanation_match.group(1) if explanation_match else "Extracted from LLM response",
			}
		except Exception as e:
			logger.error(f"Parse LLM response error: {e}")
			return {
				'cypher_query': "MATCH (n) RETURN n LIMIT 10",
				'parameters': {},
				'confidence': 0.3,
				'explanation': "Failed to parse LLM response",
			}

	def _validate_cypher_query(self, query: str) -> bool:
		try:
			u = query.upper()
			if not any(k in u for k in ['MATCH', 'CREATE', 'MERGE', 'DELETE', 'SET', 'REMOVE']):
				return False
			if 'MATCH' in u and 'RETURN' not in u and 'DELETE' not in u:
				return False
			if query.count('(') != query.count(')'):
				return False
			if query.count('[') != query.count(']'):
				return False
			if query.count('{') != query.count('}'):
				return False
			return True
		except Exception:
			return False

	def explain_query(self, query: str) -> str:
		parts: List[str] = []
		U = query.upper()
		if 'MATCH' in U: parts.append("This query searches for patterns")
		if 'WHERE' in U: parts.append("with filters")
		if 'RETURN' in U: parts.append("and returns results")
		if 'ORDER BY' in U: parts.append("sorted")
		if 'LIMIT' in U: parts.append("limited count")
		return "; ".join(parts) or "Graph operation"
