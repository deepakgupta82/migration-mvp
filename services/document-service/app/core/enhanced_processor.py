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
import httpx
import json
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# Import structured processor
from .structured_processor import StructuredDocumentProcessor, ProcessingResult

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
        
        # Service URLs
        self.vector_url = os.getenv("VECTOR_SERVICE_URL", "http://localhost:8005")
        self.graph_url = os.getenv("GRAPH_SERVICE_URL", "http://localhost:8006")
        self.websocket_url = os.getenv("WEBSOCKET_SERVICE_URL", "http://localhost:8009")
        self.storage_url = os.getenv("STORAGE_SERVICE_URL", "http://localhost:8010")
        
        # Configuration
        self.http_timeout = httpx.Timeout(60.0, connect=10.0)
        self.auth_token = os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')
        
        # Processing options
        self.enable_vector_integration = os.getenv("ENABLE_VECTOR_INTEGRATION", "true").lower() == "true"
        self.enable_graph_integration = os.getenv("ENABLE_GRAPH_INTEGRATION", "true").lower() == "true"
        self.enable_websocket_notifications = os.getenv("ENABLE_WEBSOCKET_NOTIFICATIONS", "true").lower() == "true"
        
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
        
        # Step 3: Conversion & Structuring (unstructured.io PRIMARY)
        try:
            # Send WebSocket notification - Processing Started
            await self._send_websocket_notification(
                project_id, correlation_id, "document_processing_started",
                {"filename": filename, "stage": "conversion_structuring"}
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
            
            await self._save_structured_output(
                project_id, structured_filename, processing_result, correlation_id
            )
            
            logger.info(f"Structured processing completed: {len(processing_result.elements)} elements extracted")
            
            # Step 4 & 5: Parallel Service Integration for Performance
            if self.enable_parallel_processing:
                # Run vector and graph integration in parallel
                integration_tasks = []
                
                if self.enable_vector_integration:
                    integration_tasks.append(self._integrate_vector_service(
                        project_id, processing_result, correlation_id
                    ))
                
                if self.enable_graph_integration:
                    integration_tasks.append(self._integrate_graph_service(
                        project_id, processing_result, correlation_id
                    ))
                
                # Wait for all integrations to complete
                if integration_tasks:
                    integration_results = await asyncio.gather(*integration_tasks, return_exceptions=True)
                    
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
                        graph_result = integration_results[result_index]
                        if isinstance(graph_result, Exception):
                            graph_status = {"status": "error", "message": str(graph_result)}
                        elif isinstance(graph_result, dict):
                            graph_status = graph_result
                else:
                    vector_status = {"status": "disabled"}
                    graph_status = {"status": "disabled"}
            else:
                # Sequential processing (original behavior)
                # Step 4: Semantic Embedding (Vector Service Integration)
                vector_status = await self._integrate_vector_service(
                    project_id, processing_result, correlation_id
                )
                
                # Step 5: Entity & Relationship Extraction (Graph Service Integration)
                graph_status = await self._integrate_graph_service(
                    project_id, processing_result, correlation_id
                )
            
            # Step 6: Stats Update & Completion Notification
            
            # Extract and notify stats service of embeddings and graph updates
            await self._notify_stats_service(
                project_id, vector_status, graph_status, correlation_id
            )
            
            await self._send_websocket_notification(
                project_id, correlation_id, "document_processing_completed",
                {
                    "filename": filename,
                    "structured_output": structured_filename,
                    "elements_extracted": len(processing_result.elements),
                    "vector_integration": vector_status,
                    "graph_integration": graph_status,
                    "processing_time": processing_result.processing_stats.get("processing_time_seconds", 0)
                }
            )
            
            return {
                "status": "success",
                "filename": filename,
                "structured_output": structured_filename,
                "elements_extracted": len(processing_result.elements),
                "element_types": processing_result.processing_stats.get("element_types", {}),
                "processing_time": processing_result.processing_stats.get("processing_time_seconds", 0),
                "vector_integration": vector_status,
                "graph_integration": graph_status,
                "correlation_id": correlation_id,
                "processing_result": processing_result
            }
            
        except Exception as e:
            logger.error(f"Enhanced processing failed for {filename}: {e}")
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
        correlation_id: str
    ):
        """Save structured JSONL output to Storage Service"""
        try:
            jsonl_content = processing_result.to_jsonl()
            
            async with httpx.AsyncClient(timeout=self.http_timeout) as client:
                # Upload to Storage Service structured folder
                files_data = {
                    'files': (filename, jsonl_content.encode('utf-8'), 'application/jsonl')
                }
                
                headers = {
                    "Authorization": f"Bearer {self.auth_token}",
                    "X-Correlation-ID": correlation_id
                }
                
                response = await client.post(
                    f"{self.storage_url}/api/storage/projects/{project_id}/upload/structured",
                    files=files_data,
                    headers=headers
                )
                
                if response.status_code == 200:
                    logger.info(f"Saved structured output: {filename}")
                else:
                    logger.error(f"Failed to save structured output: {response.status_code} - {response.text[:500]}")
                    # Don't fail the entire process if structured storage fails
                    # This allows the document to still be processed successfully
                    
        except Exception as e:
            logger.error(f"Error saving structured output: {e}")
    
    async def _integrate_vector_service(
        self,
        project_id: str,
        processing_result: ProcessingResult,
        correlation_id: str
    ) -> Dict[str, Any]:
        """
        Step 4: Semantic Embedding Integration
        Send structured elements to Vector Service for smart chunking and embedding
        """
        if not self.enable_vector_integration:
            return {"status": "disabled", "message": "Vector integration disabled"}
        
        try:
            # Prepare structured elements for vector processing
            vector_documents = []
            
            for element in processing_result.elements:
                # Smart chunking based on element types
                if element.type in ['title', 'header', 'narrative_text', 'list_item']:
                    # These elements are good for embedding
                    vector_documents.append({
                        "element_id": element.element_id,
                        "content": element.text,
                        "element_type": element.type,
                        "page_number": element.page_number,
                        "hierarchy_level": element.hierarchy_level,
                        "semantic_tags": element.semantic_tags,
                        "metadata": {
                            "filename": processing_result.document_metadata.filename,
                            "coordinates": element.coordinates,
                            "confidence_score": element.confidence_score
                        }
                    })
            
            if not vector_documents:
                return {"status": "skipped", "message": "No suitable elements for vectorization"}
            
            # Send to Vector Service for processing
            async with httpx.AsyncClient(timeout=self.http_timeout) as client:
                payload = {
                    "documents": vector_documents,
                    "processing_type": "structured",
                    "source": "enhanced_document_processor"
                }
                
                headers = {
                    "Authorization": f"Bearer {self.auth_token}",
                    "X-Correlation-ID": correlation_id
                }
                
                response = await client.post(
                    f"{self.vector_url}/api/vectors/projects/{project_id}/process-structured",
                    json=payload,
                    headers=headers
                )
                
                if response.status_code == 200:
                    result = response.json()
                    embeddings_created = result.get("embeddings_created", 0)
                    logger.info(f"Vector integration successful: {len(vector_documents)} elements processed, {embeddings_created} embeddings created")
                    return {
                        "status": "success",
                        "elements_processed": len(vector_documents),
                        "embeddings_created": embeddings_created
                    }
                else:
                    logger.warning(f"Vector service returned {response.status_code}: {response.text[:300]}")
                    return {
                        "status": "error",
                        "message": f"Vector service error: {response.status_code}"
                    }
                    
        except Exception as e:
            logger.error(f"Vector integration failed: {e}")
            return {"status": "error", "message": str(e)}
    
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
        if not self.enable_graph_integration:
            return {"status": "disabled", "message": "Graph integration disabled"}
        
        try:
            # Prepare structured content for graph processing
            # Focus on title, narrative_text, and list_item elements for entity extraction
            content_elements = []
            for element in processing_result.elements:
                if element.type in ['title', 'narrative_text', 'list_item'] and len(element.text.strip()) > 10:
                    content_elements.append({
                        "element_id": element.element_id,
                        "content": element.text,
                        "element_type": element.type,
                        "page_number": element.page_number,
                        "hierarchy_level": element.hierarchy_level,
                        "metadata": element.metadata
                    })
            
            if not content_elements:
                return {"status": "skipped", "message": "No suitable elements for entity extraction"}
            
            # Send to Graph Service for processing
            async with httpx.AsyncClient(timeout=self.http_timeout) as client:
                payload = {
                    "document_id": str(uuid.uuid4()),
                    "filename": processing_result.document_metadata.filename,
                    "structured_elements": content_elements,
                    "processing_type": "structured_extraction",
                    "extract_entities": True,
                    "extract_relationships": True
                }
                
                headers = {
                    "Authorization": f"Bearer {self.auth_token}",
                    "X-Correlation-ID": correlation_id
                }
                
                response = await client.post(
                    f"{self.graph_url}/api/graphs/projects/{project_id}/process-structured",
                    json=payload,
                    headers=headers
                )
                
                if response.status_code == 200:
                    result = response.json()
                    entities_extracted = result.get("entities_extracted", 0)
                    relationships_found = result.get("relationships_found", 0)
                    logger.info(f"Graph integration successful: {len(content_elements)} elements analyzed, {entities_extracted} entities, {relationships_found} relationships")
                    return {
                        "status": "success",
                        "elements_analyzed": len(content_elements),
                        "entities_extracted": entities_extracted,
                        "relationships_found": relationships_found
                    }
                else:
                    logger.warning(f"Graph service returned {response.status_code}: {response.text[:300]}")
                    return {
                        "status": "error",
                        "message": f"Graph service error: {response.status_code}"
                    }
                    
        except Exception as e:
            logger.error(f"Graph integration failed: {e}")
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
            backend_url = os.getenv("BACKEND_URL", "http://localhost:8000")
            
            # Notify embeddings added if vector integration was successful
            if vector_status.get("status") == "success":
                embeddings_count = vector_status.get("embeddings_created", 0)
                if embeddings_count > 0:
                    async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                        await client.post(
                            f"{backend_url}/api/stats/events",
                            json={
                                "project_id": project_id,
                                "event_type": "embeddings_added",
                                "additional_data": {
                                    "embeddings_count": embeddings_count,
                                    "source": "enhanced_workflow"
                                },
                                "timestamp": datetime.now().isoformat()
                            },
                            headers={
                                "Authorization": f"Bearer {self.auth_token}",
                                "Content-Type": "application/json",
                                "X-Correlation-ID": correlation_id
                            }
                        )
                    logger.debug(f"Notified stats service: embeddings_added - {embeddings_count}")
            
            # Notify graph updated if graph integration was successful
            if graph_status.get("status") == "success":
                entities_extracted = graph_status.get("entities_extracted", 0)
                relationships_found = graph_status.get("relationships_found", 0)
                if entities_extracted > 0 or relationships_found > 0:
                    async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                        await client.post(
                            f"{backend_url}/api/stats/events",
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
                            headers={
                                "Authorization": f"Bearer {self.auth_token}",
                                "Content-Type": "application/json",
                                "X-Correlation-ID": correlation_id
                            }
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
            backend_url = os.getenv("BACKEND_URL", "http://localhost:8000")
            
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
            
            # Notify aggregated embeddings
            if total_embeddings > 0:
                async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                    await client.post(
                        f"{backend_url}/api/stats/events",
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
                        headers={
                            "Authorization": f"Bearer {self.auth_token}",
                            "Content-Type": "application/json",
                            "X-Correlation-ID": correlation_id
                        }
                    )
                logger.info(f"Notified batch embeddings: {total_embeddings} from {files_processed} files")
            
            # Notify aggregated graph updates
            if total_entities > 0 or total_relationships > 0:
                async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                    await client.post(
                        f"{backend_url}/api/stats/events",
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
                        headers={
                            "Authorization": f"Bearer {self.auth_token}",
                            "Content-Type": "application/json",
                            "X-Correlation-ID": correlation_id
                        }
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
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                payload = {
                    "project_id": project_id,
                    "correlation_id": correlation_id,
                    "event_type": event_type,
                    "timestamp": datetime.now().isoformat(),
                    "data": data
                }
                
                headers = {
                    "Authorization": f"Bearer {self.auth_token}",
                    "X-Correlation-ID": correlation_id
                }
                
                response = await client.post(
                    f"{self.websocket_url}/api/websocket/broadcast",
                    json=payload,
                    headers=headers
                )
                
                if response.status_code == 200:
                    logger.debug(f"WebSocket notification sent: {event_type}")
                else:
                    logger.warning(f"WebSocket notification failed: {response.status_code}")
                    
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
        
        # Send batch started notification
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
                await self._send_websocket_notification(
                    project_id, correlation_id, "file_processing_started",
                    {
                        "filename": filename,
                        "progress": f"{i+1}/{len(filenames)}",
                        "percentage": round((i / len(filenames)) * 100, 1)
                    }
                )
                
                # Process with enhanced workflow
                result = await self.process_document_enhanced(
                    file_path=file_path,
                    filename=filename,
                    project_id=project_id,
                    correlation_id=correlation_id,
                    extract_images=extract_images,
                    extract_tables=extract_tables,
                    include_coordinates=include_coordinates
                )
                
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
        async with httpx.AsyncClient(timeout=self.http_timeout) as client:
            headers = {
                "Authorization": f"Bearer {self.auth_token}",
                "X-Correlation-ID": correlation_id
            }
            
            # Fix: Use correct download endpoint
            # Was: /files/uploads_raw/{filename} (405 Method Not Allowed)
            # Now: /download/uploads_raw/{filename} (correct)
            download_url = f"{self.storage_url}/api/storage/projects/{project_id}/download/uploads_raw/{filename}"
            
            logger.info(f"Downloading file from: {download_url}")
            
            response = await client.get(download_url, headers=headers)
            
            if response.status_code != 200:
                raise Exception(f"Failed to download file from storage: {response.status_code} - {response.text}")
            
            # Save to temporary file
            suffix = Path(filename).suffix
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                tmp_file.write(response.content)
                temp_path = tmp_file.name
            
            logger.info(f"File downloaded to temporary location: {temp_path}")
            return temp_path
    
    def get_integration_status(self) -> Dict[str, Any]:
        """Get current integration configuration status"""
        return {
            "vector_integration": self.enable_vector_integration,
            "graph_integration": self.enable_graph_integration,
            "websocket_notifications": self.enable_websocket_notifications,
            "service_urls": {
                "vector_service": self.vector_url,
                "graph_service": self.graph_url,
                "websocket_service": self.websocket_url,
                "storage_service": self.storage_url
            }
        }
