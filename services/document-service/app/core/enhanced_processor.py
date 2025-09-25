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
import time

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
        # Phase 2/3 flags for cards pipeline
        self.enable_cards = os.getenv("ENABLE_CARDS_PIPELINE", "true").lower() == "true"
    # Layout JSONL flag (A2)
    self.enable_layout_jsonl = os.getenv("LAYOUT_JSONL_ENABLED", "true").lower() in ("1","true","yes","on")

        # Force-enable graph integration for debugging if disabled
        if not self.enable_graph_integration:
            logger.warning("Graph integration was disabled, FORCE ENABLING for debugging!")
            self.enable_graph_integration = True

        logger.info(f"Enhanced Processor Configuration: vector={self.enable_vector_integration}, graph={self.enable_graph_integration}, websocket={self.enable_websocket_notifications}, llm={self.enable_llm_analysis}")

        # Performance optimization
        self.max_concurrent_integrations = int(os.getenv("MAX_CONCURRENT_INTEGRATIONS", "2"))
        self.enable_parallel_processing = os.getenv("ENABLE_PARALLEL_PROCESSING", "true").lower() == "true"

        # Kind-aware vectors (multi-embedding collections)
        # When set, embeddings will be tagged with this kind in the 'source' field
        # Allowed values are aligned with vector-service KIND_VALUES
        self.vectors_kind_allowed = {"raw_chunks", "entity_cards", "triple_cards"}
        self.vectors_kind = os.getenv("VECTORS_USE_KIND")
        if self.vectors_kind and self.vectors_kind not in self.vectors_kind_allowed:
            logger.warning(
                f"VECTORS_USE_KIND='{self.vectors_kind}' is invalid. Allowed: {sorted(self.vectors_kind_allowed)}. Ignoring."
            )
            self.vectors_kind = None

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
                {
                    "filename": filename,
                    "stage": "conversion_structuring",
                    "progress": 10,
                    "message": f"Starting document processing for {filename}",
                    "details": "Analyzing document structure and extracting content"
                }
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
            
            # Initialize LLM analysis result
            llm_analysis_result = None
            
            # Save structured JSONL output to Storage Service
            base_name = os.path.splitext(filename)[0]
            structured_filename = f"{base_name}_structured.jsonl"
            layout_filename = f"{base_name}_layout.jsonl" if self.enable_layout_jsonl else None

            await self.progress_tracker.update_operation_progress(
                event_id, "Saving structured output...", 2
            )

            await self._send_websocket_notification(
                project_id, correlation_id, "document_processing_progress",
                {
                    "filename": filename,
                    "stage": "saving_output",
                    "progress": 25,
                    "message": f"Saving structured content for {filename}",
                    "details": f"Processed {len(processing_result.elements)} elements, saving to storage"
                }
            )

            await self._save_structured_output(
                project_id, structured_filename, processing_result, correlation_id, llm_analysis_result
            )
            # Generate & save layout JSONL (A2)
            if self.enable_layout_jsonl:
                try:
                    mineru_used = bool(getattr(self.structured_processor._mineru, 'is_enabled', lambda: False)())
                    layout_content = self.structured_processor.generate_layout_jsonl(processing_result, mineru_used=mineru_used)
                    await self._save_layout_output(project_id, layout_filename, layout_content, correlation_id)
                except Exception as le:
                    logger.warning(f"Layout JSONL generation failed (non-fatal): {le}")
            
            logger.info(f"Structured processing completed: {len(processing_result.elements)} elements extracted")

            # Step 3.5: LLM Analysis Integration (if enabled)
            if self.enable_llm_analysis and self.llm_analyzer:
                await self.progress_tracker.update_operation_progress(
                    event_id, "Performing LLM analysis...", 3
                )

                await self._send_websocket_notification(
                    project_id, correlation_id, "document_processing_progress",
                    {
                        "filename": filename,
                        "stage": "llm_analysis",
                        "progress": 30,
                        "message": f"Performing AI analysis on {filename}",
                        "details": "Using advanced language models to understand document content and context"
                    }
                )

                llm_analysis_result = await self._integrate_llm_analysis(
                    project_id, processing_result, correlation_id
                )

                logger.info(f"LLM analysis completed for {filename}")

                # Update structured output with LLM analysis if it was successful
                if llm_analysis_result and llm_analysis_result.get("status") == "success":
                    await self._save_structured_output(
                        project_id, structured_filename, processing_result, correlation_id, llm_analysis_result
                    )

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

                # Optional: entity/triple cards vector upsert
                if self.enable_cards and self.enable_vector_integration:
                    integration_tasks.append(self._integrate_cards_vectors(
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
                        {
                            "filename": filename,
                            "stage": "starting_integration",
                            "progress": 40,
                            "message": f"Starting service integrations for {filename}",
                            "details": "Connecting to vector database and knowledge graph services"
                        }
                    )

                    integration_results = await asyncio.gather(*integration_tasks, return_exceptions=True)
                    logger.info(f"Parallel integration completed with {len(integration_results)} results")

                    await self._send_websocket_notification(
                        project_id, correlation_id, "document_processing_progress",
                        {
                            "filename": filename,
                            "stage": "integration_completed",
                            "progress": 75,
                            "message": f"Service integrations completed for {filename}",
                            "details": "Vector embeddings and knowledge graph updates finished successfully"
                        }
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

                    # If cards upsert task was scheduled, consume and log it to keep indices aligned
                    if self.enable_cards and self.enable_vector_integration:
                        cards_result = None
                        try:
                            cards_result = integration_results[result_index]
                        except Exception:
                            cards_result = None
                        if isinstance(cards_result, Exception):
                            logger.debug(f"Cards vector upsert failed: {cards_result}")
                        elif isinstance(cards_result, dict):
                            logger.info(f"Cards vector upsert status: {cards_result.get('status')}")
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
                        elif graph_result is None:
                            logger.warning("Graph integration returned None - treating as error")
                            graph_status = {"status": "error", "message": "Graph service returned None"}
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
                    # Cards upsert (sequential)
                    if self.enable_cards and vector_status.get("status") == "success":
                        try:
                            await self._integrate_cards_vectors(project_id, processing_result, correlation_id)
                        except Exception as _cards_err:
                            logger.debug(f"Cards vector upsert skipped: {_cards_err}")
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
                {
                    "filename": filename,
                    "stage": "updating_stats",
                    "progress": 80,
                    "message": f"Updating project statistics for {filename}",
                    "details": "Recording processing metrics and updating project analytics"
                }
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
                {
                    "filename": filename,
                    "stage": "finalizing",
                    "progress": 95,
                    "message": f"Finalizing processing for {filename}",
                    "details": "Sending completion notifications and preparing results"
                }
            )

            # Generate analysis_id for the completed document
            analysis_id = str(uuid.uuid4())

            await self._send_websocket_notification(
                project_id, correlation_id, "document_processing_completed",
                {
                    "filename": filename,
                    "analysis_id": analysis_id,
                    "structured_output": structured_filename,
                    "elements_extracted": len(processing_result.elements),
                    "vector_integration": vector_status,
                    "graph_integration": graph_status,
                    "processing_time": processing_result.processing_stats.get("processing_time_seconds", 0),
                    "progress": 100,
                    "message": f"Document processing completed successfully for {filename}",
                    "details": f"Extracted {len(processing_result.elements)} elements, analysis ready for viewing",
                    "analysis_status": "analysis_complete"
                }
            )
            
            await self.progress_tracker.complete_operation(event_id, True)
            
            # Prepare comprehensive analysis result
            analysis_result = {
                "status": "success",
                "filename": filename,
                "structured_output": structured_filename,
                "layout_output": layout_filename if layout_filename and self.enable_layout_jsonl else None,
                "elements_extracted": len(processing_result.elements),
                "element_types": processing_result.processing_stats.get("element_types", {}),
                "processing_time": processing_result.processing_stats.get("processing_time_seconds", 0),
                "vector_integration": vector_status,
                "graph_integration": graph_status,
                "llm_analysis": llm_analysis_result,
                "correlation_id": correlation_id,
                "processing_result": processing_result.to_dict()  # Convert to dict for JSON serialization
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

    def _generate_entity_cards(self, processing_result: ProcessingResult) -> List[Dict[str, Any]]:
        """Derive lightweight entity cards from structured elements using simple heuristics."""
        cards = []
        seen = set()
        try:
            for elem in processing_result.elements:
                t = (elem.type or "").lower()
                text = (elem.text or "").strip()
                if not text or len(text) < 3:
                    continue
                # Heuristic: titles and list items likely denote entities/topics
                if t in ("title", "header", "list_item"):
                    key = text.lower()[:200]
                    if key in seen:
                        continue
                    seen.add(key)
                    cards.append({
                        "content": text,
                        "filename": processing_result.document_metadata.filename,
                        "source": "entity_cards",
                        "chunk_index": elem.hierarchy_level or 0,
                    })
        except Exception as e:
            logger.debug(f"Entity cards generation skipped: {e}")
        return cards

    def _generate_triple_cards(self, processing_result: ProcessingResult) -> List[Dict[str, Any]]:
        """Create simple subject-verb-object triples from sentences as relationship hints."""
        cards = []
        try:
            import re
            sentence_split = re.split(r"(?<=[.!?])\s+", "\n".join([e.text for e in processing_result.elements if (e.text or "").strip()]))
            for i, sent in enumerate(sentence_split[:200]):
                s = sent.strip()
                if len(s) < 20:
                    continue
                # Very naive pattern: "X is Y", "X has Y"
                m = re.search(r"^(?P<src>[A-Z][\w\s-]{2,})\s+(is|has|includes|requires)\s+(?P<dst>[A-Z][\w\s-]{2,})", s)
                if not m:
                    continue
                src = m.group("src").strip()
                dst = m.group("dst").strip()
                rel = m.group(2)
                cards.append({
                    "content": f"{src} --{rel}--> {dst}",
                    "filename": processing_result.document_metadata.filename,
                    "source": "triple_cards",
                    "chunk_index": i,
                })
        except Exception as e:
            logger.debug(f"Triple cards generation skipped: {e}")
        return cards

    async def _integrate_cards_vectors(self, project_id: str, processing_result: ProcessingResult, correlation_id: str) -> Dict[str, Any]:
        """Upsert generated entity/triple cards into per-kind vector views when enabled."""
        try:
            client = await get_service_client()
            headers = {"X-Correlation-ID": correlation_id} if correlation_id else {}

            entity_docs = self._generate_entity_cards(processing_result)
            triple_docs = self._generate_triple_cards(processing_result)

            added_total = 0
            for kind, docs in (("entity_cards", entity_docs), ("triple_cards", triple_docs)):
                if not docs:
                    continue
                # Ensure kind collection
                try:
                    await client.post("vector", f"/api/vectors/projects/{project_id}/collections/{kind}", headers=headers)
                except Exception:
                    pass
                payload = {"documents": docs}
                resp = await client.post(
                    "vector",
                    f"/api/vectors/projects/{project_id}/collections/{kind}/documents/sync",
                    json=payload,
                    headers=headers,
                )
                if resp.get("status_code") in (200, 201):
                    added = resp.get("documents_added") or resp.get("added_count") or len(docs)
                    added_total += int(added)
                    logger.info(f"Upserted {added} docs to kind={kind}")
                else:
                    logger.warning(f"Cards upsert for kind={kind} failed: HTTP {resp.get('status_code')}")

            return {"status": "success", "cards_added": added_total}
        except Exception as e:
            logger.debug(f"Cards vectors integration error: {e}")
            return {"status": "error", "message": str(e)}

    def get_integration_status(self) -> Dict[str, Any]:
        """Lightweight snapshot of integration feature flags for UI/diagnostics."""
        try:
            return {
                "vector_enabled": bool(self.enable_vector_integration),
                "graph_enabled": bool(self.enable_graph_integration),
                "websocket_enabled": bool(self.enable_websocket_notifications),
                "llm_analysis_enabled": bool(self.enable_llm_analysis),
                "cards_pipeline_enabled": bool(getattr(self, 'enable_cards', False)),
            }
        except Exception:
            return {
                "vector_enabled": False,
                "graph_enabled": False,
                "websocket_enabled": False,
                "llm_analysis_enabled": False,
                "cards_pipeline_enabled": False,
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
            # Upload to Storage Service structured folder using proper multipart form data
            files_data = {
                'files': (filename, jsonl_content.encode('utf-8'), 'application/jsonl')
            }

            headers = {}
            if correlation_id:
                headers["X-Correlation-ID"] = correlation_id

            response = await client.post(
                "storage",
                f"/api/storage/projects/{project_id}/upload/structured",
                files=files_data,
                headers=headers
            )

            # If we reach here, the request was successful (no exception raised)
            logger.info(f"Saved structured output with LLM analysis: {filename}")
            return {"status": "success"}

        except Exception as e:
            logger.error(f"Error saving structured output: {e}")
            # Don't fail the entire process if structured storage fails
            # This allows the document to still be processed successfully
            return {"status": "error", "message": str(e)}

    async def _save_layout_output(
        self,
        project_id: str,
        filename: Optional[str],
        layout_content: str,
        correlation_id: str
    ) -> Dict[str, Any]:
        """Save layout JSONL output (A2) to Storage Service."""
        if not filename:
            return {"status": "skipped", "message": "No filename provided"}
        try:
            client = await get_service_client()
            files_data = {'files': (filename, layout_content.encode('utf-8'), 'application/jsonl')}
            headers = {"X-Correlation-ID": correlation_id} if correlation_id else {}
            response = await client.post(
                "storage",
                f"/api/storage/projects/{project_id}/upload/structured",
                files=files_data,
                headers=headers
            )
            if response.get("status_code") in (200,201):
                logger.info(f"Saved layout JSONL output: {filename}")
                return {"status": "success"}
            logger.warning(f"Layout upload failed HTTP {response.get('status_code')}")
            return {"status": "error", "message": f"HTTP {response.get('status_code')}"}
        except Exception as e:
            logger.warning(f"Layout output save failed (non-fatal): {e}")
            return {"status": "error", "message": str(e)}
    
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
            
            # Determine the source (kind-aware if configured)
            source_value = "enhanced_document_processor_v2"
            if self.vectors_kind:
                source_value = self.vectors_kind
                # Best-effort: ensure the per-kind view is initialized (non-fatal if it fails)
                try:
                    client = await get_service_client()
                    await client.post(
                        "vector",
                        f"/api/vectors/projects/{project_id}/collections/{self.vectors_kind}",
                        headers={"X-Correlation-ID": correlation_id} if correlation_id else {}
                    )
                    logger.info(
                        f"Ensured kind collection for project={project_id}, kind={self.vectors_kind}"
                    )
                except Exception as e:
                    logger.debug(f"Kind collection ensure skipped/failed: {e}")

            # Build AddDocumentsRequest payload for per-kind or generic ingestion
            client = await get_service_client()
            headers = {"X-Correlation-ID": correlation_id} if correlation_id else {}

            # Map elements to DocumentInput shape (content, filename, source, chunk_index)
            base_filename = processing_result.document_metadata.filename or "unknown"
            documents_payload = []
            for idx, doc in enumerate(structured_documents):
                # Prefer explicit metadata filename if provided
                meta = doc.get("metadata") or {}
                fname = meta.get("filename") or base_filename
                documents_payload.append({
                    "content": doc.get("content", ""),
                    "filename": fname,
                    "source": source_value,
                    "chunk_index": int(doc.get("hierarchy_level") or idx),
                })

            # Prefer per-kind endpoint when vectors_kind is configured
            if self.vectors_kind:
                # Ensure kind view (best-effort already attempted above)
                try:
                    await client.post(
                        "vector",
                        f"/api/vectors/projects/{project_id}/collections/{self.vectors_kind}",
                        headers=headers,
                    )
                except Exception:
                    pass

                response = await client.post(
                    "vector",
                    f"/api/vectors/projects/{project_id}/collections/{self.vectors_kind}/documents/sync",
                    json={"documents": documents_payload},
                    headers=headers,
                )

                if response.get("status_code") in (200, 201):
                    result = response
                    added = result.get("documents_added") or result.get("added_count") or len(documents_payload)
                    logger.info(
                        f"Per-kind vector upsert successful: kind={self.vectors_kind} added={added}"
                    )
                    return {
                        "status": "success",
                        "elements_processed": len(structured_documents),
                        "embeddings_created": int(added),
                        "chunking_strategy": "element_based",
                    }
                else:
                    logger.warning(
                        f"Per-kind vector upsert failed: HTTP {response.get('status_code')} - falling back to process-structured"
                    )

            # Fallback: legacy structured processing endpoint
            response = await client.post(
                "vector",
                f"/api/vectors/projects/{project_id}/process-structured",
                json={
                    "documents": structured_documents,
                    "processing_type": "structured",
                    "chunking_strategy": "element_based",
                    "source": source_value,
                },
                headers=headers,
            )

            if response.get("status_code") == 200:
                result = response
                embeddings_created = result.get("embeddings_created", 0)
                elements_processed = result.get("elements_processed", len(structured_documents))
                logger.info(
                    f"Enhanced vector integration successful (fallback): {elements_processed} elements processed, {embeddings_created} embeddings created"
                )
                return {
                    "status": "success",
                    "elements_processed": elements_processed,
                    "embeddings_created": embeddings_created,
                    "chunking_strategy": "element_based",
                }
            else:
                logger.warning(f"Vector service returned status {response.get('status_code')}")
                return {"status": "error", "message": f"Vector service error: {response.get('status_code')}"}
                    
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
        Step 5: Entity & Relationship Extraction Integration with Enhanced Timeout & Retry Logic
        Send structured content to Graph Service for entity extraction
        """
        logger.info(f"=== GRAPH INTEGRATION START === [corr_id={correlation_id}]")
        logger.info(f"Graph integration check: enabled={self.enable_graph_integration}, url={self.graph_url}")

        if not self.enable_graph_integration:
            logger.warning("Graph integration is DISABLED by configuration")
            return {"status": "disabled", "message": "Graph integration disabled"}

        # Enhanced timeout and retry configuration
        max_retries = 3
        base_timeout = 90.0  # Start with 90 seconds
        max_timeout = 180.0  # Maximum timeout
        retry_delays = [2, 5, 10]  # Exponential backoff delays

        try:
            logger.info(f"Processing {len(processing_result.elements)} elements for graph service integration")

            # Prepare structured content for graph processing by READING JSONL from storage
            # This enforces that graph-service uses the JSONL output (not the original CSV)
            content_elements = []
            structured_filename = f"{os.path.splitext(processing_result.document_metadata.filename)[0]}_structured.jsonl"

            try:
                client = await get_service_client()
                headers = {"X-Correlation-ID": correlation_id} if correlation_id else {}
                resp = await client.get(
                    "storage",
                    f"/api/storage/projects/{project_id}/download/structured/{structured_filename}",
                    headers=headers
                )

                if resp.get("status_code") == 200:
                    jsonl_text = resp.get("text") or resp.get("content") or ""
                    # content could be bytes; ensure str
                    if isinstance(jsonl_text, (bytes, bytearray)):
                        try:
                            jsonl_text = jsonl_text.decode("utf-8", errors="ignore")
                        except Exception:
                            jsonl_text = str(jsonl_text)

                    parsed = 0
                    for line in (jsonl_text or "").split("\n"):
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                        except Exception:
                            continue
                        if data.get("type") != "element":
                            continue
                        elem = data.get("data", {})
                        text = (elem.get("text") or "").strip()
                        if len(text) <= 5:
                            continue
                        # Normalize element_type to lowercase for downstream filters
                        content_elements.append({
                            "element_id": elem.get("element_id"),
                            "content": text,
                            "element_type": (elem.get("type") or elem.get("element_type") or "unknown").lower(),
                            "page_number": elem.get("page_number"),
                            "hierarchy_level": elem.get("hierarchy_level"),
                            "metadata": elem.get("metadata") or {}
                        })
                        parsed += 1
                    logger.info(f"Prepared {len(content_elements)} elements from JSONL for graph service (parsed={parsed})")
                else:
                    logger.warning(f"Could not read structured JSONL from storage (HTTP {resp.get('status_code')}). Falling back to in-memory elements.")
            except Exception as e:
                logger.warning(f"Failed to load structured JSONL from storage: {e}. Falling back to in-memory elements.")

            # Fallback: in-memory structured elements from processing_result if JSONL not available
            if not content_elements:
                logger.info(f"Examining {len(processing_result.elements)} in-memory elements for graph processing (JSONL unavailable)")
                for element in processing_result.elements:
                    if element.text and len(element.text.strip()) > 5:
                        content_elements.append({
                            "element_id": element.element_id,
                            "content": element.text,
                            "element_type": (element.type or "unknown").lower(),
                            "page_number": element.page_number,
                            "hierarchy_level": element.hierarchy_level,
                            "metadata": element.metadata
                        })
                logger.info(f"Prepared {len(content_elements)} fallback elements for graph service")

            if not content_elements:
                logger.warning("No suitable elements found for entity extraction")
                return {"status": "skipped", "message": "No suitable elements for entity extraction"}

            # Send to Graph Service for processing with enhanced retry logic
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

            headers = {}
            if correlation_id:
                headers["X-Correlation-ID"] = correlation_id

            logger.info(f"Sending {len(content_elements)} elements to graph service")

            # Enhanced retry logic with progressive timeout increases
            last_exception = None

            for attempt in range(max_retries):
                try:
                    # Progressive timeout increase
                    current_timeout = min(base_timeout + (attempt * 30), max_timeout)
                    logger.info(f"Graph service call attempt {attempt + 1}/{max_retries} with {current_timeout}s timeout")

                    # Add timeout to headers for service-level timeout handling
                    request_headers = headers.copy()
                    request_headers["X-Timeout"] = str(int(current_timeout))

                    start_time = time.time()

                    response = await client.post(
                        "graph",
                        f"/api/graphs/projects/{project_id}/process-structured",
                        json=payload,
                        headers=request_headers,
                        timeout=current_timeout
                    )

                    processing_time = time.time() - start_time
                    logger.info(f"Graph service response: {response.get('status_code')} (took {processing_time:.2f}s)")

                    status_code = response.get("status_code")
                    if status_code == 200:
                        result = response
                        entities_extracted = result.get("entities_extracted", 0)
                        relationships_found = result.get("relationships_found", 0)
                        logger.info(f"🎉 Graph integration successful: {len(content_elements)} elements analyzed, {entities_extracted} entities, {relationships_found} relationships")
                        # After successful graph upsert, trigger facts extraction from the same structured elements
                        try:
                            facts_payload = {
                                "document_id": payload["document_id"],
                                "filename": processing_result.document_metadata.filename,
                                "structured_elements": content_elements,
                                "processing_type": "structured_extraction",
                                "extract_entities": False,
                                "extract_relationships": False
                            }
                            _ = await client.post(
                                "graph",
                                f"/api/graphs/projects/{project_id}/structured/facts",
                                json=facts_payload,
                                headers=request_headers,
                                timeout=60
                            )
                        except Exception as _facts_err:
                            logger.debug(f"Structured facts extraction post-step skipped: {_facts_err}")
                        return {
                            "status": "success",
                            "elements_analyzed": len(content_elements),
                            "entities_extracted": entities_extracted,
                            "relationships_found": relationships_found,
                            "processing_time": processing_time,
                            "attempts": attempt + 1
                        }

                    elif status_code == 429:  # Rate limited
                        logger.warning(f"Graph service rate limited (429) on attempt {attempt + 1}")
                        if attempt < max_retries - 1:
                            delay = retry_delays[attempt] * 2  # Extra delay for rate limits
                            logger.info(f"Waiting {delay} seconds before retry due to rate limit...")
                            await asyncio.sleep(delay)
                            continue

                    elif status_code and status_code >= 500:  # Server errors
                        logger.warning(f"Graph service server error ({status_code}) on attempt {attempt + 1}")
                        if attempt < max_retries - 1:
                            delay = retry_delays[attempt]
                            logger.info(f"Waiting {delay} seconds before retry due to server error...")
                            await asyncio.sleep(delay)
                            continue

                    else:
                        # Client errors (4xx) or unknown status - don't retry
                        status_text = str(status_code) if status_code else "None"
                        error_text = str(response)[:500]
                        logger.error(f"❌ Graph service client error ({status_text}): {error_text}")
                        return {
                            "status": "error",
                            "message": f"Graph service client error: {status_text} - {error_text[:200]}",
                            "attempts": attempt + 1
                        }

                except asyncio.TimeoutError:
                    last_exception = asyncio.TimeoutError(f"Graph service timeout after {current_timeout}s")
                    logger.warning(f"Graph service timeout on attempt {attempt + 1}: {last_exception}")
                    if attempt < max_retries - 1:
                        delay = retry_delays[attempt]
                        logger.info(f"Waiting {delay} seconds before retry due to timeout...")
                        await asyncio.sleep(delay)
                        continue

                except Exception as e:
                    last_exception = e
                    logger.error(f"Graph service call failed on attempt {attempt + 1}: {e}")
                    if attempt < max_retries - 1:
                        delay = retry_delays[attempt]
                        logger.info(f"Waiting {delay} seconds before retry due to error...")
                        await asyncio.sleep(delay)
                        continue

            # All retries exhausted
            error_msg = f"Graph service failed after {max_retries} attempts"
            if last_exception:
                error_msg += f": {str(last_exception)}"

            logger.error(f"❌ {error_msg}")
            return {
                "status": "error",
                "message": error_msg,
                "attempts": max_retries
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
                        headers={"X-Correlation-ID": correlation_id} if correlation_id else {}
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
                        headers={"X-Correlation-ID": correlation_id} if correlation_id else {}
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
                    headers={"X-Correlation-ID": correlation_id} if correlation_id else {}
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
                    headers={"X-Correlation-ID": correlation_id} if correlation_id else {}
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
            if event_type == "document_processing_completed":
                # Send completion message that will update analysis status
                await ws_client.send_document_processing_update(
                    project_id, data.get("filename", "unknown"), "completed",
                    message=f"Document processing completed: {data.get('message', 'Ready for analysis')}",
                    analysis_id=data.get("analysis_id"),
                    analysis_status="analysis_complete"
                )
            elif "processing" in event_type.lower():
                await ws_client.send_document_processing_update(
                    project_id, data.get("filename", "unknown"), "in_progress",
                    message=data.get("message", event_type)
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
                headers={"X-Correlation-ID": correlation_id} if correlation_id else {}
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
        Store analysis result in database via backend service
        """
        try:
            client = await get_service_client()
            
            # Ensure the payload matches the AnalysisResultCreate model exactly
            payload = {
                "status": analysis_result.get("status", "unknown"),
                "filename": analysis_result.get("filename", ""),
                "structured_output": analysis_result.get("structured_output"),
                "elements_extracted": analysis_result.get("elements_extracted", 0),
                "element_types": analysis_result.get("element_types", {}),
                "processing_time": analysis_result.get("processing_time", 0.0),
                "vector_integration": analysis_result.get("vector_integration"),
                "graph_integration": analysis_result.get("graph_integration"),
                "llm_analysis": analysis_result.get("llm_analysis"),
                "correlation_id": analysis_result.get("correlation_id"),
                "processing_result": analysis_result.get("processing_result")
            }
            
            # Ensure element_types is a dict with string keys and int values
            if payload["element_types"] and not isinstance(payload["element_types"], dict):
                payload["element_types"] = {}
            
            # Ensure processing_result is serializable
            if payload["processing_result"] and not isinstance(payload["processing_result"], dict):
                try:
                    # Try to convert to dict if it's an object
                    if hasattr(payload["processing_result"], 'to_dict'):
                        payload["processing_result"] = payload["processing_result"].to_dict()
                    else:
                        payload["processing_result"] = {}
                except Exception:
                    payload["processing_result"] = {}
            
            logger.info(f"Sending analysis result payload for {payload['filename']}")
            
            response = await client.post(
                "backend",
                "/api/documents/analysis/results",
                json=payload,
                headers={"X-Correlation-ID": correlation_id} if correlation_id else {}
            )
            
            if response.get("status_code") in [200, 201]:
                logger.info(f"Analysis result stored successfully in database")
                return {"status": "success"}
            else:
                logger.warning(f"Failed to store analysis result: {response.get('status_code')}")
                logger.warning(f"Response: {response}")
                return {"status": "error", "message": f"HTTP {response.get('status_code')}"}
                
        except Exception as e:
            logger.error(f"Database storage error: {e}")
            return {"status": "error", "message": str(e)}

    async def extract_entities_llm(
        self,
        project_id: str,
        filename: str,
        jsonl_content: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extract entities using LLM analysis from structured content
        This method is called by the processing pipeline for entity extraction
        """
        try:
            if not correlation_id:
                correlation_id = str(uuid.uuid4())

            logger.info(f"Starting LLM entity extraction for {filename} [corr_id={correlation_id}]")

            # If we have JSONL content, parse it to get structured elements
            if jsonl_content:
                try:
                    import json
                    elements = []
                    for line in jsonl_content.strip().split('\n'):
                        if line.strip():
                            data = json.loads(line)
                            if data.get('type') == 'element':
                                element_data = data.get('data', {})
                                elements.append({
                                    # Preserve original 'type' but also add canonical 'element_type' expected by graph service
                                    "type": element_data.get('type', 'unknown'),
                                    "element_type": element_data.get('type', 'unknown'),
                                    "content": element_data.get('text', ''),
                                    "metadata": element_data.get('metadata', {}),
                                    "page_number": element_data.get('page_number'),
                                    "element_id": element_data.get('element_id'),
                                    "hierarchy_level": element_data.get('hierarchy_level', 0),
                                    "semantic_tags": element_data.get('semantic_tags', []),
                                    "confidence_score": element_data.get('confidence_score', 0.8)
                                })

                    if elements:
                        # Use the graph service for entity extraction from structured elements
                        return await self._extract_entities_from_elements(
                            project_id, filename, elements, correlation_id
                        )
                except Exception as e:
                    logger.warning(f"Failed to parse JSONL content: {e}")

            # Fallback: Get content from storage and extract entities
            try:
                client = await get_service_client()

                # Try to get structured content first
                base_name = os.path.splitext(filename)[0]
                structured_filename = f"{base_name}_structured.jsonl"
                response = await client.get(
                    "storage",
                    f"/api/storage/projects/{project_id}/download/structured/{structured_filename}",
                    headers={"X-Correlation-ID": correlation_id} if correlation_id else {}
                )

                if response.get("status_code") == 200:
                    jsonl_content = response.get("text", "")
                    if jsonl_content.strip():
                        # Parse and extract entities
                        return await self._extract_entities_from_jsonl(
                            project_id, filename, jsonl_content, correlation_id
                        )
                    else:
                        logger.warning(f"Structured file exists but is empty: {structured_filename}")

                elif response.get("status_code") == 404:
                    logger.info(f"Structured file not found (404), trying other sources: {structured_filename}")
                else:
                    logger.warning(f"Failed to get structured content: HTTP {response.get('status_code')}")

                # Fallback 1: Try parsed markdown content
                response = await client.get(
                    "storage",
                    f"/api/storage/projects/{project_id}/download/uploads_parsed/{filename}",
                    headers={"X-Correlation-ID": correlation_id} if correlation_id else {}
                )

                if response.get("status_code") == 200:
                    content = response.get("text", "")
                    if content.strip():
                        return await self._extract_entities_from_text(
                            project_id, filename, content, correlation_id
                        )
                    else:
                        logger.warning(f"Parsed file exists but is empty: {filename}")

                elif response.get("status_code") == 404:
                    logger.info(f"Parsed file not found (404), trying original upload: {filename}")
                else:
                    logger.warning(f"Failed to get parsed content: HTTP {response.get('status_code')}")

                # Fallback 2: Try original uploaded file
                response = await client.get(
                    "storage",
                    f"/api/storage/projects/{project_id}/download/uploads/{filename}",
                    headers={"X-Correlation-ID": correlation_id} if correlation_id else {}
                )

                if response.get("status_code") == 200:
                    content = response.get("text", "")
                    if content and len(content.strip()) > 100:
                        return await self._extract_entities_from_text(
                            project_id, filename, content, correlation_id
                        )
                    else:
                        logger.warning(f"Original file exists but content too short for extraction: {filename}")

                elif response.get("status_code") == 404:
                    logger.warning(f"Original file not found (404): {filename}")
                else:
                    logger.warning(f"Failed to get original content: HTTP {response.get('status_code')}")

            except Exception as e:
                logger.warning(f"Failed to get content from storage: {e}")

            logger.warning(f"No suitable content found for entity extraction after trying all sources: {filename}")
            return {
                "status": "skipped",
                "message": "No suitable content found for entity extraction after trying structured, parsed, and original files",
                "entities": [],
                "correlation_id": correlation_id
            }

        except Exception as e:
            logger.error(f"LLM entity extraction failed for {filename}: {e}")
            return {
                "status": "error",
                "message": f"Entity extraction failed: {str(e)}",
                "entities": [],
                "correlation_id": correlation_id
            }

    async def _extract_entities_from_elements(
        self,
        project_id: str,
        filename: str,
        elements: List[Dict[str, Any]],
        correlation_id: str
    ) -> Dict[str, Any]:
        """Enhanced entity extraction with better error handling and document type awareness"""
        try:
            # Filter elements with meaningful content
            content_elements = [
                elem for elem in elements
                if elem.get("content", "").strip() and len(elem["content"].strip()) > 10
            ]

            if not content_elements:
                logger.info(f"No suitable elements found for entity extraction in {filename}")
                return {
                    "status": "skipped",
                    "message": "No suitable elements for entity extraction",
                    "entities": [],
                    "correlation_id": correlation_id
                }

            # Use graph service for entity extraction with enhanced error handling
            client = await get_service_client()

            # Backward compatibility: map legacy 'type' key to 'element_type' if missing
            normalized_elements = []
            for e in content_elements:
                if 'element_type' not in e:
                    e = {**e, 'element_type': e.get('type', 'unknown')}
                # Remove any keys that might confuse pydantic (optional)
                normalized_elements.append({
                    'element_id': e.get('element_id'),
                    'content': e.get('content', ''),
                    'element_type': e.get('element_type'),
                    'page_number': e.get('page_number'),
                    'hierarchy_level': e.get('hierarchy_level'),
                    'metadata': e.get('metadata')
                })

            # Safeguard: enforce element_type presence and log diagnostic stats
            missing_types = [e for e in normalized_elements if not e.get('element_type')]
            if missing_types:
                for mt in missing_types:
                    mt['element_type'] = 'unknown'
                logger.warning(f"Normalized elements missing element_type were patched with 'unknown' (count={len(missing_types)}) for {filename}")

            # Pre-call debug sampling (first 2 elements) to verify schema sent to graph service
            try:
                sample_debug = normalized_elements[:2]
                logger.debug(
                    "Graph entity extraction payload sample for %s: total=%d, sample=%s", 
                    filename, len(normalized_elements), sample_debug
                )
                # Also log aggregated type distribution for quick inspection
                from collections import Counter
                type_counter = Counter([e.get('element_type') for e in normalized_elements])
                logger.info(f"Element type distribution for entity extraction ({filename}): {dict(type_counter)}")
            except Exception as debug_e:
                logger.debug(f"Failed to build debug sample for entity extraction payload: {debug_e}")

            payload = {
                "document_id": str(uuid.uuid4()),
                "filename": filename,
                "structured_elements": normalized_elements,
                "processing_type": "entity_extraction",
                "extract_entities": True,
                "extract_relationships": False  # Focus on entities only
            }

            logger.info(f"Sending {len(content_elements)} elements to graph service for entity extraction")

            response = await client.post(
                "graph",
                f"/api/graphs/projects/{project_id}/process-structured",
                json=payload,
                headers={"X-Correlation-ID": correlation_id} if correlation_id else {},
                timeout=120
            )

            if response.get("status_code") == 200:
                result = response
                entities_extracted = result.get("entities_extracted", 0)
                document_type = result.get("document_type", "unknown")

                logger.info(f"Entity extraction successful: {entities_extracted} entities extracted from {len(content_elements)} elements (type: {document_type})")

                # Handle case where zero entities were extracted (expected for some document types)
                if entities_extracted == 0:
                    logger.info(f"No entities extracted from {filename} - this may be expected for {document_type} documents")
                    return {
                        "status": "success",
                        "entities_extracted": 0,
                        "elements_processed": len(content_elements),
                        "entities": [],
                        "document_type": document_type,
                        "message": f"No entities extracted (expected for {document_type} documents)",
                        "correlation_id": correlation_id
                    }

                return {
                    "status": "success",
                    "entities_extracted": entities_extracted,
                    "elements_processed": len(content_elements),
                    "entities": result.get("entities", []),
                    "document_type": document_type,
                    "correlation_id": correlation_id
                }
            elif response.get("status_code") == 422:
                # Handle 422 Unprocessable Entity - likely due to document type or content issues
                logger.warning(f"Graph service returned 422 for {filename} - likely document type/content issue")
                return {
                    "status": "skipped",
                    "message": "Graph service rejected request (422) - possibly unsupported document type",
                    "entities": [],
                    "correlation_id": correlation_id
                }
            else:
                logger.warning(f"Graph service entity extraction failed: HTTP {response.get('status_code')}")
                return {
                    "status": "error",
                    "message": f"Graph service error: HTTP {response.get('status_code')}",
                    "entities": [],
                    "correlation_id": correlation_id
                }

        except Exception as e:
            logger.error(f"Entity extraction from elements failed for {filename}: {e}")
            return {
                "status": "error",
                "message": f"Entity extraction error: {str(e)}",
                "entities": [],
                "correlation_id": correlation_id
            }

    async def _extract_entities_from_jsonl(
        self,
        project_id: str,
        filename: str,
        jsonl_content: str,
        correlation_id: str
    ) -> Dict[str, Any]:
        """Extract entities from JSONL content"""
        try:
            import json
            elements = []

            for line in jsonl_content.strip().split('\n'):
                if line.strip():
                    data = json.loads(line)
                    if data.get('type') == 'element':
                        element_data = data.get('data', {})
                        elements.append({
                            "type": element_data.get('type', 'unknown'),
                            "element_type": element_data.get('type', 'unknown'),
                            "content": element_data.get('text', ''),
                            "metadata": element_data.get('metadata', {}),
                            "page_number": element_data.get('page_number'),
                            "element_id": element_data.get('element_id'),
                            "hierarchy_level": element_data.get('hierarchy_level', 0),
                            "semantic_tags": element_data.get('semantic_tags', []),
                            "confidence_score": element_data.get('confidence_score', 0.8)
                        })

            return await self._extract_entities_from_elements(
                project_id, filename, elements, correlation_id
            )

        except Exception as e:
            logger.error(f"JSONL entity extraction failed: {e}")
            return {
                "status": "error",
                "message": f"JSONL parsing error: {str(e)}",
                "entities": []
            }

    async def _extract_entities_from_text(
        self,
        project_id: str,
        filename: str,
        content: str,
        correlation_id: str
    ) -> Dict[str, Any]:
        """Extract entities from plain text content"""
        try:
            if not content or len(content.strip()) < 100:
                return {
                    "status": "skipped",
                    "message": "Content too short for entity extraction",
                    "entities": []
                }

            # Use graph service for text-based entity extraction
            client = await get_service_client()
            payload = {
                "document_content": content,
                "filename": filename,
                "document_id": str(uuid.uuid4()),
                "processing_type": "text_entity_extraction"
            }

            response = await client.post(
                "graph",
                f"/api/graphs/projects/{project_id}/extract",
                json=payload,
                headers={"X-Correlation-ID": correlation_id} if correlation_id else {},
                timeout=120
            )

            if response.get("status_code") == 200:
                result = response
                logger.info(f"Text entity extraction successful for {filename}")
                return {
                    "status": "success",
                    "entities": result.get("entities", []),
                    "correlation_id": correlation_id
                }
            else:
                logger.warning(f"Text entity extraction failed: {response.get('status_code')}")
                return {
                    "status": "error",
                    "message": f"Graph service error: {response.get('status_code')}",
                    "entities": []
                }

        except Exception as e:
            logger.error(f"Text entity extraction failed: {e}")
            return {
                "status": "error",
                "message": f"Text extraction error: {str(e)}",
                "entities": []
            }
