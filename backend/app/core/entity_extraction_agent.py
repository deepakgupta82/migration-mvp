"""
Entity Extraction Agent for Dynamic Infrastructure Discovery
Uses AI to identify and extract infrastructure entities and relationships from documents
"""

import json
import logging
import re
from typing import Dict, List, Tuple, Any
from langchain.schema import BaseMessage, HumanMessage, SystemMessage
from langchain.schema.language_model import BaseLanguageModel

logger = logging.getLogger(__name__)

class EntityExtractionAgent:
    """AI-powered entity extraction agent for infrastructure discovery"""
    
    def __init__(self, llm: BaseLanguageModel):
        self.llm = llm
        
    def extract_entities_and_relationships(self, content: str) -> Dict[str, Any]:
        """
        Extract infrastructure entities and relationships from document content
        Returns structured data with entities and their relationships
        """
        try:
            # Create the extraction prompt
            system_prompt = self._create_system_prompt()
            human_prompt = self._create_human_prompt(content)
            
            # Get AI response
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            response = self.llm.invoke(messages)
            
            # Parse the JSON response
            try:
                result = json.loads(response.content)
                logger.info(f"Successfully extracted {len(result.get('entities', {}))} entity types")
                return result
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse AI response as JSON: {e}")
                return self._fallback_extraction(content)
                
        except Exception as e:
            logger.error(f"Error in AI entity extraction: {e}")
            return self._fallback_extraction(content)
    
    def _create_system_prompt(self) -> str:
        """Create the system prompt for entity extraction"""
        return """You are an expert infrastructure analyst specializing in cloud migration assessments. 
Your task is to analyze technical documents and extract infrastructure entities and their relationships.

IMPORTANT: You must respond with ONLY valid JSON. No explanations, no markdown, just pure JSON.

Extract the following types of entities:
1. SERVERS: Physical/virtual servers, hosts, machines
2. APPLICATIONS: Software applications, services, systems
3. DATABASES: Database systems, data stores
4. NETWORKS: Network components, subnets, VPNs
5. STORAGE: Storage systems, file shares, volumes
6. SECURITY: Firewalls, security groups, certificates

For each entity, identify:
- name: The specific name/identifier
- type: The category (server, application, database, etc.)
- description: Brief description if available
- properties: Any technical details (OS, version, size, etc.)

Also identify RELATIONSHIPS between entities:
- source: Source entity name
- target: Target entity name  
- relationship: Type of relationship (hosts, connects_to, uses, depends_on, etc.)

Response format (JSON only):
{
  "entities": {
    "servers": [{"name": "server1", "type": "server", "description": "...", "properties": {...}}],
    "applications": [{"name": "app1", "type": "application", "description": "...", "properties": {...}}],
    "databases": [{"name": "db1", "type": "database", "description": "...", "properties": {...}}],
    "networks": [{"name": "net1", "type": "network", "description": "...", "properties": {...}}],
    "storage": [{"name": "storage1", "type": "storage", "description": "...", "properties": {...}}],
    "security": [{"name": "fw1", "type": "security", "description": "...", "properties": {...}}]
  },
  "relationships": [
    {"source": "server1", "target": "app1", "relationship": "hosts"},
    {"source": "app1", "target": "db1", "relationship": "uses"}
  ]
}"""

    def _create_human_prompt(self, content: str) -> str:
        """Create the human prompt with the document content"""
        # Truncate content if too long to avoid token limits
        max_content_length = 4000
        if len(content) > max_content_length:
            content = content[:max_content_length] + "... [truncated]"
            
        return f"""Analyze the following technical document and extract infrastructure entities and relationships.
Focus on concrete, specific names and identifiers mentioned in the text.

Document content:
{content}

Remember: Respond with ONLY valid JSON following the specified format."""

    def _fallback_extraction(self, content: str) -> Dict[str, Any]:
        """Fallback extraction using regex patterns when AI fails"""
        logger.info("Using fallback regex-based entity extraction")
        
        # Enhanced regex patterns for different entity types
        patterns = {
            "servers": [
                r'\b(?:server|srv|host|machine|vm|node)[-_]?\w*\d+\b',
                r'\b\w+[-_](?:server|srv|host|vm)\b',
                r'\b(?:web|app|db|mail|file|dns|proxy)[-_]?(?:server|srv)\d*\b',
                r'\b(?:windows|linux|unix)[-_]?\w*\d*\b'
            ],
            "applications": [
                r'\b(?:application|app|service|system)[-_]?\w*\b',
                r'\b\w+[-_](?:application|app|service|sys)\b',
                r'\b(?:web|mobile|desktop|api)[-_]?(?:app|application|service)\b',
                r'\b(?:apache|nginx|iis|tomcat|jboss|websphere)\b',
                r'\b(?:sap|oracle|salesforce|sharepoint|exchange)\b'
            ],
            "databases": [
                r'\b(?:database|db|datastore)[-_]?\w*\b',
                r'\b\w+[-_](?:database|db)\b',
                r'\b(?:mysql|postgresql|postgres|oracle|sqlserver|mongodb|redis|cassandra|elasticsearch)\b',
                r'\b(?:sql|nosql)[-_]?\w*\b'
            ],
            "networks": [
                r'\b(?:network|subnet|vlan|vpn)[-_]?\w*\b',
                r'\b(?:lan|wan|dmz|vnet)\b',
                r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?:/\d{1,2})?\b',  # IP addresses/CIDR
                r'\b(?:switch|router|firewall|gateway)[-_]?\w*\b'
            ],
            "storage": [
                r'\b(?:storage|disk|volume|share|nas|san)[-_]?\w*\b',
                r'\b\w+[-_](?:storage|disk|vol)\b',
                r'\b(?:file|block|object)[-_]?storage\b'
            ],
            "security": [
                r'\b(?:firewall|fw|security|cert|ssl|tls)[-_]?\w*\b',
                r'\b(?:antivirus|av|ids|ips|waf)\b',
                r'\b(?:active[-_]?directory|ad|ldap)\b'
            ]
        }
        
        entities = {}
        content_lower = content.lower()
        
        for entity_type, type_patterns in patterns.items():
            found_entities = set()
            for pattern in type_patterns:
                matches = re.findall(pattern, content_lower, re.IGNORECASE)
                found_entities.update(matches)
            
            # Convert to structured format
            entities[entity_type] = [
                {
                    "name": entity,
                    "type": entity_type.rstrip('s'),  # Remove plural
                    "description": f"Extracted {entity_type.rstrip('s')} from document",
                    "properties": {"extraction_method": "regex_fallback"}
                }
                for entity in found_entities
            ]
        
        # Simple relationship inference based on co-occurrence
        relationships = []
        all_entities = []
        for entity_list in entities.values():
            all_entities.extend([e["name"] for e in entity_list])
        
        # Basic relationship patterns
        for server in [e["name"] for e in entities.get("servers", [])]:
            for app in [e["name"] for e in entities.get("applications", [])]:
                if server in content_lower and app in content_lower:
                    # Check if they appear close to each other
                    server_pos = content_lower.find(server)
                    app_pos = content_lower.find(app)
                    if abs(server_pos - app_pos) < 200:  # Within 200 characters
                        relationships.append({
                            "source": server,
                            "target": app,
                            "relationship": "hosts"
                        })
        
        for app in [e["name"] for e in entities.get("applications", [])]:
            for db in [e["name"] for e in entities.get("databases", [])]:
                if app in content_lower and db in content_lower:
                    app_pos = content_lower.find(app)
                    db_pos = content_lower.find(db)
                    if abs(app_pos - db_pos) < 200:
                        relationships.append({
                            "source": app,
                            "target": db,
                            "relationship": "uses"
                        })
        
        return {
            "entities": entities,
            "relationships": relationships
        }
