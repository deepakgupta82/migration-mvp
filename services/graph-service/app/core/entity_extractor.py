"""
2-Stage Adaptive Entity Extraction.
Stage 1: Analyze document structure and type
Stage 2: Extract entities with adaptive strategy and retry logic
"""
import asyncio
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from itertools import islice
import uuid

from app.models.extraction_models import (
    DocumentAnalysis,
    EntityExtractionResult,
    EntityExtractionAttempt,
    InfrastructureEntity,
    InfrastructureRelationship
)
from app.shared.llm_client import get_llm_client
from app.prompts.infrastructure_prompts import build_extraction_prompt

logger = logging.getLogger(__name__)


class AdaptiveEntityExtractor:
    """2-stage adaptive entity extraction with retry logic."""
    
    def __init__(
        self,
        max_attempts: int = 3,
        timeout_base: int = 300,  # Increased from 180s to 300s (5 minutes) for large documents
        timeout_max: int = 600
    ):
        """
        Initialize extractor.
        
        Args:
            max_attempts: Maximum extraction attempts with progressive enhancement
            timeout_base: Base timeout in seconds (default 300s = 5 minutes)
            timeout_max: Maximum timeout in seconds (default 600s = 10 minutes)
        """
        self.max_attempts = max_attempts
        self.timeout_base = timeout_base
        self.timeout_max = timeout_max
        self.llm_client = get_llm_client()
    
    async def extract_from_content(
        self,
        content: str,
        project_id: Optional[str] = None,
        filename: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> EntityExtractionResult:
        """
        Main extraction method with 2-stage process.
        
        Args:
            content: Content to extract entities from
            project_id: Project ID
            filename: Source filename
            correlation_id: Correlation ID for tracking
        
        Returns:
            EntityExtractionResult with all attempts and final results
        """
        start_time = datetime.utcnow()
        correlation_id = correlation_id or str(uuid.uuid4())
        
        logger.info(
            f"[{correlation_id}] Starting 2-stage entity extraction: "
            f"content_length={len(content)}, filename={filename}"
        )
        
        # Stage 1: Analyze document
        analysis = await self._analyze_document(content, project_id, correlation_id)
        
        logger.info(
            f"[{correlation_id}] Document analysis complete: "
            f"type={analysis.get('document_type')}, "
            f"strategy={analysis.get('extraction_strategy')}, "
            f"confidence={analysis.get('confidence')}"
        )
        
        # Detect large spreadsheets for batch processing
        row_count = content.count('\n')
        doc_type = analysis.get('document_type', '')
        use_batch_processing = (
            row_count > 100 and 
            ('inventory' in doc_type.lower() or 
             'spreadsheet' in doc_type.lower() or
             'server' in doc_type.lower() or
             'asset' in doc_type.lower())
        )
        
        if use_batch_processing:
            logger.info(
                f"[{correlation_id}] Large spreadsheet detected ({row_count} rows), "
                f"using P3 batch processing optimization"
            )
            # Stage 2: Extract with batch processing
            extraction_result = await self._extract_with_batching(
                content=content,
                analysis=analysis,
                project_id=project_id,
                filename=filename,
                correlation_id=correlation_id
            )
        else:
            # Stage 2: Extract with strategy and retry logic (original path)
            extraction_result = await self._extract_with_retry(
                content=content,
                analysis=analysis,
                project_id=project_id,
                filename=filename,
                correlation_id=correlation_id
            )
        
        # Calculate total processing time
        end_time = datetime.utcnow()
        total_ms = int((end_time - start_time).total_seconds() * 1000)
        extraction_result.total_processing_time_ms = total_ms
        extraction_result.correlation_id = correlation_id
        
        # Add document analysis to result
        try:
            extraction_result.document_analysis = DocumentAnalysis(**analysis)
        except Exception as e:
            logger.warning(f"Failed to create DocumentAnalysis model: {e}")
        
        logger.info(
            f"[{correlation_id}] Extraction complete: "
            f"entities={extraction_result.total_entities}, "
            f"relationships={extraction_result.total_relationships}, "
            f"attempts={len(extraction_result.attempts)}, "
            f"time_ms={total_ms}"
        )
        
        return extraction_result
    
    async def _analyze_document(
        self,
        content: str,
        project_id: Optional[str],
        correlation_id: str
    ) -> Dict[str, Any]:
        """Stage 1: Analyze document structure and type."""
        try:
            analysis = await self.llm_client.analyze_document(
                content=content,
                project_id=project_id,
                correlation_id=correlation_id,
                timeout=60  # Analysis should be quick
            )
            
            # Ensure required fields exist
            if not isinstance(analysis, dict):
                analysis = {}
            
            analysis.setdefault("document_type", "infrastructure_general")
            analysis.setdefault("suggested_entities", [])
            analysis.setdefault("extraction_strategy", "mixed_strategy")
            analysis.setdefault("confidence", 0.5)
            analysis.setdefault("key_indicators", [])
            analysis.setdefault("complexity", "medium")
            analysis.setdefault("metadata", {})
            
            return analysis
        
        except Exception as e:
            logger.error(f"[{correlation_id}] Document analysis failed: {e}")
            # Return default analysis
            return {
                "document_type": "infrastructure_general",
                "suggested_entities": [],
                "extraction_strategy": "mixed_strategy",
                "confidence": 0.0,
                "key_indicators": [],
                "complexity": "medium",
                "metadata": {"analysis_error": str(e)}
            }
    
    async def _extract_with_retry(
        self,
        content: str,
        analysis: Dict[str, Any],
        project_id: Optional[str],
        filename: Optional[str],
        correlation_id: str
    ) -> EntityExtractionResult:
        """Stage 2: Extract entities with retry and progressive enhancement."""
        
        result = EntityExtractionResult(
            success=False,
            entities=[],
            relationships=[],
            total_entities=0,
            total_relationships=0,
            attempts=[],
            metadata={
                "filename": filename,
                "document_type": analysis.get("document_type"),
                "extraction_strategy": analysis.get("extraction_strategy")
            }
        )
        
        document_type = analysis.get("document_type", "infrastructure_general")
        focus_entities = analysis.get("suggested_entities", [])
        strategy = analysis.get("extraction_strategy", "mixed_strategy")
        
        for attempt in range(1, self.max_attempts + 1):
            attempt_start = datetime.utcnow()
            
            logger.info(
                f"[{correlation_id}] Extraction attempt {attempt}/{self.max_attempts}: "
                f"type={document_type}, strategy={strategy}"
            )
            
            try:
                # Build prompt for this attempt (enhanced for retries)
                prompt = build_extraction_prompt(
                    document_type=document_type,
                    content=content,
                    focus_entities=focus_entities,
                    strategy=strategy,
                    attempt=attempt,
                    max_chars=20000
                )
                
                # Calculate timeout (increase for each attempt)
                timeout = min(
                    self.timeout_base + (attempt - 1) * 60,
                    self.timeout_max
                )
                
                # Make extraction request
                extraction_data = await self.llm_client.extract_entities(
                    content=content,
                    document_type=document_type,
                    project_id=project_id,
                    correlation_id=correlation_id,
                    focus_entities=focus_entities,
                    strategy=strategy,
                    timeout=timeout
                )
                
                # Parse results
                entities = extraction_data.get("entities", [])
                relationships = extraction_data.get("relationships", [])
                
                attempt_end = datetime.utcnow()
                attempt_time_ms = int((attempt_end - attempt_start).total_seconds() * 1000)
                
                # Record attempt
                attempt_record = EntityExtractionAttempt(
                    attempt_number=attempt,
                    prompt_used=prompt[:1000] + "..." if len(prompt) > 1000 else prompt,
                    strategy=strategy,
                    entities_found=len(entities),
                    relationships_found=len(relationships),
                    success=len(entities) > 0,
                    processing_time_ms=attempt_time_ms
                )
                result.attempts.append(attempt_record)
                
                logger.info(
                    f"[{correlation_id}] Attempt {attempt} extracted: "
                    f"entities={len(entities)}, relationships={len(relationships)}, "
                    f"time_ms={attempt_time_ms}"
                )
                
                # Check if extraction succeeded
                if len(entities) > 0:
                    # Success!
                    result.success = True
                    result.entities = entities
                    result.relationships = relationships
                    result.total_entities = len(entities)
                    result.total_relationships = len(relationships)
                    result.final_strategy = strategy
                    
                    logger.info(
                        f"[{correlation_id}] Extraction succeeded on attempt {attempt}"
                    )
                    break
                else:
                    logger.warning(
                        f"[{correlation_id}] Attempt {attempt} found 0 entities, "
                        f"will retry with enhanced prompt"
                    )
                    
                    # If this was the last attempt, mark as failed
                    if attempt == self.max_attempts:
                        logger.error(
                            f"[{correlation_id}] All {self.max_attempts} attempts "
                            f"failed to extract entities"
                        )
            
            except Exception as e:
                attempt_end = datetime.utcnow()
                attempt_time_ms = int((attempt_end - attempt_start).total_seconds() * 1000)
                
                error_msg = str(e)
                logger.error(
                    f"[{correlation_id}] Attempt {attempt} failed with error: {error_msg}"
                )
                
                # Record failed attempt
                attempt_record = EntityExtractionAttempt(
                    attempt_number=attempt,
                    prompt_used="Error occurred before prompt generation",
                    strategy=strategy,
                    entities_found=0,
                    relationships_found=0,
                    success=False,
                    error=error_msg[:500],  # Truncate long errors
                    processing_time_ms=attempt_time_ms
                )
                result.attempts.append(attempt_record)
                
                # If this was the last attempt, give up
                if attempt == self.max_attempts:
                    logger.error(
                        f"[{correlation_id}] All {self.max_attempts} attempts "
                        f"failed with errors"
                    )
                    result.metadata["final_error"] = error_msg
        
        return result
    
    async def _extract_with_batching(
        self,
        content: str,
        analysis: DocumentAnalysis,
        project_id: str,
        filename: str,
        correlation_id: str = None
    ) -> EntityExtractionResult:
        """
        Extract entities using batch processing for large spreadsheets.
        Splits content into row-based chunks and processes in parallel.
        
        Args:
            content: Document content (large spreadsheet)
            analysis: Document analysis results
            project_id: Project ID for the extraction
            filename: Source filename
            correlation_id: Request tracking ID
            
        Returns:
            EntityExtractionResult with merged entities and relationships
        """
        correlation_id = correlation_id or str(uuid.uuid4())
        result = EntityExtractionResult(
            correlation_id=correlation_id,
            project_id=project_id,
            document_id=filename or "unknown"
        )
        
        try:
            # Split content into chunks
            rows = content.split('\n')
            row_count = len(rows)
            chunk_size = 50  # Process 50 rows at a time
            chunks = [rows[i:i+chunk_size] for i in range(0, row_count, chunk_size)]
            
            logger.info(
                f"[{correlation_id}] Large spreadsheet detected: {row_count} rows. "
                f"Processing in {len(chunks)} chunks with max 3 parallel batches"
            )
            
            # Parallel processing with semaphore (max 3 concurrent)
            semaphore = asyncio.Semaphore(3)
            
            async def process_chunk(chunk_rows: List[str], chunk_id: int) -> Tuple[List[Dict], List[Dict]]:
                """Process a single chunk with retry logic."""
                async with semaphore:
                    chunk_content = '\n'.join(chunk_rows)
                    chunk_row_count = len(chunk_rows)
                    
                    logger.info(
                        f"[{correlation_id}] Processing chunk {chunk_id}/{len(chunks)}: "
                        f"{chunk_row_count} rows"
                    )
                    
                    # Extract entities for this chunk using retry logic
                    for attempt in range(1, self.max_attempts + 1):
                        try:
                            # Build prompt for chunk
                            prompt = build_extraction_prompt(
                                chunk_content,
                                analysis.document_type,
                                analysis.structure,
                                analysis.key_sections
                            )
                            
                            # Calculate timeout based on chunk size
                            timeout = min(
                                self.timeout_base * attempt,
                                self.timeout_max
                            )
                            
                            # Call LLM
                            start_time = datetime.now()
                            
                            llm_response = await self.llm_client.extract_entities(
                                content=chunk_content,
                                prompt=prompt,
                                document_type=analysis.document_type,
                                timeout=timeout
                            )
                            
                            elapsed = (datetime.now() - start_time).total_seconds()
                            
                            # Parse response
                            if isinstance(llm_response, dict):
                                entities = llm_response.get("entities", [])
                                relationships = llm_response.get("relationships", [])
                            else:
                                entities = []
                                relationships = []
                            
                            logger.info(
                                f"[{correlation_id}] Chunk {chunk_id} attempt {attempt}: "
                                f"{len(entities)} entities, {len(relationships)} relationships "
                                f"in {elapsed:.2f}s"
                            )
                            
                            return entities, relationships
                            
                        except Exception as e:
                            logger.warning(
                                f"[{correlation_id}] Chunk {chunk_id} attempt {attempt} "
                                f"failed: {str(e)}"
                            )
                            if attempt == self.max_attempts:
                                logger.error(
                                    f"[{correlation_id}] Chunk {chunk_id} failed after "
                                    f"{self.max_attempts} attempts"
                                )
                                return [], []  # Return empty on failure
                            await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    
                    return [], []
            
            # Process all chunks in parallel
            batch_start = datetime.now()
            tasks = [process_chunk(chunk, i+1) for i, chunk in enumerate(chunks)]
            chunk_results = await asyncio.gather(*tasks)
            batch_elapsed = (datetime.now() - batch_start).total_seconds()
            
            # Merge results from all chunks
            all_entities = []
            all_relationships = []
            for entities, relationships in chunk_results:
                all_entities.extend(entities)
                all_relationships.extend(relationships)
            
            logger.info(
                f"[{correlation_id}] Batch processing complete: "
                f"{len(all_entities)} entities, {len(all_relationships)} relationships "
                f"merged from {len(chunks)} chunks in {batch_elapsed:.2f}s "
                f"(avg {batch_elapsed/len(chunks):.2f}s per chunk)"
            )
            
            # Validate and store results
            result.entities = self.validate_entities(all_entities)
            result.relationships = self.validate_relationships(all_relationships)
            result.entity_count = len(result.entities)
            result.relationship_count = len(result.relationships)
            result.success = True
            result.metadata["batch_processing"] = True
            result.metadata["chunks"] = len(chunks)
            result.metadata["rows_per_chunk"] = chunk_size
            result.metadata["total_rows"] = row_count
            result.metadata["processing_time"] = batch_elapsed
            
        except Exception as e:
            error_msg = f"Batch processing failed: {str(e)}"
            logger.error(f"[{correlation_id}] {error_msg}")
            result.error = error_msg
            result.success = False
            result.metadata["batch_error"] = str(e)
        
        return result
    
    def validate_entities(
        self,
        entities: List[Dict[str, Any]]
    ) -> List[InfrastructureEntity]:
        """Validate and convert entities to standardized format."""
        validated = []
        
        for i, entity in enumerate(entities):
            try:
                # Ensure required fields
                entity_id = entity.get("id") or f"entity_{i}"
                entity_type = entity.get("type", "other")
                name = entity.get("name") or entity_id
                
                # Map to infrastructure entity types
                type_mapping = {
                    "server": "server",
                    "database": "database",
                    "db": "database",
                    "application": "application",
                    "app": "application",
                    "network": "network_device",
                    "storage": "storage_system",
                    "cloud": "cloud_resource",
                    "container": "container",
                    "vm": "virtual_machine",
                    "firewall": "firewall",
                    "loadbalancer": "load_balancer",
                    "lb": "load_balancer"
                }
                
                mapped_type = type_mapping.get(entity_type.lower(), "other")
                
                infrastructure_entity = InfrastructureEntity(
                    entity_id=entity_id,
                    entity_type=mapped_type,
                    name=name,
                    attributes=entity.get("attributes", {}),
                    tags=entity.get("tags", []),
                    confidence=entity.get("confidence", 1.0),
                    metadata=entity.get("metadata", {})
                )
                
                validated.append(infrastructure_entity)
            
            except Exception as e:
                logger.warning(f"Failed to validate entity {i}: {e}")
        
        return validated
    
    def validate_relationships(
        self,
        relationships: List[Dict[str, Any]]
    ) -> List[InfrastructureRelationship]:
        """Validate and convert relationships to standardized format."""
        validated = []
        
        for i, rel in enumerate(relationships):
            try:
                rel_id = rel.get("id") or f"rel_{i}"
                rel_type = rel.get("type", "other")
                source_id = rel.get("source_id") or rel.get("source")
                target_id = rel.get("target_id") or rel.get("target")
                
                if not source_id or not target_id:
                    logger.warning(f"Relationship {i} missing source or target")
                    continue
                
                # Map to infrastructure relationship types
                type_mapping = {
                    "connects": "connects_to",
                    "depends": "depends_on",
                    "hosts": "hosts",
                    "runs": "runs_on",
                    "contains": "contains",
                    "monitors": "monitored_by",
                    "protects": "protected_by"
                }
                
                mapped_type = type_mapping.get(rel_type.lower(), rel_type)
                
                infrastructure_rel = InfrastructureRelationship(
                    relationship_id=rel_id,
                    relationship_type=mapped_type,
                    source_id=source_id,
                    target_id=target_id,
                    properties=rel.get("properties", {}),
                    confidence=rel.get("confidence", 1.0),
                    metadata=rel.get("metadata", {})
                )
                
                validated.append(infrastructure_rel)
            
            except Exception as e:
                logger.warning(f"Failed to validate relationship {i}: {e}")
        
        return validated


# Global extractor instance
_extractor: Optional[AdaptiveEntityExtractor] = None


def get_entity_extractor() -> AdaptiveEntityExtractor:
    """Get or create global entity extractor."""
    global _extractor
    if _extractor is None:
        _extractor = AdaptiveEntityExtractor()
    return _extractor
