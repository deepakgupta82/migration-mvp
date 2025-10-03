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
# Local graph-service client helper
from ..shared.graph_client import GraphServiceClient

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
        # Section enrichment (A3)
        self.enable_section_enrichment = os.getenv("SECTION_ENRICHMENT_ENABLED", "true").lower() in ("1","true","yes","on")
        # Proposal auto-post (A4)
        self.enable_auto_post_proposal = os.getenv("AUTO_POST_ENRICHED_PROPOSAL", "false").lower() in ("1","true","yes","on")

        # Force-enable graph integration for debugging if disabled
        if not self.enable_graph_integration:
            logger.warning("Graph integration was disabled, FORCE ENABLING for debugging!")
            self.enable_graph_integration = True

        logger.info(f"Enhanced Processor Configuration: vector={self.enable_vector_integration}, graph={self.enable_graph_integration}, websocket={self.enable_websocket_notifications}, llm={self.enable_llm_analysis}")

        # Performance optimization
        self.max_concurrent_integrations = int(os.getenv("MAX_CONCURRENT_INTEGRATIONS", "2"))
        self.enable_parallel_processing = os.getenv("ENABLE_PARALLEL_PROCESSING", "true").lower() == "true"

        # WebSocket deduplication window (seconds) to reduce noisy duplicate events
        try:
            self.ws_dedup_window = float(os.getenv("WEBSOCKET_DEDUP_WINDOW_SECONDS", "1.5"))
        except Exception:
            self.ws_dedup_window = 1.5
        # Cache for last websocket event per key
        self._ws_last_event: Dict[str, float] = {}

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
            
            # Initialize enrichment & LLM analysis result containers
            section_enrichment_result: Optional[Dict[str, Any]] = None
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
                    "stage": "jsonl_created",
                    "progress": 25,
                    "message": f"JSONL created with {len(processing_result.elements)} elements",
                    "details": f"Extracted {len(processing_result.elements)} structured elements from document"
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

            # Optional Section Enrichment (A3) prior to LLM analysis so LLM can later leverage sections (future)
            if self.enable_section_enrichment:
                try:
                    await self.progress_tracker.update_operation_progress(
                        event_id, "Enriching sections (A3)...", 2
                    )
                    section_enrichment_result = await self._enrich_sections(
                        project_id=project_id,
                        processing_result=processing_result,
                        structured_filename=structured_filename,
                        layout_filename=layout_filename,
                        correlation_id=correlation_id,
                    )
                except Exception as se:
                    logger.warning(f"Section enrichment failed (non-fatal): {se}")
            
            logger.info(f"Structured processing completed: {len(processing_result.elements)} elements extracted")

            # Determine document type profile (narrative/spreadsheet/ocr/mixed)
            doc_type = self._detect_document_type(filename, processing_result)
            logger.info(f"Document type detected: {doc_type}")

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
                        project_id, processing_result, correlation_id, doc_type=doc_type
                    ))

                # Optional: entity/triple cards vector upsert
                if self.enable_cards and self.enable_vector_integration:
                    integration_tasks.append(self._integrate_cards_vectors(
                        project_id, processing_result, correlation_id
                    ))

                if self.enable_graph_integration:
                    logger.info("Adding graph integration task to parallel execution")
                    integration_tasks.append(self._integrate_graph_service(
                        project_id, processing_result, correlation_id, doc_type=doc_type
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

                    # Handle results with proper type checking
                    vector_status = {"status": "disabled"}
                    graph_status = {"status": "disabled"}

                    result_index = 0
                    if self.enable_vector_integration:
                        vector_result = integration_results[result_index]
                        if isinstance(vector_result, Exception):
                            logger.error(f"Vector integration failed with exception: {vector_result}", exc_info=vector_result)
                            vector_status = {"status": "error", "message": str(vector_result), "exception_type": type(vector_result).__name__}
                        elif isinstance(vector_result, dict):
                            vector_status = vector_result
                            logger.info(f"Vector integration completed successfully: {vector_status}")
                            
                            # Send detailed vector completion message
                            embeddings_count = vector_status.get("embeddings_created", 0)
                            await self._send_websocket_notification(
                                project_id, correlation_id, "document_processing_progress",
                                {
                                    "filename": filename,
                                    "stage": "vector_embeddings_created",
                                    "progress": 55,
                                    "message": f"Created {embeddings_count} vector embeddings",
                                    "details": f"Vector database updated with {embeddings_count} embeddings"
                                }
                            )
                        else:
                            logger.warning(f"Vector integration returned unexpected type: {type(vector_result)}")
                            vector_status = {"status": "error", "message": f"Unexpected result type: {type(vector_result)}"}
                        result_index += 1

                    # If cards upsert task was scheduled, consume and log it to keep indices aligned
                    if self.enable_cards and self.enable_vector_integration:
                        cards_result = None
                        try:
                            cards_result = integration_results[result_index]
                        except Exception as cards_err:
                            logger.error(f"Failed to retrieve cards result: {cards_err}")
                            cards_result = None
                        if isinstance(cards_result, Exception):
                            logger.error(f"Cards vector upsert failed: {cards_result}", exc_info=cards_result)
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
                            
                            # Send detailed graph completion message with batch and extraction counts
                            entities_count = graph_status.get("entities_extracted", 0)
                            relationships_count = graph_status.get("relationships_found", 0)
                            elements_analyzed = graph_status.get("elements_analyzed", 0)
                            
                            details_parts = []
                            if elements_analyzed > 0:
                                details_parts.append(f"{elements_analyzed} elements analyzed")
                            if entities_count > 0:
                                details_parts.append(f"{entities_count} entities extracted")
                            if relationships_count > 0:
                                details_parts.append(f"{relationships_count} relationships found")
                            
                            details = ", ".join(details_parts) if details_parts else "Knowledge graph updated"
                            
                            await self._send_websocket_notification(
                                project_id, correlation_id, "document_processing_progress",
                                {
                                    "filename": filename,
                                    "stage": "graph_extraction_completed",
                                    "progress": 70,
                                    "message": f"Graph: {entities_count} entities, {relationships_count} relationships",
                                    "details": details
                                }
                            )
                        elif graph_result is None:
                            logger.warning("Graph integration returned None - treating as error")
                            graph_status = {"status": "error", "message": "Graph service returned None"}
                        else:
                            logger.warning(f"Unexpected graph result type: {type(graph_result)}")
                            graph_status = {"status": "error", "message": f"Unexpected result type: {type(graph_result)}"}
                    else:
                        logger.info("Graph integration disabled")
                        graph_status = {"status": "disabled"}
                    
                    # Send final integration completed message
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
                        project_id, processing_result, correlation_id, doc_type=doc_type
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
                        project_id, processing_result, correlation_id, doc_type=doc_type
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
                "doc_type": doc_type,
                "llm_analysis": llm_analysis_result,
                "section_enrichment": section_enrichment_result,
                "correlation_id": correlation_id,
                "processing_result": processing_result.to_dict()  # Convert to dict for JSON serialization
            }

            # Optional A4 proposal assembly / posting
            proposal_result = None
            if self.enable_auto_post_proposal and section_enrichment_result and section_enrichment_result.get("status") == "success":
                try:
                    proposal_result = await self.assemble_and_post_proposal(
                        project_id=project_id,
                        correlation_id=correlation_id,
                        section_enrichment=section_enrichment_result,
                        auto_post=True,
                    )
                except Exception as ap_err:
                    proposal_result = {"status": "error", "message": str(ap_err)}
                analysis_result["proposal_post"] = proposal_result
            elif section_enrichment_result and section_enrichment_result.get("status") == "success":
                # Provide a prepared payload preview (without posting) for UI clients
                try:
                    proposal_result = await self.assemble_and_post_proposal(
                        project_id=project_id,
                        correlation_id=correlation_id,
                        section_enrichment=section_enrichment_result,
                        auto_post=False,
                    )
                    analysis_result["proposal_preview"] = proposal_result.get("proposal")
                except Exception as prep_err:
                    analysis_result["proposal_preview_error"] = str(prep_err)

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

    def _detect_document_type(self, filename: str, processing_result: ProcessingResult) -> str:
        """Heuristic detection of document type to drive routing/profiles.

        Returns one of: 'excel_table', 'narrative', 'ocr_scanned', 'mixed'.
        """
        try:
            ext = (os.path.splitext(filename)[1] or '').lower()
            if ext in {'.xlsx', '.xls', '.csv'}:
                return 'excel_table'
            # Count element types
            total = max(1, len(processing_result.elements))
            table_count = sum(1 for e in processing_result.elements if (e.type or '').lower() == 'table')
            image_like = sum(1 for e in processing_result.elements if (e.type or '').lower() in {'image','figure','diagram'})
            text_like = sum(1 for e in processing_result.elements if (e.type or '').lower() in {'paragraph','text','narrative_text','list_item','title','header'})
            table_ratio = table_count / total
            if table_ratio >= 0.6:
                return 'excel_table'
            # OCR heuristic: many images and little text
            if image_like > 0 and text_like < image_like * 0.5:
                return 'ocr_scanned'
            # Predominantly text
            if text_like / total >= 0.5:
                return 'narrative'
            return 'mixed'
        except Exception:
            return 'mixed'

    async def assemble_and_post_proposal(
        self,
        project_id: str,
        correlation_id: str,
        section_enrichment: Optional[Dict[str, Any]],
        auto_post: bool = True,
        proposal_type: str = "standard"
    ) -> Dict[str, Any]:
        """A4: Aggregate section enrichment into a proposal payload and POST to graph-service.

        Strategy (initial heuristic):
          - Summarized entities/relationships/facts remain empty placeholders until later enrichment passes.
          - payload_* columns carry raw section objects for traceability.
        """
        if not section_enrichment or section_enrichment.get("status") != "success":
            return {"status": "skipped", "reason": "no_section_enrichment"}
        try:
            sections = section_enrichment.get("sections", [])
            # Placeholder extraction logic: future passes will distill section-level entities
            entities: List[Dict[str, Any]] = []
            relationships: List[Dict[str, Any]] = []
            facts: List[Dict[str, Any]] = []
            # Build payload_* raw artifacts (could be filtered / normalized later)
            payload_entities = []
            payload_relationships = []
            payload_facts = []
            evidence: List[Dict[str, Any]] = []
            for s in sections:
                # Store section itself as a fact-like artifact for now; later we will parse
                payload_facts.append({
                    "section_id": s.get("section_id"),
                    "heading": s.get("heading"),
                    "text_length": s.get("text_length"),
                    "page_spread": s.get("page_spread"),
                    "elements_count": s.get("elements_count"),
                })
                evidence.append({
                    "kind": "section_summary",
                    "section_id": s.get("section_id"),
                    "heading": s.get("heading"),
                    "pages": s.get("page_spread"),
                    "elements_count": s.get("elements_count"),
                    "extracted_entities": len(s.get("entities", [])),
                    "extracted_relationships": len(s.get("relationships", [])),
                })
            proposal_payload = {
                "proposal_id": str(uuid.uuid4()),
                "proposal_type": proposal_type,
                "entities": entities,
                "relationships": relationships,
                "facts": facts,
                "payload_entities": payload_entities,
                "payload_relationships": payload_relationships,
                "payload_facts": payload_facts,
                "source_documents": [],
                "evidence": evidence,
                "meta_counts": {
                    "sections": len(sections),
                    "payload_facts": len(payload_facts),
                    "evidence": len(evidence),
                }
            }
            if not auto_post:
                return {"status": "prepared", "proposal": proposal_payload}
            client = GraphServiceClient()
            resp = await client.propose_entities(project_id, proposal_payload, corr_id=correlation_id)
            if resp.get("error"):
                return {"status": "error", "message": resp.get("error"), "code": resp.get("code"), "proposal": proposal_payload}
            return {"status": "posted", "graph_response": resp, "proposal": proposal_payload}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def _enrich_sections(
        self,
        project_id: str,
        processing_result: ProcessingResult,
        structured_filename: str,
        layout_filename: Optional[str],
        correlation_id: Optional[str] = None,
        max_section_chars: int = 4000,
    ) -> Dict[str, Any]:
        """A3: Derive logical sections and perform lightweight enrichment.

        This initial implementation is intentionally heuristic and fast:
        - Uses heading-like elements (type in {title, header}) as section delimiters
        - Aggregates following elements until next heading or size threshold
        - Produces per-section summary stats and simple entity/relationship/fact placeholders
        - Returns a structure ready to be persisted later into payload_* columns

        Future enhancements (not yet implemented):
        - Table/figure cross-references using layout JSONL
        - LLM summarization per section (behind a flag)
        - Confidence scoring and deduplication across sections
        """
        try:
            # ---------- Caching pre-check ----------
            from ..cache.section_enrich_cache import (
                get_section_enrich_cache, build_cache_key
            )
            cache = get_section_enrich_cache()
            elem_ids = [e.element_id for e in processing_result.elements]
            total_len = sum(len(e.text or "") for e in processing_result.elements)
            cache_key = build_cache_key(project_id, structured_filename, elem_ids[:2000], total_len)
            cached = cache.get(cache_key)
            if cached:
                cached_copy = dict(cached)
                cached_copy["cache_hit"] = True
                cached_copy["cache_key"] = cache_key
                return cached_copy

            # ---------- Token budgeting helpers ----------
            max_tokens_per_section = int(os.getenv("SECTION_TOKEN_BUDGET", "750"))
            # crude token estimate (~4 chars/token fallback)
            def est_tokens(text: str) -> int:
                return max(1, len(text) // 4)

            sections: List[Dict[str, Any]] = []
            current: Optional[Dict[str, Any]] = None
            current_tok = 0
            import re
            entity_pattern = re.compile(r"\b([A-Z][A-Za-z0-9]{2,}(?:\s+[A-Z][A-Za-z0-9]{2,}){0,3})\b")
            rel_pattern = re.compile(r"\b([A-Z][A-Za-z0-9]+)\s+(is|has|includes|requires)\s+([A-Z][A-Za-z0-9]+)\b")

            def start_section(heading_text: str, etype: str):
                return {
                    "section_id": f"sec_{len(sections)}",
                    "heading": heading_text,
                    "heading_type": etype,
                    "content": "",
                    "elements": [],
                    "entities": [],
                    "relationships": [],
                    "facts": [],
                    "page_spread": set(),
                    "tables": [],
                    "figures": [],
                    "token_budget_exceeded": False,
                }

            for elem in processing_result.elements:
                etype = (elem.type or '').lower()
                raw_text = (elem.text or '').strip()
                if not raw_text:
                    continue
                is_heading = etype in {"title", "header"}
                if is_heading or current is None or current_tok > max_tokens_per_section:
                    if current is not None:
                        current["text_length"] = len(current.get("content", ""))
                        sections.append(current)
                    heading = raw_text if is_heading else f"Section {len(sections)+1}"
                    current = start_section(heading, etype if is_heading else "auto")
                    current_tok = 0
                # Append element content
                if current is not None:
                    if current["content"]:
                        current["content"] += "\n\n" + raw_text
                    else:
                        current["content"] = raw_text
                    current["elements"].append({
                        "element_id": elem.element_id,
                        "type": etype,
                        "page_number": elem.page_number,
                        "chars": len(raw_text),
                    })
                    if elem.page_number is not None:
                        current["page_spread"].add(elem.page_number)
                    # classify for multimodal grouping
                    if etype == 'table':
                        current.setdefault('tables', []).append({
                            'element_id': elem.element_id,
                            'preview': raw_text[:200],
                        })
                    if etype in {'image','figure','diagram'}:
                        current.setdefault('figures', []).append({
                            'element_id': elem.element_id,
                            'preview': raw_text[:200],
                        })
                    # basic NER/relationship heuristic
                    if etype in {"paragraph", "title", "header", "list_item"}:
                        ents = []
                        for m in entity_pattern.findall(raw_text):
                            token = m.strip()
                            if len(token.split()) > 6 or len(token) < 3:
                                continue
                            ents.append(token)
                        if ents:
                            seen_e = set()
                            norm_ents = []
                            for e in ents[:20]:
                                key = e.lower()
                                if key in seen_e:
                                    continue
                                seen_e.add(key)
                                norm_ents.append({"name": e, "source_element": elem.element_id})
                            current["entities"].extend(norm_ents)
                        rels = []
                        for rm in rel_pattern.findall(raw_text):
                            src, pred, dst = rm
                            rels.append({
                                "from_name": src,
                                "predicate": pred,
                                "to_name": dst,
                                "source_element": elem.element_id,
                            })
                        if rels:
                            current["relationships"].extend(rels[:10])
                    current_tok += est_tokens(raw_text)
                    if current_tok > max_tokens_per_section:
                        current["token_budget_exceeded"] = True

            if current is not None:
                current["text_length"] = len(current.get("content", ""))
                sections.append(current)

            # Dedupe entities & relationships per section
            for s in sections:
                dedup_e = []
                seen_en = set()
                for ent in s.get("entities", []):
                    k = ent["name"].lower()
                    if k in seen_en:
                        continue
                    seen_en.add(k)
                    dedup_e.append(ent)
                s["entities"] = dedup_e
                dedup_r = []
                seen_r = set()
                for rel in s.get("relationships", []):
                    k = (rel["from_name"].lower(), rel["predicate"].lower(), rel["to_name"].lower())
                    if k in seen_r:
                        continue
                    seen_r.add(k)
                    dedup_r.append(rel)
                s["relationships"] = dedup_r
                pages = sorted(list(s.get("page_spread", [])))
                s["page_spread"] = pages
                s["elements_count"] = len(s.get("elements", []))

            # ---------- Multimodal integration (tables / diagrams) ----------
            multimodal_enabled = str(os.getenv("MULTIMODAL_ENABLED","true")).lower() in ("1","true","yes","on")
            if multimodal_enabled:
                import httpx
                llm_url = os.getenv("LLM_SERVICE_URL","http://localhost:8007")
                async with httpx.AsyncClient(timeout=20.0) as client:
                    for s in sections:
                        # Only call when we actually have candidate visual elements
                        if s.get('tables'):
                            try:
                                payload = {"project_id": project_id, "text": s.get("heading"), "image_urls": []}
                                r = await client.post(f"{llm_url}/api/llm/multimodal/tables", json=payload)
                                if r.status_code == 200:
                                    resp = r.json()
                                    if resp.get("success"):
                                        s["tables_extracted"] = resp.get("data", {}).get("tables", [])
                            except Exception as te:
                                s.setdefault("multimodal_errors", []).append(str(te)[:120])
                        if s.get('figures'):
                            try:
                                payload = {"project_id": project_id, "text": s.get("heading"), "image_urls": []}
                                r = await client.post(f"{llm_url}/api/llm/multimodal/diagrams", json=payload)
                                if r.status_code == 200:
                                    resp = r.json()
                                    if resp.get("success"):
                                        s["figures_extracted"] = resp.get("data", {}).get("entities", [])
                            except Exception as de:
                                s.setdefault("multimodal_errors", []).append(str(de)[:120])

            summary = {
                "sections_count": len(sections),
                "total_elements": len(processing_result.elements),
                "approx_total_chars": sum(s.get("text_length", 0) for s in sections),
                "extracted_entities": sum(len(s.get("entities", [])) for s in sections),
                "extracted_relationships": sum(len(s.get("relationships", [])) for s in sections),
                "multimodal_sections": sum(1 for s in sections if s.get('tables_extracted') or s.get('figures_extracted')),
                "token_budget": max_tokens_per_section,
            }
            result_obj = {
                "status": "success",
                "sections": sections,
                "summary": summary,
                "structured_ref": structured_filename,
                "layout_ref": layout_filename,
                "cache_key": cache_key,
                "cache_hit": False,
            }
            cache.set(cache_key, result_obj)
            return result_obj
        except Exception as e:
            logger.warning(f"Section enrichment error: {e}")
            return {"status": "error", "message": str(e)}

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
        correlation_id: str,
        doc_type: Optional[str] = None
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
                # Include additional element types for comprehensive vector coverage
                # Includes PDF OCR content: uncategorizedtext, header, footer, image (with text)
                allowed_types = [
                    'title', 'narrative_text', 'list_item', 'table', 'table_row',
                    'uncategorizedtext', 'header', 'footer', 'image'
                ]
                if element.type in allowed_types and len(element.text.strip()) > 10:
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
                    "metadata": {
                        "project_id": project_id,
                        "document_id": processing_result.document_metadata.filename,
                        "page_number": doc.get("page_number"),
                        "element_id": doc.get("element_id"),
                        "element_type": (doc.get("element_type") or '').lower(),
                        "doc_type": doc_type or 'unknown'
                    }
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
        correlation_id: str,
        doc_type: Optional[str] = None
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

        # Enhanced timeout and retry configuration (env-tunable)
        try:
            max_retries = int(os.getenv("GRAPH_MAX_RETRIES", "3"))
        except Exception:
            max_retries = 3
        try:
            # Increased default timeout to 1000s (from 120s) to support 15-min LLM calls
            base_timeout = float(os.getenv("GRAPH_BASE_TIMEOUT_SECONDS", "1000"))
        except Exception:
            base_timeout = 1000.0
        try:
            # Increased max timeout to 1200s (from 300s) for long-running operations
            max_timeout = float(os.getenv("GRAPH_MAX_TIMEOUT_SECONDS", "1200"))
        except Exception:
            max_timeout = 1200.0
        retry_delays = [2, 5, 10]

        try:
            logger.info(f"Processing {len(processing_result.elements)} elements for graph service integration")

            # Prepare structured content for graph processing by READING JSONL from storage
            # This enforces that graph-service uses the JSONL output (not the original CSV)
            content_elements = []
            jsonl_rows: List[Dict[str, Any]] = []  # rows for unified extractor (table_row -> metadata.row_data)
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
                        # Capture spreadsheet row data for unified extractor when available
                        try:
                            if ((elem.get("type") or elem.get("element_type") or "").lower() == "table_row"):
                                md = elem.get("metadata") or {}
                                row_map = md.get("row_data")
                                if isinstance(row_map, dict) and row_map:
                                    # Normalize values to compact strings/numbers
                                    norm_row: Dict[str, Any] = {}
                                    for k, v in row_map.items():
                                        if isinstance(v, (int, float)):
                                            norm_row[str(k)] = v
                                        elif v is None:
                                            norm_row[str(k)] = ""
                                        else:
                                            s = str(v)
                                            norm_row[str(k)] = s.replace("\n", " ").replace("\r", " ")
                                    jsonl_rows.append(norm_row)
                        except Exception:
                            pass
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

            # Prefer unified extractor for spreadsheet-style docs when row data present
            use_unified = os.getenv("USE_UNIFIED_EXTRACTOR", "true").lower() in ("1", "true", "yes", "on")
            is_spreadsheet = (doc_type == 'excel_table') or any((e.get("element_type") == "table_row") for e in content_elements)
            if use_unified and is_spreadsheet and jsonl_rows:
                try:
                    logger.info(f"Using unified extractor with {len(jsonl_rows)} rows (spreadsheets)")
                    client = await get_service_client()
                    headers = {"X-Correlation-ID": correlation_id} if correlation_id else {}
                    # Chunking config for unified extractor
                    try:
                        chunk_rows = int(os.getenv("UNIFIED_CHUNK_ROWS", os.getenv("TABLE_GRAPH_MAX_ELEMENTS", "300")))
                    except Exception:
                        chunk_rows = 300
                    try:
                        max_parts = int(os.getenv("UNIFIED_MAX_PARTS", "2"))
                    except Exception:
                        max_parts = 2

                    payload = {
                        "document_id": str(processing_result.document_metadata.filename) + "::" + str(uuid.uuid4()),
                        "filename": processing_result.document_metadata.filename,
                        "rows": jsonl_rows,
                        "chunk_rows": chunk_rows,
                        "max_parts": max_parts,
                    }
                    resp = await client.post(
                        "graph",
                        f"/api/graphs/projects/{project_id}/extract-unified",
                        json=payload,
                        headers=headers,
                        timeout=float(os.getenv("GRAPH_BASE_TIMEOUT_SECONDS", "1000"))
                    )
                    status_code = resp.get("status_code")
                    if status_code not in (200, 202):
                        logger.warning(f"Unified extractor enqueue failed: HTTP {status_code}")
                    else:
                        job_id = (resp.get("json") or {}).get("job_id") or resp.get("job_id")
                        if job_id:
                            # Poll job until completion or timeout
                            logger.info(f"Unified job queued: {job_id}; polling status...")
                            start_poll = time.time()
                            total_timeout = float(os.getenv("GRAPH_MAX_TIMEOUT_SECONDS", "600"))
                            poll_delay = 2.0
                            poll_timeout = 30.0  # Timeout for individual status checks
                            final_status = None
                            entities_found = 0
                            relationships_found = 0
                            facts_found = 0
                            poll_count = 0
                            while (time.time() - start_poll) < total_timeout:
                                poll_count += 1
                                try:
                                    js = await client.get(
                                        "graph",
                                        f"/api/graphs/projects/{project_id}/jobs/{job_id}",
                                        headers=headers,
                                        timeout=poll_timeout  # Explicit timeout for status check
                                    )
                                    if (js or {}).get("status_code") == 200:
                                        body = js.get("json") or js
                                        st = (body or {}).get("status")
                                        logger.debug(f"Unified job {job_id} poll {poll_count}: status={st}")
                                        if st in ("succeeded", "failed"):
                                            final_status = st
                                            entities_found = int((body or {}).get("entities_found") or 0)
                                            relationships_found = int((body or {}).get("relationships_found") or 0)
                                            facts_found = int((body or {}).get("facts_found") or 0)
                                            break
                                    elif (js or {}).get("status_code") == 404:
                                        logger.warning(f"Unified job {job_id} not found, may have expired")
                                        break
                                except Exception as poll_err:
                                    logger.warning(f"Unified job poll error (attempt {poll_count}): {poll_err}")
                                    # Continue polling unless we've hit max timeout
                                
                                await asyncio.sleep(poll_delay)
                                poll_delay = min(poll_delay * 1.5, 10.0)

                            elapsed = time.time() - start_poll
                            if final_status == "succeeded":
                                logger.info(f"Unified extraction succeeded after {elapsed:.1f}s ({poll_count} polls): entities={entities_found} rels={relationships_found} facts={facts_found}")
                                return {
                                    "status": "success",
                                    "elements_analyzed": len(jsonl_rows),
                                    "entities_extracted": entities_found,
                                    "relationships_found": relationships_found,
                                    "facts_found": facts_found,
                                    "processing_time": elapsed,
                                    "attempts": 1,
                                }
                            elif final_status == "failed":
                                logger.error(f"Unified extraction job failed after {elapsed:.1f}s ({poll_count} polls); falling back to legacy structured path")
                            else:
                                logger.warning(f"Unified extraction timed out after {elapsed:.1f}s ({poll_count} polls); falling back to legacy structured path")
                        else:
                            logger.warning("Unified extractor did not return a job_id; falling back")
                except Exception as ue:
                    logger.warning(f"Unified extractor path error: {ue}; proceeding with legacy structured path")

            # Optional payload trimming for large table-like content to avoid long blocking calls
            try:
                max_table_chars = int(os.getenv("GRAPH_TABLE_CONTENT_MAX_CHARS", "8000"))
            except Exception:
                max_table_chars = 8000
            try:
                max_elements = int(os.getenv("GRAPH_MAX_ELEMENTS", "0"))  # 0 means no cap
            except Exception:
                max_elements = 0

            if content_elements:
                trimmed: List[Dict[str, Any]] = []
                for e in content_elements[: (max_elements or len(content_elements))]:
                    et = (e.get("element_type") or "").lower()
                    c = e.get("content") or ""
                    if et == "table" and len(c) > max_table_chars:
                        # Keep only first N chars and add note in metadata
                        e = dict(e)
                        e["content"] = c[:max_table_chars]
                        md = dict(e.get("metadata") or {})
                        md["_trimmed_for_graph"] = True
                        md["_original_length"] = len(c)
                        md["_kept_chars"] = max_table_chars
                        e["metadata"] = md
                    trimmed.append(e)
                # Only replace if any trimming or capping applied
                if len(trimmed) != len(content_elements) or any((t.get("metadata") or {}).get("_trimmed_for_graph") for t in trimmed):
                    logger.info(
                        "Applied graph payload shaping: elements=%d (was %d), table_trim<=%d chars",
                        len(trimmed), len(content_elements), max_table_chars,
                    )
                content_elements = trimmed

            # Provider-aware input budgeting caps (fallback if provider config unavailable)
            narrative_cap = int(os.getenv("GRAPH_NARRATIVE_CAP_CHARS", "28000"))
            sheet_cap = int(os.getenv("GRAPH_SPREADSHEET_CAP_CHARS", "20000"))
            effective_cap = sheet_cap if (doc_type == 'excel_table') else narrative_cap

            # Spreadsheet batching configuration
            batch_chars = int(os.getenv("TABLE_GRAPH_BATCH_CHARS", "12000"))
            batch_max_elements = int(os.getenv("TABLE_GRAPH_MAX_ELEMENTS", "450"))

            # Decide batching: for excel_table or when content is large
            need_batching = (doc_type == 'excel_table') or (sum(len(e.get('content') or '') for e in content_elements) > effective_cap)

            if not content_elements:
                logger.warning("No suitable elements found for entity extraction")
                return {"status": "skipped", "message": "No suitable elements for entity extraction"}

            # Send to Graph Service for processing with enhanced retry logic
            logger.info(f"Calling graph service for project {project_id}")

            client = await get_service_client()
            shared_document_id = str(uuid.uuid4())
            base_payload = {
                "document_id": shared_document_id,
                "filename": processing_result.document_metadata.filename,
                "processing_type": "structured_extraction",
                "extract_entities": True,
                "extract_relationships": True,
                "strict_json": True,
                # Hint to downstream about dominant content type to adjust strategy/prompts
                "document_type": (doc_type or ("excel_table" if all((e.get("element_type") or "").lower() == "table" for e in content_elements) else "mixed"))
            }

            headers = {}
            if correlation_id:
                headers["X-Correlation-ID"] = correlation_id

            logger.info(f"Sending {len(content_elements)} elements to graph service" + (" in batches" if need_batching else ""))

            # Enhanced retry logic with progressive timeout increases
            last_exception = None

            def _split_into_batches(items: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
                batches: List[List[Dict[str, Any]]] = []
                buf: List[Dict[str, Any]] = []
                total_chars = 0
                for e in items:
                    c = e.get('content') or ''
                    if (len(buf) >= batch_max_elements) or (total_chars + len(c) > batch_chars and buf):
                        batches.append(buf)
                        buf = []
                        total_chars = 0
                    buf.append(e)
                    total_chars += len(c)
                if buf:
                    batches.append(buf)
                return batches

            async def _call_graph(payload_structured: List[Dict[str, Any]], attempt: int) -> Optional[Dict[str, Any]]:
                # Progressive timeout increase
                current_timeout = min(base_timeout + (attempt * 30), max_timeout)
                request_headers = headers.copy()
                request_headers["X-Timeout"] = str(int(current_timeout))
                start_time = time.time()
                response = await client.post(
                    "graph",
                    f"/api/graphs/projects/{project_id}/process-structured",
                    json={**base_payload, "structured_elements": payload_structured},
                    headers=request_headers,
                    timeout=current_timeout
                )
                processing_time = time.time() - start_time
                logger.info(f"Graph service response: {response.get('status_code')} (took {processing_time:.2f}s)")
                return {"response": response, "processing_time": processing_time, "timeout": current_timeout}

            # Prepare batches if needed
            batches = _split_into_batches(content_elements) if need_batching else [content_elements]
            total_entities = 0
            total_relationships = 0
            total_elements = 0
            total_time = 0.0
            # Facts-once configuration
            facts_once_enabled = str(os.getenv("FACTS_ONCE_PER_DOCUMENT", "true")).lower() in ("1","true","yes","on")

            for bi, batch in enumerate(batches):
                logger.info(f"Processing graph batch {bi+1}/{len(batches)} with {len(batch)} elements")
                last_exception = None
                for attempt in range(max_retries):
                    try:
                        call = await _call_graph(batch, attempt)
                        response = call["response"]
                        processing_time = call["processing_time"]
                        status_code = response.get("status_code")
                        if status_code == 200:
                            result = response
                            entities_extracted = int(result.get("entities_extracted", 0))
                            relationships_found = int(result.get("relationships_found", 0))
                            total_entities += entities_extracted
                            total_relationships += relationships_found
                            total_elements += len(batch)
                            total_time += processing_time
                            break
                        elif status_code == 429:
                            logger.warning(f"Graph service rate limited (429) on attempt {attempt + 1} (batch {bi+1})")
                            if attempt < max_retries - 1:
                                delay = retry_delays[attempt] * 2
                                logger.info(f"Waiting {delay} seconds before retry due to rate limit...")
                                await asyncio.sleep(delay)
                                continue
                        elif status_code and status_code >= 500:
                            logger.warning(f"Graph service server error ({status_code}) on attempt {attempt + 1} (batch {bi+1})")
                            if attempt < max_retries - 1:
                                delay = retry_delays[attempt]
                                logger.info(f"Waiting {delay} seconds before retry due to server error...")
                                await asyncio.sleep(delay)
                                continue
                        else:
                            status_text = str(status_code) if status_code else "None"
                            error_text = str(response)[:500]
                            logger.error(f"❌ Graph service client error ({status_text}): {error_text}")
                            return {
                                "status": "error",
                                "message": f"Graph service client error: {status_text} - {error_text[:200]}",
                                "attempts": attempt + 1
                            }
                    except asyncio.TimeoutError as tex:
                        last_exception = tex
                        logger.warning(f"Graph service timeout on attempt {attempt + 1} (batch {bi+1})")
                        if attempt < max_retries - 1:
                            delay = retry_delays[attempt]
                            logger.info(f"Waiting {delay} seconds before retry due to timeout...")
                            await asyncio.sleep(delay)
                            continue
                    except Exception as e:
                        last_exception = e
                        logger.error(f"Graph service call failed on attempt {attempt + 1} (batch {bi+1}): {e}")
                        if attempt < max_retries - 1:
                            delay = retry_delays[attempt]
                            logger.info(f"Waiting {delay} seconds before retry due to error...")
                            await asyncio.sleep(delay)
                            continue

                if last_exception and (total_elements == 0):
                    # if first batch failed after retries
                    error_msg = f"Graph service failed after {max_retries} attempts: {str(last_exception)}"
                    logger.error(f"❌ {error_msg}")
                    return {"status": "error", "message": error_msg, "attempts": max_retries}

            # After all batches complete, optionally trigger facts exactly once (legacy path only)
            if facts_once_enabled and total_elements > 0:
                try:
                    logger.info("Triggering facts extraction once for the entire document (legacy path)")
                    facts_payload = {
                        "document_id": shared_document_id,
                        "filename": processing_result.document_metadata.filename,
                        "structured_elements": content_elements,
                        "processing_type": "structured_extraction",
                        "extract_entities": False,
                        "extract_relationships": False
                    }
                    facts_resp = await client.post(
                        "graph",
                        f"/api/graphs/projects/{project_id}/structured/facts",
                        json=facts_payload,
                        headers=headers,
                        timeout=120
                    )
                    if (facts_resp or {}).get("status_code") in (200, 202):
                        logger.info("Facts extraction (once) completed successfully")
                    else:
                        logger.debug(f"Facts extraction (once) returned HTTP {facts_resp.get('status_code')}")
                except Exception as _facts_err:
                    logger.debug(f"Facts extraction (once) skipped due to error: {_facts_err}")

            # Summarize across batches
            return {
                "status": "success",
                "elements_analyzed": total_elements,
                "entities_extracted": total_entities,
                "relationships_found": total_relationships,
                "processing_time": total_time,
                "attempts": max_retries
            }

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
            # Deduplicate repeated messages within a small time window
            import time as _time
            key_parts = [project_id or "", event_type or "", str(data.get("stage") or ""), str(data.get("progress") or ""), data.get("filename") or ""]
            dedup_key = "|".join(key_parts)
            now = _time.time()
            last = self._ws_last_event.get(dedup_key)
            if last is not None and (now - last) < self.ws_dedup_window:
                logger.debug(f"Skipping duplicate websocket event within {self.ws_dedup_window}s window: {dedup_key}")
                return
            self._ws_last_event[dedup_key] = now

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
            file_path = None
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
                    
            except Exception as e:
                logger.error(f"Error processing {filename}: {e}")
                failed_count += 1
                results.append({
                    "status": "error",
                    "filename": filename,
                    "error": str(e),
                    "correlation_id": correlation_id
                })
            finally:
                # Fix #5: Always clean up temp file with retry logic for Windows file locks
                if file_path and os.path.exists(file_path):
                    from ..utils.file_utils import cleanup_temp_file_with_retry
                    try:
                        if cleanup_temp_file_with_retry(file_path):
                            logger.debug(f"Cleaned up temp file: {file_path}")
                        else:
                            logger.warning(f"Failed to cleanup temp file (will retry later): {file_path}")
                    except Exception as cleanup_error:
                        logger.warning(f"Error during temp file cleanup: {cleanup_error}")
        
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
            from ..utils.file_utils import create_temp_file_with_actual_name
            
            client = await get_service_client()

            # Download file from storage service
            response = await client.get(
                "storage",
                f"/api/storage/projects/{project_id}/download/uploads_raw/{filename}",
                headers={"X-Correlation-ID": correlation_id} if correlation_id else {}
            )

            if response.get("status_code") != 200:
                raise Exception(f"Failed to download file from storage: {response.get('status_code')}")

            # Save to temporary file with actual filename + timestamp
            # This is better than random temp names (tmpc7qtvyfo.xlsx) because:
            # - Easier to debug and track in logs
            # - Better compatibility with processing libraries
            # - Timestamp prevents conflicts
            content = response.get("content", b"")
            temp_path = create_temp_file_with_actual_name(
                original_filename=filename,
                content=content,
                project_id=project_id,
                prefix="download_"
            )

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

    async def assess_document_llm(
        self,
        project_id: str,
        filename: str,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate document-level assessment using LLM analysis
        Creates a high-level summary with key topics, entities, insights, and relationships
        
        Args:
            project_id: Project identifier
            filename: Document filename
            correlation_id: Optional correlation ID for tracking
            
        Returns:
            Dict containing assessment results with summary, topics, insights, etc.
        """
        try:
            if not correlation_id:
                correlation_id = str(uuid.uuid4())
            
            logger.info(f"Starting document assessment for {filename} [corr_id={correlation_id}]")
            
            # Get document content from storage (try structured first, then parsed)
            client = await get_service_client()
            
            # Try structured content first
            base_name = os.path.splitext(filename)[0]
            structured_filename = f"{base_name}_structured.jsonl"
            
            content_for_assessment = None
            content_source = None
            
            # Attempt 1: Get structured JSONL content
            try:
                response = await client.get(
                    "storage",
                    f"/api/storage/projects/{project_id}/download/structured/{structured_filename}",
                    headers={"X-Correlation-ID": correlation_id} if correlation_id else {}
                )
                
                if response.get("status_code") == 200:
                    jsonl_content = response.get("text", "")
                    if jsonl_content.strip():
                        # Parse JSONL and extract text content
                        text_parts = []
                        for line in jsonl_content.strip().split('\n'):
                            if line.strip():
                                try:
                                    data = json.loads(line)
                                    if data.get('type') == 'element':
                                        element_data = data.get('data', {})
                                        text = element_data.get('text', '').strip()
                                        if text and len(text) > 20:  # Filter out very short snippets
                                            text_parts.append(text)
                                except json.JSONDecodeError:
                                    continue
                        
                        if text_parts:
                            content_for_assessment = "\n\n".join(text_parts)
                            content_source = "structured"
                            logger.info(f"Using structured content for assessment: {len(text_parts)} elements")
            except Exception as e:
                logger.debug(f"Could not get structured content: {e}")
            
            # Attempt 2: Get parsed markdown content
            if not content_for_assessment:
                try:
                    response = await client.get(
                        "storage",
                        f"/api/storage/projects/{project_id}/download/uploads_parsed/{filename}",
                        headers={"X-Correlation-ID": correlation_id} if correlation_id else {}
                    )
                    
                    if response.get("status_code") == 200:
                        content = response.get("text", "")
                        if content.strip():
                            content_for_assessment = content
                            content_source = "parsed"
                            logger.info(f"Using parsed content for assessment: {len(content)} chars")
                except Exception as e:
                    logger.debug(f"Could not get parsed content: {e}")
            
            if not content_for_assessment:
                logger.warning(f"No suitable content found for assessment: {filename}")
                return {
                    "status": "skipped",
                    "message": "No suitable content found for assessment",
                    "correlation_id": correlation_id
                }
            
            # Truncate content if too large (max ~8000 tokens ≈ 32000 chars)
            max_chars = 32000
            if len(content_for_assessment) > max_chars:
                content_for_assessment = content_for_assessment[:max_chars] + "\n\n[Content truncated for analysis]"
                logger.info(f"Content truncated from {len(content_for_assessment)} to {max_chars} chars")
            
            # Call LLM service for document assessment
            assessment_prompt = f"""Analyze the following document and provide a comprehensive assessment.

Document: {filename}

Content:
{content_for_assessment}

Please provide:
1. Executive Summary (2-3 sentences)
2. Key Topics (list 5-7 main topics)
3. Important Entities (people, organizations, systems, technologies mentioned)
4. Key Insights (3-5 actionable insights)
5. Document Type Classification
6. Technical Complexity Level (Low/Medium/High)
7. Migration Relevance Score (0-10)

Format your response as JSON with these exact keys:
{{
  "summary": "...",
  "topics": ["topic1", "topic2", ...],
  "entities": ["entity1", "entity2", ...],
  "insights": ["insight1", "insight2", ...],
  "document_type": "...",
  "complexity": "...",
  "migration_relevance": 0
}}"""

            llm_response = await client.post(
                "llm",
                "/api/llm/process",
                json={
                    "process_type": "document_assessment",
                    "prompt": assessment_prompt,
                    "project_id": project_id,
                    "metadata": {
                        "filename": filename,
                        "content_source": content_source or "unknown",
                        "correlation_id": correlation_id
                    }
                },
                headers={"X-Correlation-ID": correlation_id} if correlation_id else {},
                timeout=180  # Increased timeout for document assessment (3 minutes)
            )
            
            if llm_response.get("status_code") != 200:
                logger.error(f"LLM service error: {llm_response.get('status_code')}")
                return {
                    "status": "error",
                    "message": f"LLM service error: {llm_response.get('status_code')}",
                    "correlation_id": correlation_id
                }
            
            # Parse LLM response
            llm_result = llm_response.get("result", {})
            llm_content = llm_result.get("output", "") if isinstance(llm_result, dict) else str(llm_result)
            
            # Try to extract JSON from response
            assessment_data = {}
            try:
                # Remove markdown code blocks if present
                if "```json" in llm_content:
                    llm_content = llm_content.split("```json")[1].split("```")[0]
                elif "```" in llm_content:
                    llm_content = llm_content.split("```")[1].split("```")[0]
                
                assessment_data = json.loads(llm_content.strip())
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse LLM response as JSON: {e}")
                # Fallback: return raw content
                assessment_data = {
                    "summary": llm_content[:500],
                    "topics": [],
                    "entities": [],
                    "insights": [],
                    "document_type": "unknown",
                    "complexity": "medium",
                    "migration_relevance": 5
                }
            
            # Store assessment in document metadata (via storage service)
            try:
                metadata_update = {
                    "assessment": assessment_data,
                    "assessment_timestamp": datetime.now().isoformat(),
                    "content_source": content_source,
                    "correlation_id": correlation_id
                }
                
                # Update document metadata in storage
                await client.post(
                    "storage",
                    f"/api/storage/projects/{project_id}/files/{filename}/metadata",
                    json=metadata_update,
                    headers={"X-Correlation-ID": correlation_id} if correlation_id else {}
                )
                
                logger.info(f"Document assessment completed and stored for {filename}")
            except Exception as e:
                logger.warning(f"Failed to store assessment metadata: {e}")
            
            return {
                "status": "success",
                "filename": filename,
                "assessment": assessment_data,
                "correlation_id": correlation_id
            }
            
        except Exception as e:
            logger.error(f"Document assessment failed for {filename}: {e}")
            return {
                "status": "error",
                "message": f"Assessment failed: {str(e)}",
                "correlation_id": correlation_id
            }

    async def update_project_insights_llm(
        self,
        project_id: str,
        assessment: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update project-level insights by aggregating document assessments
        Creates cross-document insights, patterns, and recommendations
        
        Args:
            project_id: Project identifier
            assessment: Document assessment results
            correlation_id: Optional correlation ID for tracking
            
        Returns:
            Dict containing updated project insights
        """
        try:
            if not correlation_id:
                correlation_id = str(uuid.uuid4())
            
            logger.info(f"Updating project insights for {project_id} [corr_id={correlation_id}]")
            
            client = await get_service_client()
            
            # Get existing project metadata to retrieve previous assessments
            try:
                project_meta_response = await client.get(
                    "project",
                    f"/api/projects/{project_id}",
                    headers={"X-Correlation-ID": correlation_id} if correlation_id else {}
                )
                
                if project_meta_response.get("status_code") == 200:
                    project_data = project_meta_response
                    existing_insights = project_data.get("metadata", {}).get("insights", {})
                else:
                    existing_insights = {}
            except Exception as e:
                logger.warning(f"Could not retrieve project metadata: {e}")
                existing_insights = {}
            
            # Aggregate topics, entities, and insights from all assessments
            all_topics = existing_insights.get("all_topics", [])
            all_entities = existing_insights.get("all_entities", [])
            all_insights = existing_insights.get("all_insights", [])
            document_count = existing_insights.get("documents_assessed", 0) + 1
            
            # Add new assessment data
            if assessment.get("status") == "success":
                assessment_data = assessment.get("assessment", {})
                
                all_topics.extend(assessment_data.get("topics", []))
                all_entities.extend(assessment_data.get("entities", []))
                all_insights.extend(assessment_data.get("insights", []))
                
                # Deduplicate and count frequency
                from collections import Counter
                topic_freq = Counter(all_topics)
                entity_freq = Counter(all_entities)
                
                # Keep top items
                top_topics = [item for item, count in topic_freq.most_common(20)]
                top_entities = [item for item, count in entity_freq.most_common(30)]
                
                # Calculate aggregate metrics
                avg_migration_relevance = existing_insights.get("avg_migration_relevance", 0)
                new_relevance = assessment_data.get("migration_relevance", 5)
                updated_avg_relevance = ((avg_migration_relevance * (document_count - 1)) + new_relevance) / document_count
                
                # Build updated insights
                updated_insights = {
                    "documents_assessed": document_count,
                    "all_topics": top_topics,
                    "all_entities": top_entities,
                    "all_insights": all_insights[-50:],  # Keep last 50 insights
                    "avg_migration_relevance": round(updated_avg_relevance, 2),
                    "last_updated": datetime.now().isoformat(),
                    "correlation_id": correlation_id
                }
                
                # Call LLM for cross-document pattern analysis (if we have multiple docs)
                if document_count >= 3:
                    try:
                        pattern_prompt = f"""Analyze the following aggregated data from {document_count} documents in a cloud migration project:

Top Topics: {', '.join(top_topics[:15])}
Key Entities: {', '.join(top_entities[:20])}
Recent Insights: {'; '.join(all_insights[-10:])}
Average Migration Relevance: {updated_avg_relevance:.1f}/10

Please identify:
1. Common themes across documents
2. Cross-document relationships or dependencies
3. Migration patterns or anti-patterns
4. Priority recommendations for the migration project

Respond in JSON format:
{{
  "common_themes": ["theme1", "theme2", ...],
  "relationships": ["relationship1", "relationship2", ...],
  "patterns": ["pattern1", "pattern2", ...],
  "recommendations": ["rec1", "rec2", ...]
}}"""

                        pattern_response = await client.post(
                            "llm",
                            "/api/llm/process",
                            json={
                                "process_type": "cross_document_analysis",
                                "prompt": pattern_prompt,
                                "project_id": project_id,
                                "metadata": {
                                    "document_count": document_count,
                                    "top_topics_count": len(top_topics[:15]),
                                    "key_entities_count": len(top_entities[:20]),
                                    "correlation_id": correlation_id
                                }
                            },
                            headers={"X-Correlation-ID": correlation_id} if correlation_id else {},
                            timeout=180  # Increased timeout for cross-document analysis (3 minutes)
                        )
                        
                        if pattern_response.get("status_code") == 200:
                            pattern_result = pattern_response.get("result", {})
                            pattern_content = pattern_result.get("output", "") if isinstance(pattern_result, dict) else str(pattern_result)
                            
                            # Parse pattern analysis
                            try:
                                if "```json" in pattern_content:
                                    pattern_content = pattern_content.split("```json")[1].split("```")[0]
                                elif "```" in pattern_content:
                                    pattern_content = pattern_content.split("```")[1].split("```")[0]
                                
                                pattern_data = json.loads(pattern_content.strip())
                                updated_insights["cross_document_analysis"] = pattern_data
                            except json.JSONDecodeError:
                                logger.warning("Failed to parse pattern analysis JSON")
                    except Exception as e:
                        logger.warning(f"Cross-document pattern analysis failed: {e}")
                
                # Update project metadata with new insights
                try:
                    metadata_update = {
                        "metadata": {
                            "insights": updated_insights
                        }
                    }
                    
                    await client.patch(
                        "project",
                        f"/api/projects/{project_id}",
                        json=metadata_update,
                        headers={"X-Correlation-ID": correlation_id} if correlation_id else {}
                    )
                    
                    logger.info(f"Project insights updated for {project_id} ({document_count} documents)")
                except Exception as e:
                    logger.warning(f"Failed to update project metadata: {e}")
                
                return {
                    "status": "success",
                    "project_id": project_id,
                    "insights": updated_insights,
                    "correlation_id": correlation_id
                }
            else:
                logger.warning(f"Assessment not successful, skipping insights update")
                return {
                    "status": "skipped",
                    "message": "Assessment not successful",
                    "correlation_id": correlation_id
                }
            
        except Exception as e:
            logger.error(f"Project insights update failed: {e}")
            return {
                "status": "error",
                "message": f"Insights update failed: {str(e)}",
                "correlation_id": correlation_id
            }

