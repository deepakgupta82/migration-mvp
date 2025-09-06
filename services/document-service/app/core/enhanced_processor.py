"""
Enhanced Document Processor with Structured Workflow
Implements Step 3-6 improvements: unstructured.io primary, service integration, JSONL output

This processor aligns with the expected document processing workflow:
1. Upload (handled by router)
2. Processing Request (handled by router) 
3. Conversion & Structuring (this module - unstructured.io primary)
4. Semantic Embedding (automatic vector-service integration)
5. Entity & Relationship Extraction (automatic graph-service integration)
6. Completion & Notification (WebSocket integration)
"""

import os
import logging
import tempfile
import asyncio
import json
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import httpx

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
from services.shared.service_client import get_service_client
from services.shared.websocket_client import get_websocket_client

# Import structured processor
from .structured_processor import StructuredDocumentProcessor, ProcessingResult
from .progress_tracker import ProgressTracker
from .semantic_chunking import SemanticChunker

# Import LLM analyzer for enhanced processing
try:
    from .llm_content_analyzer import LLMContentAnalyzer
    LLM_ANALYZER_AVAILABLE = True
except ImportError:
    LLM_ANALYZER_AVAILABLE = False
    # logger.warning("LLM Content Analyzer not available for enhanced processing")  # Commented out until logger is defined

logger = logging.getLogger("document-service.enhanced-processor")

