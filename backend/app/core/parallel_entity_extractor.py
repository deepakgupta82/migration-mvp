"""
Parallel Entity Extraction with Improved AI Prompting
Processes multiple chunks concurrently and handles AI response failures gracefully
"""

import asyncio
import json
import logging
from typing import List, Dict, Any, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import time

from app.core.semantic_chunking import DocumentChunk

logger = logging.getLogger(__name__)


@dataclass
class ExtractionResult:
    """Result of entity extraction from a chunk"""
    chunk_id: int
    entities: List[Dict]
    relationships: List[Dict]
    success: bool
    error_message: str = None
    processing_time: float = 0.0


class ParallelEntityExtractor:
    """Parallel entity extraction with improved prompting and error handling"""
    
    def __init__(self, max_workers: int = 3, timeout_seconds: int = 30):
        self.max_workers = max_workers
        self.timeout_seconds = timeout_seconds
        
    async def extract_entities_parallel(self, chunks: List[DocumentChunk], llm_client) -> List[ExtractionResult]:
        """
        Extract entities from multiple chunks in parallel
        
        Args:
            chunks: List of document chunks to process
            llm_client: LLM client for entity extraction
            
        Returns:
            List of extraction results
        """
        logger.info(f"Starting parallel entity extraction for {len(chunks)} chunks")
        start_time = time.time()
        
        # Create tasks for parallel processing
        tasks = []
        for chunk in chunks:
            task = self._extract_from_chunk(chunk, llm_client)
            tasks.append(task)
        
        # Process chunks in batches to avoid overwhelming the LLM
        batch_size = min(self.max_workers, len(chunks))
        results = []
        
        for i in range(0, len(tasks), batch_size):
            batch_tasks = tasks[i:i + batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}/{(len(tasks) + batch_size - 1)//batch_size}")
            
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            
            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"Batch processing error: {result}")
                    results.append(ExtractionResult(
                        chunk_id=-1,
                        entities=[],
                        relationships=[],
                        success=False,
                        error_message=str(result)
                    ))
                else:
                    results.append(result)
            
            # Small delay between batches to be respectful to LLM API
            if i + batch_size < len(tasks):
                await asyncio.sleep(1)
        
        total_time = time.time() - start_time
        successful_extractions = sum(1 for r in results if r.success)
        
        logger.info(f"Parallel extraction completed in {total_time:.2f}s - {successful_extractions}/{len(chunks)} successful")
        
        return results
    
    async def _extract_from_chunk(self, chunk: DocumentChunk, llm_client) -> ExtractionResult:
        """Extract entities from a single chunk with improved prompting"""
        start_time = time.time()
        
        try:
            # Use improved prompt that's more likely to get valid responses
            prompt = self._create_improved_prompt(chunk)
            
            # Make LLM call with timeout
            response = await asyncio.wait_for(
                self._call_llm_with_retry(llm_client, prompt),
                timeout=self.timeout_seconds
            )
            
            # Parse response with multiple fallback strategies
            entities, relationships = self._parse_response_robust(response, chunk.chunk_id)
            
            processing_time = time.time() - start_time
            
            return ExtractionResult(
                chunk_id=chunk.chunk_id,
                entities=entities,
                relationships=relationships,
                success=True,
                processing_time=processing_time
            )
            
        except asyncio.TimeoutError:
            logger.warning(f"Timeout extracting entities from chunk {chunk.chunk_id}")
            return ExtractionResult(
                chunk_id=chunk.chunk_id,
                entities=[],
                relationships=[],
                success=False,
                error_message="Timeout",
                processing_time=self.timeout_seconds
            )
            
        except Exception as e:
            logger.error(f"Error extracting entities from chunk {chunk.chunk_id}: {e}")
            return ExtractionResult(
                chunk_id=chunk.chunk_id,
                entities=[],
                relationships=[],
                success=False,
                error_message=str(e),
                processing_time=time.time() - start_time
            )
    
    def _create_improved_prompt(self, chunk: DocumentChunk) -> str:
        """Create an improved prompt that's more likely to get valid JSON responses"""

        # Truncate content to prevent token overflow and improve focus
        content = chunk.content[:6000] if len(chunk.content) > 6000 else chunk.content

        prompt = f"""Extract infrastructure entities from this technical document.

DOCUMENT TEXT:
{content}

Extract entities like: servers, databases, applications, networks, systems, technologies, processes.

RESPOND WITH ONLY THIS JSON FORMAT:
{{
    "entities": [
        {{"name": "EntityName", "type": "server|database|application|network|system", "description": "brief description"}}
    ],
    "relationships": [
        {{"source": "Entity1", "target": "Entity2", "type": "connects_to|depends_on|hosts", "description": "how they relate"}}
    ]
}}

If no technical entities found, respond: {{"entities": [], "relationships": []}}

JSON:"""

        return prompt
    
    async def _call_llm_with_retry(self, llm_client, prompt: str, max_retries: int = 2) -> str:
        """Call LLM with retry logic for better reliability"""
        
        for attempt in range(max_retries + 1):
            try:
                # Adjust parameters for more reliable responses
                response = await llm_client.generate_response(
                    prompt=prompt,
                    temperature=0.1,  # Lower temperature for more consistent output
                    max_tokens=2000,  # Reasonable limit for JSON response
                    stop_sequences=None
                )
                
                if response and response.strip():
                    return response.strip()
                else:
                    logger.warning(f"Empty response from LLM (attempt {attempt + 1})")
                    if attempt < max_retries:
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
                        continue
                    else:
                        return '{"entities": [], "relationships": []}'
                        
            except Exception as e:
                logger.warning(f"LLM call failed (attempt {attempt + 1}): {e}")
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)
                    continue
                else:
                    raise e
        
        return '{"entities": [], "relationships": []}'
    
    def _parse_response_robust(self, response: str, chunk_id: int) -> Tuple[List[Dict], List[Dict]]:
        """Parse LLM response with multiple fallback strategies"""
        
        if not response or not response.strip():
            logger.warning(f"Empty response for chunk {chunk_id}")
            return [], []
        
        # Strategy 1: Direct JSON parsing
        try:
            data = json.loads(response)
            entities = data.get("entities", [])
            relationships = data.get("relationships", [])
            
            # Validate structure
            if isinstance(entities, list) and isinstance(relationships, list):
                return entities, relationships
                
        except json.JSONDecodeError:
            pass
        
        # Strategy 2: Extract JSON from response (in case of extra text)
        try:
            # Look for JSON block in response
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                data = json.loads(json_str)
                entities = data.get("entities", [])
                relationships = data.get("relationships", [])
                return entities, relationships
                
        except (json.JSONDecodeError, AttributeError):
            pass
        
        # Strategy 3: Try to fix common JSON issues
        try:
            # Fix common issues like trailing commas, missing quotes
            fixed_response = self._fix_common_json_issues(response)
            data = json.loads(fixed_response)
            entities = data.get("entities", [])
            relationships = data.get("relationships", [])
            return entities, relationships
            
        except json.JSONDecodeError:
            pass
        
        # Strategy 4: Parse as text and extract entities manually
        try:
            entities, relationships = self._parse_as_text(response)
            if entities or relationships:
                return entities, relationships
                
        except Exception:
            pass
        
        logger.warning(f"Could not parse response for chunk {chunk_id}: {response[:200]}...")
        return [], []
    
    def _fix_common_json_issues(self, response: str) -> str:
        """Fix common JSON formatting issues"""
        import re
        
        # Remove trailing commas
        response = re.sub(r',\s*}', '}', response)
        response = re.sub(r',\s*]', ']', response)
        
        # Ensure proper quotes around keys
        response = re.sub(r'(\w+):', r'"\1":', response)
        
        # Fix single quotes to double quotes
        response = response.replace("'", '"')
        
        return response
    
    def _parse_as_text(self, response: str) -> Tuple[List[Dict], List[Dict]]:
        """Parse response as text when JSON parsing fails"""
        entities = []
        relationships = []
        
        # Simple text parsing for entity-like patterns
        import re
        
        # Look for entity patterns
        entity_patterns = [
            r'(?:Entity|entity):\s*([^\n]+)',
            r'(?:System|system):\s*([^\n]+)',
            r'(?:Component|component):\s*([^\n]+)',
        ]
        
        for pattern in entity_patterns:
            matches = re.findall(pattern, response, re.IGNORECASE)
            for match in matches:
                entities.append({
                    "name": match.strip(),
                    "type": "extracted_entity",
                    "description": "Extracted from text parsing",
                    "properties": {}
                })
        
        return entities, relationships


