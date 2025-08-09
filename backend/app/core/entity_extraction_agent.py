"""
Entity Extraction Agent for Dynamic Infrastructure Discovery
Uses AI to identify and extract infrastructure entities and relationships from documents
"""

import json
import logging
import os
import asyncio
from typing import Dict, Any, List, Tuple
from langchain.schema import HumanMessage, SystemMessage
from langchain.schema.language_model import BaseLanguageModel

logger = logging.getLogger(__name__)

class EntityExtractionAgent:
    """AI-powered entity extraction agent for infrastructure discovery"""

    def __init__(self, llm: BaseLanguageModel):
        if not llm:
            raise ValueError("LLM is required for entity extraction. Cannot initialize EntityExtractionAgent without a valid LLM instance.")
        self.llm = llm
        self.optimized_chunker = None
        self.parallel_extractor = None
        self.deduplicator = None
        logger.info("EntityExtractionAgent initialized successfully with LLM")

    def _initialize_optimized_components(self):
        """Lazy initialization of optimized components"""
        if self.optimized_chunker is None:
            try:
                from app.core.semantic_chunking import OptimizedChunker
                from app.core.parallel_entity_extractor import ParallelEntityExtractor, EntityDeduplicator

                self.optimized_chunker = OptimizedChunker()
                self.parallel_extractor = ParallelEntityExtractor(max_workers=2, timeout_seconds=45)
                self.deduplicator = EntityDeduplicator()
                logger.info("Optimized extraction components initialized")
            except ImportError as e:
                logger.warning(f"Could not initialize optimized components: {e}")
                self.optimized_chunker = None

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
        # Truncate content if too long to prevent token overflow
        if len(content) > 8000:
            content = content[:8000] + "... [content truncated]"

        return f"""Extract infrastructure entities from this technical document.

DOCUMENT:
{content}

Find entities like: servers, databases, applications, networks, systems, technologies.

RESPOND WITH ONLY JSON:
{{
    "entities": [
        {{"name": "EntityName", "type": "server", "description": "brief description", "properties": {{}}}}
    ],
    "relationships": [
        {{"source": "Entity1", "target": "Entity2", "relationship": "connects_to"}}
    ]
}}

If no entities found: {{"entities": [], "relationships": []}}

JSON:"""

    # NOTE: Regex fallback removed per requirement. Entity extraction must use the project's configured LLM.
    # If extraction fails, raise and stop the pipeline so issues are visible and fixed.

    async def extract_entities_optimized(self, content: str, file_size_mb: float = 0.0) -> Dict[str, Any]:
        """
        Optimized entity extraction using semantic chunking and parallel processing

        Args:
            content: Document content to process
            file_size_mb: File size in MB for strategy selection

        Returns:
            Dictionary with entities, relationships, and processing metadata
        """
        try:
            self._initialize_optimized_components()

            if self.optimized_chunker is None:
                logger.warning("Optimized components not available, falling back to standard extraction")
                return self.extract_entities_and_relationships(content)

            logger.info(f"Starting optimized entity extraction for {file_size_mb:.2f}MB document ({len(content)} chars)")
            import time
            start_time = time.time()

            # Step 1: Intelligent chunking
            chunks, strategy = self.optimized_chunker.process_document(content, file_size_mb)
            logger.info(f"Created {len(chunks)} chunks using '{strategy}' strategy")

            # Log chunk details for debugging
            for i, chunk in enumerate(chunks[:3]):  # Log first 3 chunks
                logger.info(f"Chunk {i+1}: {len(chunk.content)} chars, type: {chunk.chunk_type}")
            if len(chunks) > 3:
                logger.info(f"... and {len(chunks) - 3} more chunks")

            # Step 2: Parallel entity extraction
            if len(chunks) == 1:
                # Single chunk - use standard extraction
                result = self.extract_entities_and_relationships(chunks[0].content)
                entities = result.get("entities", [])
                relationships = result.get("relationships", [])
            else:
                # Multiple chunks - use parallel extraction
                extraction_results = await self.parallel_extractor.extract_entities_parallel(chunks, self)

                # Step 3: Deduplicate and merge results
                entities, relationships = self.deduplicator.deduplicate_entities(extraction_results)

            processing_time = time.time() - start_time

            logger.info(f"Optimized extraction completed in {processing_time:.2f}s - "
                       f"Found {len(entities)} entities and {len(relationships)} relationships")

            return {
                "entities": entities,
                "relationships": relationships,
                "processing_metadata": {
                    "strategy": strategy,
                    "chunks_processed": len(chunks),
                    "processing_time": processing_time,
                    "file_size_mb": file_size_mb
                }
            }

        except Exception as e:
            logger.error(f"Optimized entity extraction failed: {str(e)}")
            # Fallback to standard extraction
            logger.info("Falling back to standard entity extraction")
            return self.extract_entities_and_relationships(content)

    def extract_entities_simple_optimized(self, content: str, file_size_mb: float = 0.0) -> Dict[str, Any]:
        """
        Simplified optimized extraction that doesn't use async (for immediate reliability)
        """
        try:
            logger.info(f"Starting simple optimized extraction for {file_size_mb:.2f}MB document ({len(content)} chars)")

            # Strategy 1: For small content, process as single chunk
            if len(content) <= 20000:
                logger.info("Using single-chunk strategy for small content")
                return self.extract_entities_and_relationships(content)

            # Strategy 2: For larger content, use intelligent chunking but process synchronously
            logger.info("Using intelligent chunking for larger content")

            # Create larger, more meaningful chunks
            chunks = self._create_smart_chunks(content, target_size=15000)
            logger.info(f"Created {len(chunks)} smart chunks (avg size: {sum(len(c) for c in chunks) // len(chunks)} chars)")

            all_entities = []
            all_relationships = []

            for i, chunk in enumerate(chunks):
                try:
                    logger.info(f"Processing chunk {i+1}/{len(chunks)} ({len(chunk)} chars)")
                    result = self.extract_entities_and_relationships(chunk)

                    entities = result.get("entities", [])
                    relationships = result.get("relationships", [])

                    logger.info(f"Chunk {i+1} extracted: {len(entities)} entities, {len(relationships)} relationships")

                    all_entities.extend(entities)
                    all_relationships.extend(relationships)

                except Exception as chunk_error:
                    logger.warning(f"Error processing chunk {i+1}: {chunk_error}")
                    continue

            # Simple deduplication
            unique_entities = self._deduplicate_entities(all_entities)
            unique_relationships = self._deduplicate_relationships(all_relationships)

            logger.info(f"Simple optimized extraction completed - {len(unique_entities)} entities, {len(unique_relationships)} relationships")

            return {
                "entities": unique_entities,
                "relationships": unique_relationships,
                "processing_metadata": {
                    "strategy": "simple_optimized",
                    "chunks_processed": len(chunks),
                    "file_size_mb": file_size_mb
                }
            }

        except Exception as e:
            logger.error(f"Simple optimized extraction failed: {e}")
            return self.extract_entities_and_relationships(content)

    def _create_smart_chunks(self, content: str, target_size: int = 15000) -> List[str]:
        """Create smart chunks based on natural boundaries"""
        chunks = []

        # Try to split by double newlines (paragraphs) first
        paragraphs = content.split('\n\n')
        current_chunk = ""

        for para in paragraphs:
            if len(current_chunk) + len(para) > target_size and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = para
            else:
                current_chunk += "\n\n" + para if current_chunk else para

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        # If chunks are still too large, split by sentences
        final_chunks = []
        for chunk in chunks:
            if len(chunk) > target_size * 1.5:
                sentences = chunk.split('. ')
                current_sentence_chunk = ""
                for sentence in sentences:
                    if len(current_sentence_chunk) + len(sentence) > target_size and current_sentence_chunk:
                        final_chunks.append(current_sentence_chunk.strip())
                        current_sentence_chunk = sentence
                    else:
                        current_sentence_chunk += ". " + sentence if current_sentence_chunk else sentence
                if current_sentence_chunk.strip():
                    final_chunks.append(current_sentence_chunk.strip())
            else:
                final_chunks.append(chunk)

        return final_chunks

    def _deduplicate_entities(self, entities: List[Dict]) -> List[Dict]:
        """Simple entity deduplication by name"""
        seen = set()
        unique = []
        for entity in entities:
            name = entity.get("name", "").strip().lower()
            if name and name not in seen:
                seen.add(name)
                unique.append(entity)
        return unique

    def _deduplicate_relationships(self, relationships: List[Dict]) -> List[Dict]:
        """Simple relationship deduplication"""
        seen = set()
        unique = []
        for rel in relationships:
            source = rel.get("source", "").strip().lower()
            target = rel.get("target", "").strip().lower()
            rel_type = rel.get("type", "").strip().lower()
            key = f"{source}|{target}|{rel_type}"
            if key not in seen:
                seen.add(key)
                unique.append(rel)
        return unique

    async def generate_response(self, prompt: str, temperature: float = 0.1, max_tokens: int = 2000, stop_sequences=None) -> str:
        """
        Generate response using the LLM (for compatibility with parallel extractor)
        """
        try:
            from langchain.schema import HumanMessage
            messages = [HumanMessage(content=prompt)]
            response = self.llm.invoke(messages)
            return response.content if hasattr(response, 'content') else str(response)
        except Exception as e:
            logger.error(f"LLM response generation failed: {e}")
            return ""