class EnhancedDocumentProcessor:
    """
    Enhanced document processor implementing the expected workflow:
    - unstructured.io as PRIMARY method (not fallback)
    - Structured JSONL output with rich metadata
    - Automatic service integration (vector, graph, websocket)
    - Correlation ID tracking throughout the pipeline
    """
    
    def __init__(self):
        self.structured_processor = StructuredDocumentProcessor()
        self.progress_tracker = ProgressTracker()
        self.semantic_chunker = SemanticChunker()  # Initialize semantic chunker for JSONL-aware processing

        # Initialize LLM analyzer for enhanced processing
        self.llm_analyzer = None
        if LLM_ANALYZER_AVAILABLE:
            try:
                self.llm_analyzer = LLMContentAnalyzer()
                logger.info("LLM Content Analyzer initialized for enhanced processing")
            except Exception as e:
                logger.warning(f"Failed to initialize LLM Content Analyzer: {e}")
                self.llm_analyzer = None

        # Service URLs
        self.vector_url = os.getenv("VECTOR_SERVICE_URL", "http://localhost:8005")
        self.graph_url = os.getenv("GRAPH_SERVICE_URL", "http://localhost:8006")
        self.websocket_url = os.getenv("WEBSOCKET_SERVICE_URL", "http://localhost:8009")
        self.storage_url = os.getenv("STORAGE_SERVICE_URL", "http://localhost:8010")
        self.database_url = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/db")

        # Configuration
        self.http_timeout = httpx.Timeout(300.0, connect=30.0)  # Increased timeout for complex operations
        self.auth_token = os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')

        # Processing options
        self.enable_vector_integration = os.getenv("ENABLE_VECTOR_INTEGRATION", "true").lower() == "true"
        self.enable_graph_integration = os.getenv("ENABLE_GRAPH_INTEGRATION", "true").lower() == "true"
        self.enable_websocket_notifications = os.getenv("ENABLE_WEBSOCKET_NOTIFICATIONS", "true").lower() == "true"
        self.enable_llm_analysis = os.getenv("ENABLE_LLM_ANALYSIS", "true").lower() == "true"

        # FORCE ENABLE graph integration for debugging - this ensures it's always enabled
        if not self.enable_graph_integration:
            logger.warning("Graph integration was disabled, FORCE ENABLING for debugging!")
            self.enable_graph_integration = True

        logger.info(f"Enhanced Processor Configuration: vector={self.enable_vector_integration}, graph={self.enable_graph_integration}, websocket={self.enable_websocket_notifications}, llm={self.enable_llm_analysis}")

        # Performance optimization
        self.max_concurrent_integrations = int(os.getenv("MAX_CONCURRENT_INTEGRATIONS", "2"))
        self.enable_parallel_processing = os.getenv("ENABLE_PARALLEL_PROCESSING", "true").lower() == "true"

        # Thread pool for CPU-bound operations
        self.thread_pool = ThreadPoolExecutor(max_workers=min(4, (os.cpu_count() or 1) + 1))

        logger.info("Enhanced Document Processor initialized with service integration and performance optimizations")
    
    async def process_document_enhanced(
        self,
        file_path: str,
        filename: str,
        project_id: str,
        correlation_id: Optional[str] = None,
        extract_images: bool = True,
        extract_tables: bool = True,
        include_coordinates: bool = True
    ) -> Dict[str, Any]:
        """
        Process document using enhanced structured workflow
        
        Returns:
            Dict with processing results and integration status
        """
        
        # Generate correlation ID if not provided
        if not correlation_id:
            correlation_id = str(uuid.uuid4())
        
        logger.info(f"Starting enhanced processing for {filename} [corr_id={correlation_id}]")
        
        # Start progress tracking
        event_id = await self.progress_tracker.start_operation(
            project_id, correlation_id, f"Process {filename}", 7
        )
        
        try:
            # Step 3: Conversion & Structuring (unstructured.io PRIMARY)
            await self.progress_tracker.update_operation_progress(
                event_id, "Analyzing and parsing document content...", 1
            )

            # Send WebSocket notification - Processing Started
            await self._send_websocket_notification(
                project_id, correlation_id, "document_processing_started",
                {"filename": filename, "stage": "conversion_structuring", "progress": 10}
            )
            
            # Process with structured processor (unstructured.io primary)
            processing_result = await self.structured_processor.process_document(
                file_path=file_path,
                filename=filename,
                project_id=project_id,
                correlation_id=correlation_id,
                extract_images=extract_images,
                extract_tables=extract_tables,
                include_coordinates=include_coordinates
            )
            
            if processing_result.status != "success":
                logger.error(f"Structured processing failed for {filename}: {processing_result.errors}")
                await self.progress_tracker.complete_operation(event_id, False, str(processing_result.errors))
                await self._send_websocket_notification(
                    project_id, correlation_id, "document_processing_failed",
                    {"filename": filename, "stage": "conversion_structuring", "errors": processing_result.errors}
                )
                return {
                    "status": "error",
                    "stage": "conversion_structuring",
                    "errors": processing_result.errors,
                    "correlation_id": correlation_id
                }
            
            # Save structured JSONL output to Storage Service
            base_name = os.path.splitext(filename)[0]
            structured_filename = f"{base_name}_structured.jsonl"

            await self.progress_tracker.update_operation_progress(
                event_id, "Saving structured output...", 2
            )

            await self._send_websocket_notification(
                project_id, correlation_id, "document_processing_progress",
                {"filename": filename, "stage": "saving_output", "progress": 25}
            )

            await self._save_structured_output(
                project_id, structured_filename, processing_result, correlation_id, llm_analysis_result
            )
            
            logger.info(f"Structured processing completed: {len(processing_result.elements)} elements extracted")

            # Step 3.5: LLM Analysis Integration (if enabled)
            llm_analysis_result = None
            if self.enable_llm_analysis and self.llm_analyzer:
                await self.progress_tracker.update_operation_progress(
                    event_id, "Performing LLM analysis...", 3
                )

                await self._send_websocket_notification(
                    project_id, correlation_id, "document_processing_progress",
                    {"filename": filename, "stage": "llm_analysis", "progress": 30}
                )

                llm_analysis_result = await self._integrate_llm_analysis(
                    project_id, processing_result, correlation_id
                )

                logger.info(f"LLM analysis completed for {filename}")

            # Step 4 & 5: Parallel Service Integration for Performance
            logger.info(f"Service integration config: parallel={self.enable_parallel_processing}, vector={self.enable_vector_integration}, graph={self.enable_graph_integration}")
            
            if self.enable_parallel_processing:
                # Run vector and graph integration in parallel
                integration_tasks = []

                if self.enable_vector_integration:
                    logger.info("Adding vector integration task to parallel execution")
                    integration_tasks.append(self._integrate_vector_service(
                        project_id, processing_result, correlation_id
                    ))

                if self.enable_graph_integration:
                    logger.info("Adding graph integration task to parallel execution")
                    integration_tasks.append(self._integrate_graph_service(
                        project_id, processing_result, correlation_id
                    ))

                logger.info(f"Total integration tasks scheduled: {len(integration_tasks)}")

                # Wait for all integrations to complete
                if integration_tasks:
                    logger.info(f"Executing {len(integration_tasks)} integration tasks in parallel")
                    await self.progress_tracker.update_operation_progress(
                        event_id, "Integrating with vector and graph services...", 3
                    )

                    await self._send_websocket_notification(
                        project_id, correlation_id, "document_processing_progress",
                        {"filename": filename, "stage": "starting_integration", "progress": 40}
                    )

                    integration_results = await asyncio.gather(*integration_tasks, return_exceptions=True)
                    logger.info(f"Parallel integration completed with {len(integration_results)} results")

                    await self._send_websocket_notification(
                        project_id, correlation_id, "document_processing_progress",
                        {"filename": filename, "stage": "integration_completed", "progress": 75}
                    )

                    # Handle results with proper type checking
                    vector_status = {"status": "disabled"}
                    graph_status = {"status": "disabled"}

                    result_index = 0
                    if self.enable_vector_integration:
                        vector_result = integration_results[result_index]
                        if isinstance(vector_result, Exception):
                            vector_status = {"status": "error", "message": str(vector_result)}
                        elif isinstance(vector_result, dict):
                            vector_status = vector_result
                        result_index += 1

                    if self.enable_graph_integration:
                        logger.info(f"Processing graph integration result at index {result_index}")
                        graph_result = integration_results[result_index]
                        if isinstance(graph_result, Exception):
                            logger.error(f"Graph integration failed with exception: {graph_result}")
                            graph_status = {"status": "error", "message": str(graph_result)}
                        elif isinstance(graph_result, dict):
                            logger.info(f"Graph integration completed with status: {graph_result.get('status')}")
                            graph_status = graph_result
                        else:
                            logger.warning(f"Unexpected graph result type: {type(graph_result)}")
                            graph_status = {"status": "error", "message": f"Unexpected result type: {type(graph_result)}"}
                else:
                    logger.warning("No integration tasks were scheduled - all services may be disabled")
                    vector_status = {"status": "disabled"}
                    graph_status = {"status": "disabled"}
            else:
                # Sequential processing (original behavior)
                logger.info("Using sequential processing mode")
                
                # Step 4: Semantic Embedding (Vector Service Integration)
                await self.progress_tracker.update_operation_progress(
                    event_id, "Creating vector embeddings...", 3
                )
                
                if self.enable_vector_integration:
                    logger.info("Starting vector integration (sequential)")

                    await self._send_websocket_notification(
                        project_id, correlation_id, "document_processing_progress",
                        {"filename": filename, "stage": "vector_integration", "progress": 30}
                    )

                    vector_status = await self._integrate_vector_service(
                        project_id, processing_result, correlation_id
                    )
                    logger.info(f"Vector integration completed with status: {vector_status.get('status')}")

                    await self._send_websocket_notification(
                        project_id, correlation_id, "document_processing_progress",
                        {"filename": filename, "stage": "vector_completed", "progress": 45}
                    )
                else:
                    logger.info("Vector integration disabled")
                    vector_status = {"status": "disabled"}
                
                # Step 5: Entity & Relationship Extraction (Graph Service Integration)
                await self.progress_tracker.update_operation_progress(
                    event_id, "Extracting entities and relationships...", 4
                )
                
                if self.enable_graph_integration:
                    logger.info("Starting graph integration (sequential)")

                    await self._send_websocket_notification(
                        project_id, correlation_id, "document_processing_progress",
                        {"filename": filename, "stage": "graph_integration", "progress": 50}
                    )

                    graph_status = await self._integrate_graph_service(
                        project_id, processing_result, correlation_id
                    )
                    logger.info(f"Graph integration completed with status: {graph_status.get('status')}")

                    await self._send_websocket_notification(
                        project_id, correlation_id, "document_processing_progress",
                        {"filename": filename, "stage": "graph_completed", "progress": 70}
                    )
                else:
                    logger.info("Graph integration disabled")
                    graph_status = {"status": "disabled"}
            
            # Step 6: Stats Update & Completion Notification
            await self.progress_tracker.update_operation_progress(
                event_id, "Finalizing and updating statistics...", 5
            )

            await self._send_websocket_notification(
                project_id, correlation_id, "document_processing_progress",
                {"filename": filename, "stage": "updating_stats", "progress": 80}
            )

            # Extract and notify stats service of embeddings and graph updates
            await self._notify_stats_service(
                project_id, vector_status, graph_status, correlation_id
            )

            await self.progress_tracker.update_operation_progress(
                event_id, "Sending completion notifications...", 6
            )

            await self._send_websocket_notification(
                project_id, correlation_id, "document_processing_progress",
                {"filename": filename, "stage": "finalizing", "progress": 95}
            )

            await self._send_websocket_notification(
                project_id, correlation_id, "document_processing_completed",
                {
                    "filename": filename,
                    "structured_output": structured_filename,
                    "elements_extracted": len(processing_result.elements),
                    "vector_integration": vector_status,
                    "graph_integration": graph_status,
                    "processing_time": processing_result.processing_stats.get("processing_time_seconds", 0),
                    "progress": 100
                }
            )
            
            await self.progress_tracker.complete_operation(event_id, True)
            
            # Prepare comprehensive analysis result
            analysis_result = {
                "status": "success",
                "filename": filename,
                "structured_output": structured_filename,
                "elements_extracted": len(processing_result.elements),
                "element_types": processing_result.processing_stats.get("element_types", {}),
                "processing_time": processing_result.processing_stats.get("processing_time_seconds", 0),
                "vector_integration": vector_status,
                "graph_integration": graph_status,
                "llm_analysis": llm_analysis_result,
                "correlation_id": correlation_id,
                "processing_result": processing_result
            }

            # Store analysis result in database if LLM analysis was performed
            if llm_analysis_result:
                await self._store_analysis_result(analysis_result, correlation_id)

            return analysis_result
            
        except Exception as e:
            logger.error(f"Enhanced processing failed for {filename}: {e}")
            await self.progress_tracker.complete_operation(event_id, False, str(e))
            await self._send_websocket_notification(
                project_id, correlation_id, "document_processing_failed",
                {"filename": filename, "error": str(e)}
            )
            return {
                "status": "error",
                "filename": filename,
                "error": str(e),
                "correlation_id": correlation_id
            }
    
    async def _save_structured_output(
        self,
        project_id: str,
        filename: str,
        processing_result: ProcessingResult,
        correlation_id: str,
        llm_analysis_result: Optional[Dict[str, Any]] = None
    ):
        """Save structured JSONL output to Storage Service with LLM analysis metadata"""
        try:
            jsonl_content = processing_result.to_jsonl(llm_analysis_result)

            client = await get_service_client()
            # Upload to Storage Service structured folder
            files_data = {
                'files': (filename, jsonl_content.encode('utf-8'), 'application/jsonl')
            }

            headers = {
                "X-Correlation-ID": correlation_id
            }

            response = await client.post(
                "storage",
                f"/api/storage/projects/{project_id}/upload/structured",
                files=files_data,
                headers=headers
            )

            if response.get("status_code") == 200:
                logger.info(f"Saved structured output with LLM analysis: {filename}")
            else:
                logger.error(f"Failed to save structured output: {response}")
                # Don't fail the entire process if structured storage fails
                # This allows the document to still be processed successfully

        except Exception as e:
            logger.error(f"Error saving structured output: {e}")
    
    async def generate_enhanced_chunks(
        self,
        processing_result: ProcessingResult,
        chunking_strategy: str = "jsonl_aware"
    ) -> List[Dict[str, Any]]:
        """
        Generate enhanced chunks using JSONL-aware chunking strategy
        
        Args:
            processing_result: The structured processing result
            chunking_strategy: Strategy to use ('jsonl_aware', 'semantic', 'paragraph')
            
        Returns:
            List of enhanced chunks with metadata
        """
        try:
            # Prepare JSONL data from structured elements
            jsonl_data = []
            full_text_parts = []
            
            for element in processing_result.elements:
                if element.text.strip():  # Only include non-empty elements
                    jsonl_element = {
                        "type": element.type,
                        "content": element.text,
                        "metadata": element.metadata,
                        "page_number": element.page_number,
                        "element_id": element.element_id,
                        "hierarchy_level": element.hierarchy_level or 0,
                        "semantic_tags": element.semantic_tags or [],
                        "confidence_score": element.confidence_score or 0.8
                    }
                    jsonl_data.append(jsonl_element)
                    full_text_parts.append(element.text)
            
            # Combine all text for chunking
            full_text = "\n\n".join(full_text_parts)
            
            if chunking_strategy == "jsonl_aware" and jsonl_data:
                logger.info(f"Using JSONL-aware chunking strategy with {len(jsonl_data)} elements")
                # Use the enhanced JSONL-aware chunking
                chunks = self.semantic_chunker.chunk(full_text, "jsonl_aware", jsonl_data)
            else:
                logger.info(f"Using fallback semantic chunking strategy")
                # Fallback to semantic chunking
                chunks = self.semantic_chunker.chunk(full_text, "semantic")
            
            # Convert chunks to enhanced format with metadata
            enhanced_chunks = []
            for i, chunk in enumerate(chunks):
                # Pull original filename from processing_result or storage metadata
                original_filename = processing_result.document_metadata.filename
                if not original_filename:
                    # Fallback: query storage-service for metadata
                    try:
                        client = await get_service_client()
                        response = await client.get(
                            "storage",
                            f"/api/storage/projects/{processing_result.document_metadata.project_id}/metadata/{processing_result.document_metadata.filename}_metadata.json"
                        )
                        if response.get("status_code") == 200:
                            metadata = response
                            original_filename = metadata.get("original_filename", processing_result.document_metadata.filename)
                    except Exception:
                        pass  # Use default if query fails
                
                enhanced_chunk = {
                    "chunk_id": f"{original_filename}_{i}",
                    "content": chunk.content,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "start_position": chunk.start,
                    "end_position": chunk.end,
                    "document_metadata": {
                        "filename": original_filename,
                        "project_id": processing_result.document_metadata.project_id,
                        "correlation_id": processing_result.document_metadata.correlation_id
                    },
                    "chunking_metadata": {
                        "strategy": chunking_strategy,
                        "chunk_type": getattr(chunk, 'chunk_type', 'semantic'),
                        "contains_elements": getattr(chunk, 'metadata', {}).get('contains_elements', []),
                        "logical_boundaries": getattr(chunk, 'metadata', {}).get('logical_boundaries', [])
                    }
                }
                enhanced_chunks.append(enhanced_chunk)
            
            logger.info(f"Generated {len(enhanced_chunks)} enhanced chunks using {chunking_strategy} strategy")
            return enhanced_chunks
            
        except Exception as e:
            logger.error(f"Error generating enhanced chunks: {e}")
            # Return simple fallback chunks
            fallback_text = "\n\n".join([elem.text for elem in processing_result.elements if elem.text.strip()])
            simple_chunks = self.semantic_chunker.chunk(fallback_text, "paragraph")
            
            return [{
                "chunk_id": f"{processing_result.document_metadata.filename}_{i}",
                "content": chunk.content,
                "chunk_index": i,
                "total_chunks": len(simple_chunks),
                "start_position": chunk.start,
                "end_position": chunk.end,
                "document_metadata": {
                    "filename": processing_result.document_metadata.filename,
                    "project_id": processing_result.document_metadata.project_id,
                    "correlation_id": processing_result.document_metadata.correlation_id
                },
                "chunking_metadata": {
                    "strategy": "paragraph_fallback",
                    "chunk_type": "fallback",
                    "error": str(e)
                }
            } for i, chunk in enumerate(simple_chunks)]
    
    async def _integrate_vector_service(
        self,
        project_id: str,
        processing_result: ProcessingResult,
        correlation_id: str
    ) -> Dict[str, Any]:
        """
        Step 4: Semantic Embedding Integration with Enhanced JSONL-Aware Chunking
        Generate enhanced chunks and send to Vector Service for embedding
        """
        if not self.enable_vector_integration:
            return {"status": "disabled", "message": "Vector integration disabled"}
        
        try:
            # Convert structured elements to vector service format
            structured_documents = []
            for element in processing_result.elements:
                if element.type in ['title', 'narrative_text', 'list_item', 'table'] and len(element.text.strip()) > 10:
                    structured_documents.append({
                        "element_id": element.element_id,
                        "content": element.text,
                        "element_type": element.type,
                        "page_number": element.page_number,
                        "hierarchy_level": element.hierarchy_level,
                        "semantic_tags": getattr(element, 'semantic_tags', []),
                        "metadata": element.metadata
                    })
            
            if not structured_documents:
                return {"status": "skipped", "message": "No suitable elements for vector processing"}
            
            # Send to Vector Service for structured processing
            client = await get_service_client()
            payload = {
                "documents": structured_documents,
                "processing_type": "structured",
                "chunking_strategy": "element_based",
                "source": "enhanced_document_processor_v2"
            }

            headers = {
                "X-Correlation-ID": correlation_id
            }

            response = await client.post(
                "vector",
                f"/api/vectors/projects/{project_id}/process-structured",
                json=payload,
                headers=headers
            )

            if response.get("status_code") == 200:
                result = response
                embeddings_created = result.get("embeddings_created", 0)
                elements_processed = result.get("elements_processed", 0)
                logger.info(f"Enhanced vector integration successful: {elements_processed} elements processed, {embeddings_created} embeddings created")
                return {
                    "status": "success",
                    "elements_processed": elements_processed,
                    "embeddings_created": embeddings_created,
                    "chunking_strategy": "element_based"
                }
            else:
                logger.warning(f"Vector service returned {response.get('status_code')}: {response}")
                return {
                    "status": "error",
                    "message": f"Vector service error: {response.get('status_code')}"
                }
                    
        except Exception as e:
            logger.error(f"Enhanced vector integration failed: {e}")
            return {
                "status": "error", 
                "message": f"Vector integration error: {str(e)}"
            }
    
    async def _integrate_graph_service(
        self,
        project_id: str,
        processing_result: ProcessingResult,
        correlation_id: str
    ) -> Dict[str, Any]:
        """
        Step 5: Entity & Relationship Extraction Integration
        Send structured content to Graph Service for entity extraction
        """
        logger.info(f"=== GRAPH INTEGRATION START === [corr_id={correlation_id}]")
        logger.info(f"Graph integration check: enabled={self.enable_graph_integration}, url={self.graph_url}")
        
        if not self.enable_graph_integration:
            logger.warning("Graph integration is DISABLED by configuration")
            return {"status": "disabled", "message": "Graph integration disabled"}
        
        try:
            logger.info(f"Processing {len(processing_result.elements)} elements for graph service integration")
            
            # Prepare structured content for graph processing
            # Use ALL content elements, not just specific types - let LLM decide what's useful
            content_elements = []
            logger.info(f"Examining {len(processing_result.elements)} elements for graph processing")
            
            for element in processing_result.elements:
                # Include ALL elements with meaningful content for LLM-based entity extraction
                if element.text and len(element.text.strip()) > 5:  # Lower threshold
                    content_elements.append({
                        "element_id": element.element_id,
                        "content": element.text,
                        "element_type": element.type,
                        "page_number": element.page_number,
                        "hierarchy_level": element.hierarchy_level,
                        "metadata": element.metadata
                    })
                    logger.debug(f"Added element {element.element_id} ({element.type}) to graph processing")
                else:
                    logger.debug(f"Skipped element {element.element_id} - text too short or empty")
            
            logger.info(f"Prepared {len(content_elements)} elements for graph service")
            
            if not content_elements:
                logger.warning("No suitable elements found for entity extraction")
                return {"status": "skipped", "message": "No suitable elements for entity extraction"}
            
            # Send to Graph Service for processing
            logger.info(f"Calling graph service for project {project_id}")

            client = await get_service_client()
            payload = {
                "document_id": str(uuid.uuid4()),
                "filename": processing_result.document_metadata.filename,
                "structured_elements": content_elements,
                "processing_type": "structured_extraction",
                "extract_entities": True,
                "extract_relationships": True
            }

            headers = {
                "X-Correlation-ID": correlation_id
            }

            logger.info(f"Sending {len(content_elements)} elements to graph service")

            # Add retry logic for graph service calls
            max_retries = 3
            retry_delay = 5  # seconds

            for attempt in range(max_retries):
                try:
                    logger.info(f"Graph service call attempt {attempt + 1}/{max_retries}")

                    response = await client.post(
                        "graph",
                        f"/api/graphs/projects/{project_id}/process-structured",
                        json=payload,
                        headers=headers
                    )

                    logger.info(f"Graph service response: {response.get('status_code')}")

                    if response.get("status_code") == 200:
                        result = response
                        entities_extracted = result.get("entities_extracted", 0)
                        relationships_found = result.get("relationships_found", 0)
                        logger.info(f"🎉 Graph integration successful: {len(content_elements)} elements analyzed, {entities_extracted} entities, {relationships_found} relationships")
                        return {
                            "status": "success",
                            "elements_analyzed": len(content_elements),
                            "entities_extracted": entities_extracted,
                            "relationships_found": relationships_found
                        }
                    else:
                        error_text = str(response)[:500]
                        logger.error(f"❌ Graph service returned {response.get('status_code')}: {error_text}")
                        logger.error(f"Request URL: graph service /api/graphs/projects/{project_id}/process-structured")
                        logger.error(f"Request payload size: {len(json.dumps(payload))} bytes")

                        # Don't retry on client errors (4xx)
                        if 400 <= response.get("status_code", 500) < 500:
                            return {
                                "status": "error",
                                "message": f"Graph service client error: {response.get('status_code')} - {error_text[:200]}"
                            }

                        # Retry on server errors (5xx) or other issues
                        if attempt < max_retries - 1:
                            logger.warning(f"Retrying graph service call in {retry_delay} seconds...")
                            await asyncio.sleep(retry_delay)
                            continue
                        else:
                            return {
                                "status": "error",
                                "message": f"Graph service error after {max_retries} attempts: {response.get('status_code')} - {error_text[:200]}"
                            }

                except Exception as e:
                    logger.error(f"Graph service call failed on attempt {attempt + 1}: {e}")
                    if attempt < max_retries - 1:
                        logger.info(f"Retrying graph service call in {retry_delay} seconds...")
                        await asyncio.sleep(retry_delay)
                        continue
                    else:
                        return {
                            "status": "error",
                            "message": f"Graph service error after {max_retries} attempts: {str(e)}"
                        }
                    
        except Exception as e:
            logger.error(f"Graph integration failed with exception: {type(e).__name__}: {e}")
            import traceback
            logger.error(f"Graph integration traceback: {traceback.format_exc()}")
            return {"status": "error", "message": str(e)}
    
    async def _notify_stats_service(
        self,
        project_id: str,
        vector_status: Dict[str, Any],
        graph_status: Dict[str, Any],
        correlation_id: str
    ):
        """
        Notify backend stats service of embeddings and graph updates
        Extracts counts from Vector and Graph service responses
        """
        try:
            # Notify embeddings added if vector integration was successful
            if vector_status.get("status") == "success":
                embeddings_count = vector_status.get("embeddings_created", 0)
                if embeddings_count > 0:
                    client = await get_service_client()
                    await client.post(
                        "backend",
                        "/api/stats/events",
                        json={
                            "project_id": project_id,
                            "event_type": "embeddings_added",
                            "additional_data": {
                                "embeddings_count": embeddings_count,
                                "source": "enhanced_workflow"
                            },
                            "timestamp": datetime.now().isoformat()
                        },
                        headers={"X-Correlation-ID": correlation_id}
                    )
                    logger.debug(f"Notified stats service: embeddings_added - {embeddings_count}")

            # Notify graph updated if graph integration was successful
            if graph_status.get("status") == "success":
                entities_extracted = graph_status.get("entities_extracted", 0)
                relationships_found = graph_status.get("relationships_found", 0)
                if entities_extracted > 0 or relationships_found > 0:
                    client = await get_service_client()
                    await client.post(
                        "backend",
                        "/api/stats/events",
                        json={
                            "project_id": project_id,
                            "event_type": "graph_updated",
                            "additional_data": {
                                "nodes": entities_extracted,
                                "relationships": relationships_found,
                                "source": "enhanced_workflow"
                            },
                            "timestamp": datetime.now().isoformat()
                        },
                        headers={"X-Correlation-ID": correlation_id}
                    )
                    logger.debug(f"Notified stats service: graph_updated - {entities_extracted} nodes, {relationships_found} relationships")

        except Exception as e:
            logger.debug(f"Failed to notify stats service (non-critical): {e}")

    async def _notify_batch_completion_stats(
        self,
        project_id: str,
        results: List[Dict[str, Any]],
        correlation_id: str
    ):
        """
        Aggregate stats from batch processing results and notify backend
        """
        try:
            # Aggregate stats from all successful results
            total_embeddings = 0
            total_entities = 0
            total_relationships = 0
            files_processed = 0

            for result in results:
                if result.get("status") == "success":
                    files_processed += 1

                    # Extract vector stats
                    vector_status = result.get("vector_integration", {})
                    if vector_status.get("status") == "success":
                        total_embeddings += vector_status.get("embeddings_created", 0)

                    # Extract graph stats
                    graph_status = result.get("graph_integration", {})
                    if graph_status.get("status") == "success":
                        total_entities += graph_status.get("entities_extracted", 0)
                        total_relationships += graph_status.get("relationships_found", 0)

            client = await get_service_client()

            # Notify aggregated embeddings
            if total_embeddings > 0:
                await client.post(
                    "backend",
                    "/api/stats/events",
                    json={
                        "project_id": project_id,
                        "event_type": "embeddings_added",
                        "additional_data": {
                            "embeddings_count": total_embeddings,
                            "source": "enhanced_batch_workflow",
                            "files_processed": files_processed
                        },
                        "timestamp": datetime.now().isoformat()
                    },
                    headers={"X-Correlation-ID": correlation_id}
                )
                logger.info(f"Notified batch embeddings: {total_embeddings} from {files_processed} files")

            # Notify aggregated graph updates
            if total_entities > 0 or total_relationships > 0:
                await client.post(
                    "backend",
                    "/api/stats/events",
                    json={
                        "project_id": project_id,
                        "event_type": "graph_updated",
                        "additional_data": {
                            "nodes": total_entities,
                            "relationships": total_relationships,
                            "source": "enhanced_batch_workflow",
                            "files_processed": files_processed
                        },
                        "timestamp": datetime.now().isoformat()
                    },
                    headers={"X-Correlation-ID": correlation_id}
                )
                logger.info(f"Notified batch graph updates: {total_entities} entities, {total_relationships} relationships from {files_processed} files")

        except Exception as e:
            logger.debug(f"Failed to notify batch stats (non-critical): {e}")

    async def _send_websocket_notification(
        self,
        project_id: str,
        correlation_id: str,
        event_type: str,
        data: Dict[str, Any]
    ):
        """
        Step 6: Real-time WebSocket Notifications
        Send progress updates via WebSocket Service
        """
        if not self.enable_websocket_notifications:
            return

        try:
            ws_client = await get_websocket_client()

            # Format message for WebSocket broadcast
            message = {
                "correlation_id": correlation_id,
                "event_type": event_type,
                "timestamp": datetime.now().isoformat(),
                "data": data
            }

            # Use appropriate channel based on event type
            if "processing" in event_type.lower():
                await ws_client.send_document_processing_update(
                    project_id, data.get("filename", "unknown"), "in_progress", message=event_type
                )
            elif "progress" in event_type.lower():
                await ws_client.send_processing_update(project_id, "unknown", message)
            else:
                await ws_client.send_processing_update(project_id, event_type, message)

            logger.debug(f"WebSocket notification sent: {event_type}")

        except Exception as e:
            logger.debug(f"WebSocket notification error (non-critical): {e}")
    
    async def process_batch_enhanced(
        self,
        project_id: str,
        filenames: List[str],
        correlation_id: Optional[str] = None,
        processing_options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process multiple documents with enhanced workflow
        Includes progress tracking and batch optimization
        """
        if not correlation_id:
            correlation_id = str(uuid.uuid4())
        
        options = processing_options or {}
        extract_images = options.get("extract_images", True)
        extract_tables = options.get("extract_tables", True)
        include_coordinates = options.get("include_coordinates", True)
        
        logger.info(f"Starting enhanced batch processing: {len(filenames)} files [corr_id={correlation_id}]")
        
        # Start batch progress tracking
        batch_event_id = await self.progress_tracker.start_operation(
            project_id, correlation_id, f"Batch Process {len(filenames)} files", len(filenames) + 2
        )
        
        # Send batch started notification
        await self.progress_tracker.update_operation_progress(
            batch_event_id, "Initializing batch processing...", 1
        )
        
        await self._send_websocket_notification(
            project_id, correlation_id, "batch_processing_started",
            {"total_files": len(filenames), "filenames": filenames}
        )
        
        results = []
        processed_count = 0
        failed_count = 0
        
        for i, filename in enumerate(filenames):
            try:
                # Download file from Storage Service
                file_path = await self._download_file_for_processing(project_id, filename, correlation_id)
                
                # Send file processing started notification
                await self.progress_tracker.update_operation_progress(
                    batch_event_id, f"Processing {filename} ({i+1}/{len(filenames)})...", i + 2
                )
                
                await self._send_websocket_notification(
                    project_id, correlation_id, "file_processing_started",
                    {
                        "filename": filename,
                        "progress": f"{i+1}/{len(filenames)}",
                        "percentage": round((i / len(filenames)) * 100, 1)
                    }
                )
                
                # Process with enhanced workflow (which now includes LLM analysis)
                result = await self.process_document_enhanced(
                    file_path=file_path,
                    filename=filename,
                    project_id=project_id,
                    correlation_id=correlation_id,
                    extract_images=extract_images,
                    extract_tables=extract_tables,
                    include_coordinates=include_coordinates
                )

                # LLM analysis is now integrated into process_document_enhanced
                # The result will include llm_analysis field if successful
                
                if result["status"] == "success":
                    processed_count += 1
                else:
                    failed_count += 1
                
                results.append(result)
                
                # Clean up temp file
                if os.path.exists(file_path):
                    os.unlink(file_path)
                    
            except Exception as e:
                logger.error(f"Error processing {filename}: {e}")
                failed_count += 1
                results.append({
                    "status": "error",
                    "filename": filename,
                    "error": str(e),
                    "correlation_id": correlation_id
                })
        
        # Send batch completed notification
        await self.progress_tracker.update_operation_progress(
            batch_event_id, "Finalizing batch processing...", len(filenames) + 2
        )
        
        await self._send_websocket_notification(
            project_id, correlation_id, "batch_processing_completed",
            {
                "total_files": len(filenames),
                "processed_count": processed_count,
                "failed_count": failed_count,
                "success_rate": round((processed_count / len(filenames)) * 100, 1) if filenames else 0
            }
        )
        
        # Aggregate and notify stats for successful batch processing
        if processed_count > 0:
            await self._notify_batch_completion_stats(
                project_id, results, correlation_id
            )
        
        await self.progress_tracker.complete_operation(batch_event_id, True)
        
        logger.info(f"Enhanced batch processing completed: {processed_count} success, {failed_count} failed")
        
        return {
            "status": "completed",
            "total_files": len(filenames),
            "processed_count": processed_count,
            "failed_count": failed_count,
            "results": results,
            "correlation_id": correlation_id
        }
    
    async def _download_file_for_processing(
        self,
        project_id: str,
        filename: str,
        correlation_id: str
    ) -> str:
        """Download file from Storage Service for processing"""
        try:
            client = await get_service_client()

            # Download file from storage service
            response = await client.get(
                "storage",
                f"/api/storage/projects/{project_id}/download/uploads_raw/{filename}",
                headers={"X-Correlation-ID": correlation_id}
            )

            if response.get("status_code") != 200:
                raise Exception(f"Failed to download file from storage: {response.get('status_code')}")

            # Save to temporary file
            suffix = Path(filename).suffix
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                tmp_file.write(response.get("content", b""))
                temp_path = tmp_file.name

            logger.info(f"File downloaded to temporary location: {temp_path}")
            return temp_path

        except Exception as e:
            logger.error(f"Error downloading file {filename}: {e}")
            raise
    
    async def _integrate_llm_analysis(
        self,
        project_id: str,
        processing_result: ProcessingResult,
        correlation_id: str
    ) -> Dict[str, Any]:
        """
        Step 3.5: LLM Analysis Integration
        Perform comprehensive LLM analysis on the processed document
        """
        if not self.llm_analyzer:
            return {"status": "disabled", "message": "LLM analyzer not available"}

        try:
            # Extract text content from processing result for LLM analysis
            document_content = self._extract_document_content(processing_result)

            if not document_content or len(document_content.strip()) < 100:
                return {"status": "skipped", "message": "Insufficient content for LLM analysis"}

            # Perform LLM analysis
            analysis_result = await self.llm_analyzer.analyze_document_content(
                project_id=project_id,
                filename=processing_result.document_metadata.filename,
                processed_content=document_content,
                structured_result=processing_result,
                analysis_type="comprehensive",
                correlation_id=correlation_id
            )

            if analysis_result["status"] == "success":
                # Extract LLM metadata for tracking
                llm_metadata = {
                    "llm_summary": analysis_result.get("final_summary", ""),
                    "llm_categories": analysis_result.get("final_categories", []),
                    "quality_score": analysis_result.get("quality_score", 0.0),
                    "processing_methods": analysis_result.get("processing_methods", []),
                    "processing_time": analysis_result.get("total_processing_time", 0.0),
                    "llm_cached": analysis_result.get("llm_summary_cached", False),
                    "token_usage": analysis_result.get("token_usage", {}),
                    "confidence_score": analysis_result.get("quality_score", 0.0)
                }

                logger.info(f"LLM analysis successful: quality={llm_metadata['quality_score']:.2f}, cached={llm_metadata['llm_cached']}")
                return {
                    "status": "success",
                    "metadata": llm_metadata,
                    "full_result": analysis_result
                }
            else:
                logger.warning(f"LLM analysis failed: {analysis_result.get('error', 'Unknown error')}")
                return {
                    "status": "error",
                    "message": analysis_result.get("error", "LLM analysis failed")
                }

        except Exception as e:
            logger.error(f"LLM analysis integration failed: {e}")
            return {
                "status": "error",
                "message": f"LLM integration error: {str(e)}"
            }

    def _extract_document_content(self, processing_result: ProcessingResult) -> str:
        """Extract readable text content from processing result for LLM analysis"""
        content_parts = []

        for element in processing_result.elements:
            # Include narrative text, titles, and other readable content
            if element.type in ['title', 'narrative_text', 'list_item', 'header', 'paragraph'] and element.text.strip():
                content_parts.append(element.text)

        return '\n\n'.join(content_parts)

    async def _store_analysis_result(
        self,
        analysis_result: Dict[str, Any],
        correlation_id: str
    ):
        """
        Store comprehensive analysis result in analysis_results table
        """
        try:
            # Prepare analysis data for database storage
            analysis_data = {
                "batch_id": correlation_id,
                "document_filename": analysis_result["filename"],
                "project_id": analysis_result.get("project_id", ""),
                "analysis_type": "comprehensive",
                "status": analysis_result["status"],
                "processing_time_seconds": analysis_result["processing_time"],
                "elements_extracted": analysis_result["elements_extracted"],
                "element_types": analysis_result["element_types"],
                "structured_output_path": analysis_result.get("structured_output", ""),
                "vector_integration_status": analysis_result["vector_integration"]["status"] if analysis_result.get("vector_integration") else "disabled",
                "graph_integration_status": analysis_result["graph_integration"]["status"] if analysis_result.get("graph_integration") else "disabled",
                "llm_analysis_status": analysis_result["llm_analysis"]["status"] if analysis_result.get("llm_analysis") else "disabled",
                "correlation_id": correlation_id,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }

            # Add LLM-specific metadata if available
            if analysis_result.get("llm_analysis") and analysis_result["llm_analysis"]["status"] == "success":
                llm_meta = analysis_result["llm_analysis"]["metadata"]
                analysis_data.update({
                    "llm_summary": llm_meta.get("llm_summary", ""),
                    "llm_categories": json.dumps(llm_meta.get("llm_categories", [])),
                    "quality_score": llm_meta.get("quality_score", 0.0),
                    "confidence_score": llm_meta.get("confidence_score", 0.0),
                    "token_usage": json.dumps(llm_meta.get("token_usage", {})),
                    "llm_processing_time": llm_meta.get("processing_time", 0.0)
                })

            # Store in database (using HTTP call to backend service)
            await self._store_in_database(analysis_data, correlation_id)

            logger.info(f"Analysis result stored for {analysis_result['filename']}")

        except Exception as e:
            logger.error(f"Failed to store analysis result: {e}")
            # Don't fail the entire process if database storage fails

    async def _store_in_database(self, analysis_data: Dict[str, Any], correlation_id: str):
        """Store analysis data in the analysis_results table via backend service"""
        try:
            client = await get_service_client()

            response = await client.post(
                "backend",
                "/api/analysis/results",
                json=analysis_data,
                headers={"X-Correlation-ID": correlation_id}
            )

            if response.get("status_code") not in [200, 201]:
                logger.warning(f"Database storage returned {response.get('status_code')}: {response}")
            else:
                logger.debug("Analysis result stored in database successfully")

        except Exception as e:
            logger.warning(f"Database storage failed (non-critical): {e}")

    def get_integration_status(self) -> Dict[str, Any]:
        """Get current integration configuration status"""
        return {
            "vector_integration": self.enable_vector_integration,
            "graph_integration": self.enable_graph_integration,
            "websocket_notifications": self.enable_websocket_notifications,
            "llm_analysis": self.enable_llm_analysis,
            "llm_analyzer_available": self.llm_analyzer is not None,
            "service_urls": {
                "vector_service": self.vector_url,
                "graph_service": self.graph_url,
                "websocket_service": self.websocket_url,
                "storage_service": self.storage_url,
                "database_service": self.database_url
            }
        }
