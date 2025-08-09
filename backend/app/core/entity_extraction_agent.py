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

                # Check for completely empty response first
                if not response_text or response_text.isspace():
                    logger.warning("AI returned completely empty response")
                    raise json.JSONDecodeError("Empty response from AI", "", 0)

                # Enhanced JSON extraction from AI response with multiple strategies
                original_response = response_text

                # Strategy 1: Extract from markdown code blocks
                if "```json" in response_text:
                    start = response_text.find("```json") + 7
                    end = response_text.find("```", start)
                    if end != -1:
                        response_text = response_text[start:end].strip()
                elif "```" in response_text:
                    start = response_text.find("```") + 3
                    # Skip any language identifier on the same line
                    newline_pos = response_text.find('\n', start)
                    if newline_pos != -1:
                        start = newline_pos + 1
                    end = response_text.find("```", start)
                    if end != -1:
                        response_text = response_text[start:end].strip()

                # Strategy 2: Clean common AI response artifacts
                response_text = response_text.replace('```json', '').replace('```', '')
                response_text = response_text.replace('\n\n', '\n').strip()

                # Strategy 3: Find JSON boundaries
                first_brace = response_text.find('{')
                last_brace = response_text.rfind('}')

                if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                    response_text = response_text[first_brace:last_brace + 1]
                else:
                    # No valid JSON structure found
                    logger.warning("No valid JSON structure found in AI response")
                    raise json.JSONDecodeError("No JSON braces found", response_text, 0)

                # Strategy 4: Final validation before parsing
                if not response_text or response_text.isspace():
                    logger.warning("Response became empty after cleaning")
                    raise json.JSONDecodeError("Response empty after cleaning", "", 0)

                # Try to parse JSON
                result = json.loads(response_text)
                logger.info(f"Successfully extracted {len(result.get('entities', {}))} entity types")
                return result

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse AI response as JSON: {e}")
                logger.error(f"Response content: {response.content[:500]}...")

                # Try one more time with more aggressive cleaning
                try:
                    # Remove all markdown formatting and extra text
                    clean_text = response.content.strip()

                    # Remove any text before the first {
                    if '{' in clean_text:
                        clean_text = clean_text[clean_text.find('{'):]

                    # Remove any text after the last }
                    if '}' in clean_text:
                        clean_text = clean_text[:clean_text.rfind('}') + 1]

                    # Try parsing the cleaned text
                    result = json.loads(clean_text)
                    logger.info(f"Successfully parsed JSON after aggressive cleaning")
                    return result

                except Exception as final_error:
                    logger.error(f"Final JSON parsing attempt failed: {final_error}")

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

