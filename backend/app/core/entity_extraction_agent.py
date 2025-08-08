"""
Entity Extraction Agent for Dynamic Infrastructure Discovery
Uses AI to identify and extract infrastructure entities and relationships from documents
"""

import json
import logging
from typing import Dict, Any
from langchain.schema import HumanMessage, SystemMessage
from langchain.schema.language_model import BaseLanguageModel

logger = logging.getLogger(__name__)

class EntityExtractionAgent:
    """AI-powered entity extraction agent for infrastructure discovery"""

    def __init__(self, llm: BaseLanguageModel):
        if not llm:
            raise ValueError("LLM is required for entity extraction. Cannot initialize EntityExtractionAgent without a valid LLM instance.")
        self.llm = llm
        logger.info("EntityExtractionAgent initialized successfully with LLM")

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
                raise ValueError(f"AI response was not valid JSON. Entity extraction aborted: {e}")

        except Exception as e:
            logger.error(f"Error in AI entity extraction: {e}")
            raise

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

    # NOTE: Regex fallback removed per requirement. Entity extraction must use the project's configured LLM.
    # If extraction fails, raise and stop the pipeline so issues are visible and fixed.

