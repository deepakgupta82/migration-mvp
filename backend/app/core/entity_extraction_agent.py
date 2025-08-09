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

            # Parse the JSON response with robust handling
            try:
                response_text = response.content.strip()
                logger.debug(f"Raw AI response: {response_text[:200]}...")

                # Try to extract JSON from markdown code blocks if present
                if "```json" in response_text:
                    # Extract JSON from markdown code block
                    start = response_text.find("```json") + 7
                    end = response_text.find("```", start)
                    if end != -1:
                        response_text = response_text[start:end].strip()
                elif "```" in response_text:
                    # Extract from generic code block
                    start = response_text.find("```") + 3
                    end = response_text.find("```", start)
                    if end != -1:
                        response_text = response_text[start:end].strip()

                # Try to parse JSON
                result = json.loads(response_text)
                logger.info(f"Successfully extracted {len(result.get('entities', {}))} entity types")
                return result

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse AI response as JSON: {e}")
                logger.error(f"Response content: {response.content[:500]}...")

                # Return empty structure instead of failing completely
                logger.warning("Returning empty entity structure due to JSON parsing failure")
                return {
                    "entities": {},
                    "relationships": [],
                    "metadata": {
                        "extraction_status": "failed",
                        "error": str(e)
                    }
                }

        except Exception as e:
            logger.error(f"Error in AI entity extraction: {e}")
            raise

    def _create_system_prompt(self) -> str:
        """Create the system prompt for entity extraction"""
        return """You are an expert infrastructure analyst specializing in cloud migration assessments.
Your task is to analyze technical documents and extract infrastructure entities and their relationships.

IMPORTANT: You must respond with ONLY valid JSON. No explanations, no markdown, just pure JSON.

Analyze the document and extract ALL infrastructure entities you can find, including:
- Servers, hosts, machines, VMs (physical or virtual)
- Applications, software, services, systems, tools
- Databases, data stores, repositories, data sources
- Network components, subnets, VPNs, routers, switches, firewalls
- Storage systems, file shares, volumes, disks, backup systems
- Security components, certificates, access controls, authentication systems
- Cloud services, containers, microservices, APIs
- Operating systems, platforms, frameworks, middleware
- Hardware components, infrastructure devices
- Any other technical infrastructure mentioned

For each entity, provide:
- name: The specific name/identifier found in the document
- type: A descriptive category (e.g., "windows_server", "mysql_database", "web_application")
- description: Brief description from the document context
- properties: Any technical details mentioned (version, OS, size, location, etc.)

Also identify RELATIONSHIPS between entities:
- source: Source entity name
- target: Target entity name
- relationship: Type of relationship (hosts, connects_to, uses, depends_on, communicates_with, etc.)

EXTRACT EVERYTHING - even if you're not 100% certain. It's better to extract too much than too little.

Response format (JSON only):
{
  "entities": [
    {"name": "entity_name", "type": "entity_type", "description": "description", "properties": {"key": "value"}},
    {"name": "another_entity", "type": "another_type", "description": "description", "properties": {"key": "value"}}
  ],
  "relationships": [
    {"source": "entity1", "target": "entity2", "relationship": "relationship_type"},
    {"source": "entity2", "target": "entity3", "relationship": "another_relationship"}
  ]
}

Extract ALL entities you can find - don't limit yourself to predefined categories."""

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

