"""
LLM-Powered Cypher Query Generator
Converts natural language queries to Cypher queries for Neo4j
"""

import re
import logging
from typing import Dict, List, Any, Optional, Tuple
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
    """Generate Cypher queries from natural language using LLM"""
    
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
    
    def generate_cypher_from_natural_language(self, natural_query: str, llm=None) -> CypherQuery:
        """Convert natural language query to Cypher using LLM"""
        if llm is None:
            # Fallback to pattern-based generation
            return self._pattern_based_generation(natural_query)
        
        try:
            # Use LLM for sophisticated query generation
            return self._llm_based_generation(natural_query, llm)
        except Exception as e:
            logger.error(f"LLM-based generation failed: {str(e)}")
            # Fallback to pattern-based generation
            return self._pattern_based_generation(natural_query)
    
    def _llm_based_generation(self, natural_query: str, llm) -> CypherQuery:
        """Use LLM to generate Cypher query"""
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

        Generate the Cypher query:
        """
        
        try:
            response = llm.invoke(prompt)
            result = self._parse_llm_response(response.content if hasattr(response, 'content') else str(response))
            
            # Validate the generated query
            if self._validate_cypher_query(result['cypher_query']):
                return CypherQuery(
                    query=result['cypher_query'],
                    parameters=result.get('parameters', {}),
                    confidence=result.get('confidence', 0.8),
                    explanation=result.get('explanation', 'LLM-generated query')
                )
            else:
                logger.warning("LLM generated invalid Cypher query, falling back to pattern-based")
                return self._pattern_based_generation(natural_query)
        
        except Exception as e:
            logger.error(f"Error in LLM-based generation: {str(e)}")
            return self._pattern_based_generation(natural_query)
    
    def _pattern_based_generation(self, natural_query: str) -> CypherQuery:
        """Generate Cypher query using pattern matching (fallback)"""
        query_lower = natural_query.lower()
        
        # Pattern 1: Find all X
        if re.search(r'find all (\w+)', query_lower):
            node_type = re.search(r'find all (\w+)', query_lower).group(1)
            node_type = self._normalize_node_type(node_type)
            return CypherQuery(
                query=f"MATCH (n:{node_type}) RETURN n",
                parameters={},
                confidence=0.7,
                explanation=f"Find all nodes of type {node_type}"
            )
        
        # Pattern 2: Find X connected to Y
        if re.search(r'find (\w+) connected to (\w+)', query_lower):
            match = re.search(r'find (\w+) connected to (\w+)', query_lower)
            source_type = self._normalize_node_type(match.group(1))
            target_type = self._normalize_node_type(match.group(2))
            return CypherQuery(
                query=f"MATCH (s:{source_type})-[r:CONNECTS_TO]->(t:{target_type}) RETURN s, r, t",
                parameters={},
                confidence=0.8,
                explanation=f"Find {source_type} nodes connected to {target_type} nodes"
            )
        
        # Pattern 3: Find X with property Y
        if re.search(r'find (\w+) with (\w+) (.+)', query_lower):
            match = re.search(r'find (\w+) with (\w+) (.+)', query_lower)
            node_type = self._normalize_node_type(match.group(1))
            property_name = match.group(2)
            property_value = match.group(3).strip('"\'')
            return CypherQuery(
                query=f"MATCH (n:{node_type}) WHERE n.{property_name} = $value RETURN n",
                parameters={"value": property_value},
                confidence=0.75,
                explanation=f"Find {node_type} nodes with {property_name} = {property_value}"
            )
        
        # Pattern 4: Find dependencies of X
        if re.search(r'find dependencies of (\w+)', query_lower):
            node_type = re.search(r'find dependencies of (\w+)', query_lower).group(1)
            node_type = self._normalize_node_type(node_type)
            return CypherQuery(
                query=f"MATCH (n:{node_type})-[r:DEPENDS_ON]->(dep) RETURN n, r, dep",
                parameters={},
                confidence=0.8,
                explanation=f"Find all dependencies of {node_type} nodes"
            )
        
        # Pattern 5: Find what depends on X
        if re.search(r'find what depends on (\w+)', query_lower):
            node_type = re.search(r'find what depends on (\w+)', query_lower).group(1)
            node_type = self._normalize_node_type(node_type)
            return CypherQuery(
                query=f"MATCH (dependent)-[r:DEPENDS_ON]->(n:{node_type}) RETURN dependent, r, n",
                parameters={},
                confidence=0.8,
                explanation=f"Find what depends on {node_type} nodes"
            )
        
        # Pattern 6: Count X
        if re.search(r'count (\w+)', query_lower):
            node_type = re.search(r'count (\w+)', query_lower).group(1)
            node_type = self._normalize_node_type(node_type)
            return CypherQuery(
                query=f"MATCH (n:{node_type}) RETURN count(n) as count",
                parameters={},
                confidence=0.9,
                explanation=f"Count the number of {node_type} nodes"
            )
        
        # Default: Return all nodes
        return CypherQuery(
            query="MATCH (n) RETURN n LIMIT 25",
            parameters={},
            confidence=0.3,
            explanation="Default query to return all nodes (limited to 25)"
        )
    
    def _get_schema_description(self) -> str:
        """Get a description of the database schema"""
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
        """Normalize node type to match schema"""
        node_type = node_type.lower()
        
        # Mapping common terms to schema node types
        type_mapping = {
            'server': 'Server',
            'servers': 'Server',
            'app': 'Application',
            'application': 'Application',
            'applications': 'Application',
            'db': 'Database',
            'database': 'Database',
            'databases': 'Database',
            'service': 'Service',
            'services': 'Service',
            'network': 'Network',
            'container': 'Container',
            'containers': 'Container',
            'vm': 'VM',
            'vms': 'VM',
            'loadbalancer': 'LoadBalancer',
            'load_balancer': 'LoadBalancer',
            'cache': 'Cache',
            'queue': 'Queue'
        }
        
        return type_mapping.get(node_type, node_type.capitalize())
    
    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM response to extract Cypher query components"""
        try:
            # Try to parse as JSON first
            import json
            if response.strip().startswith('{'):
                return json.loads(response)
            
            # If not JSON, try to extract components using regex
            cypher_match = re.search(r'cypher_query["\']?\s*:\s*["\']([^"\']+)["\']', response, re.IGNORECASE)
            confidence_match = re.search(r'confidence["\']?\s*:\s*([0-9.]+)', response, re.IGNORECASE)
            explanation_match = re.search(r'explanation["\']?\s*:\s*["\']([^"\']+)["\']', response, re.IGNORECASE)
            
            result = {
                'cypher_query': cypher_match.group(1) if cypher_match else "MATCH (n) RETURN n LIMIT 10",
                'parameters': {},
                'confidence': float(confidence_match.group(1)) if confidence_match else 0.5,
                'explanation': explanation_match.group(1) if explanation_match else "Extracted from LLM response"
            }
            
            return result
        
        except Exception as e:
            logger.error(f"Error parsing LLM response: {str(e)}")
            return {
                'cypher_query': "MATCH (n) RETURN n LIMIT 10",
                'parameters': {},
                'confidence': 0.3,
                'explanation': "Failed to parse LLM response"
            }
    
    def _validate_cypher_query(self, query: str) -> bool:
        """Basic validation of Cypher query syntax"""
        try:
            # Basic syntax checks
            query_upper = query.upper()
            
            # Must contain at least one of these keywords
            required_keywords = ['MATCH', 'CREATE', 'MERGE', 'DELETE', 'SET', 'REMOVE']
            if not any(keyword in query_upper for keyword in required_keywords):
                return False
            
            # Must contain RETURN if it's a read query
            if 'MATCH' in query_upper and 'RETURN' not in query_upper and 'DELETE' not in query_upper:
                return False
            
            # Check for balanced parentheses
            if query.count('(') != query.count(')'):
                return False
            
            # Check for balanced brackets
            if query.count('[') != query.count(']'):
                return False
            
            # Check for balanced braces
            if query.count('{') != query.count('}'):
                return False
            
            return True
        
        except Exception:
            return False
    
    def optimize_query(self, query: str) -> str:
        """Optimize Cypher query for better performance"""
        # Add LIMIT if not present and it's a MATCH query
        if 'MATCH' in query.upper() and 'LIMIT' not in query.upper() and 'COUNT' not in query.upper():
            query += " LIMIT 100"
        
        # Add index hints for common properties
        for prop in ['name', 'id', 'type']:
            pattern = f"n.{prop} = "
            if pattern in query and f"USING INDEX n:{prop}" not in query:
                # This is a simplified optimization - in practice, you'd need schema info
                pass
        
        return query
    
    def explain_query(self, query: str) -> str:
        """Generate human-readable explanation of Cypher query"""
        explanations = []
        
        if 'MATCH' in query.upper():
            explanations.append("This query searches for patterns in the graph")
        
        if 'WHERE' in query.upper():
            explanations.append("with specific filtering conditions")
        
        if 'RETURN' in query.upper():
            explanations.append("and returns the matching results")
        
        if 'ORDER BY' in query.upper():
            explanations.append("sorted in a specific order")
        
        if 'LIMIT' in query.upper():
            explanations.append("limited to a maximum number of results")
        
        return " ".join(explanations) if explanations else "This query performs graph operations"