class EntityDeduplicator:
    """Deduplicate and merge entities across chunks"""
    
    def deduplicate_entities(self, results: List[ExtractionResult]) -> Tuple[List[Dict], List[Dict]]:
        """
        Deduplicate entities and relationships across all chunks
        
        Returns:
            Tuple of (unique_entities, unique_relationships)
        """
        entity_map = {}
        relationships = []
        
        for result in results:
            if not result.success:
                continue
                
            # Process entities
            for entity in result.entities:
                name = entity.get("name", "").strip().lower()
                if name and name not in entity_map:
                    entity_map[name] = entity
                elif name in entity_map:
                    # Merge properties if entity already exists
                    existing = entity_map[name]
                    if "properties" in entity:
                        existing.setdefault("properties", {}).update(entity.get("properties", {}))
            
            # Collect relationships (will deduplicate later)
            relationships.extend(result.relationships)
        
        # Deduplicate relationships
        unique_relationships = []
        seen_relationships = set()
        
        for rel in relationships:
            source = rel.get("source", "").strip().lower()
            target = rel.get("target", "").strip().lower()
            rel_type = rel.get("type", "").strip().lower()
            
            rel_key = f"{source}|{target}|{rel_type}"
            if rel_key not in seen_relationships:
                seen_relationships.add(rel_key)
                unique_relationships.append(rel)
        
        unique_entities = list(entity_map.values())
        
        logger.info(f"Deduplicated to {len(unique_entities)} entities and {len(unique_relationships)} relationships")
        
        return unique_entities, unique_relationships
