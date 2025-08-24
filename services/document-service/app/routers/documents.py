"""
Document Processing Router
Handles document upload, processing, and status endpoints
"""

from fastapi import APIRouter, HTTPException, Form, File, UploadFile, BackgroundTasks, Request
from fastapi.responses import JSONResponse
from typing import List, Optional
import uuid
import tempfile
import os
import logging
from datetime import datetime
import asyncio

from ..core.document_processor import DocumentProcessor
from ..core.semantic_chunking import chunk_text as chunk_text_semantic
from ..core.enrichment import enrich_text
from ..core.structured_processor import StructuredDocumentProcessor

logger = logging.getLogger("document-service.router")
router = APIRouter()

from pydantic import BaseModel

# Initialize document processors
processor = DocumentProcessor()
structured_processor = StructuredDocumentProcessor()

# Pydantic models for request/response
class ProcessRequest(BaseModel):
    file_names: Optional[List[str]] = None
    reprocess: bool = False

class ProcessResponse(BaseModel):
    project_id: str
    job_id: str
    status: str
    files_to_process: List[str]
    message: str
    started_at: str

class FileStatus(BaseModel):
    filename: str
    status: str
    conversion_strategy: Optional[str] = None
    timestamp: Optional[str] = None
    error: Optional[str] = None

class ProcessingStatus(BaseModel):
    project_id: str
    job_id: str
    status: str
    total_files: int
    processed_files: int
    failed_files: int
    current_file: Optional[str] = None
    files_status: List[FileStatus] = []
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    last_updated: Optional[str] = None

def _chunk_markdown_text(text: str) -> List[str]:
    """Chunk markdown text using semantic/paragraph strategy helper.
    Strategy can be set via CHUNKING_STRATEGY env: semantic | paragraph | rule_based
    """
    try:
        from app.core.config_client import cfg_get
        strategy = str(cfg_get(["document_service", "chunking_strategy"], os.getenv("CHUNKING_STRATEGY", "paragraph")))
    except Exception:
        strategy = os.getenv("CHUNKING_STRATEGY", "paragraph")
    try:
        return chunk_text_semantic(text, strategy=strategy)
    except Exception as e:
        logger.warning(f"Semantic chunking failed ({e}); falling back to simple paragraph split")
        # minimal fallback
        return [p.strip() for p in text.split("\n\n") if p.strip()]

@router.post("/{project_id}/upload")
async def upload_documents(
    project_id: str,
    files: List[UploadFile] = File(...),
    request: Request = None,
):
    """Upload documents to Storage Service (port 8010)"""
    try:
        import httpx

        uploaded_files = []

        # Create HTTP client to call Storage Service
        async with httpx.AsyncClient(timeout=processor.http_timeout) as client:
            corr_id = None
            try:
                if request is not None:
                    corr_id = request.headers.get("X-Correlation-ID")
            except Exception:
                pass
            for file in files:
                if not file.filename:
                    continue

                # Read file content
                content = await file.read()

                # Prepare multipart form data for Storage Service
                files_data = {
                    'files': (file.filename, content, file.content_type or 'application/octet-stream')
                }

                # Call Storage Service upload endpoint
                headers = {
                    "Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"
                }
                if corr_id:
                    headers["X-Correlation-ID"] = corr_id
                storage_response = await client.post(
                    f"{processor.storage_url}/api/storage/projects/{project_id}/upload/uploads_raw",
                    files=files_data,
                    headers=headers,
                )

                if storage_response.status_code == 200:
                    uploaded_files.append({
                        "filename": file.filename,
                        "size": len(content),
                        "uploaded_at": datetime.now().isoformat()
                    })
                    logger.info(f"Uploaded {file.filename} to project {project_id}")
                else:
                    logger.error(f"Storage service upload failed for {file.filename}: {storage_response.status_code}")
                    raise HTTPException(
                        status_code=500,
                        detail=f"Storage service upload failed: {storage_response.status_code}"
                    )

        return {
            "project_id": project_id,
            "uploaded_files": uploaded_files,
            "total_uploaded": len(uploaded_files),
            "message": f"Successfully uploaded {len(uploaded_files)} files"
        }

    except Exception as e:
        logger.error(f"Upload failed for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.post("/{project_id}/process-all", response_model=ProcessResponse)
async def process_all_documents(
    project_id: str, 
    background_tasks: BackgroundTasks,
    request_data: ProcessRequest = ProcessRequest(),
    request: Request = None,
):
    """Process all uploaded documents"""
    try:
        # Call Storage Service to get uploaded files (NO BACKEND IMPORTS!)
        import httpx
        
        async with httpx.AsyncClient(timeout=processor.http_timeout) as client:
            corr_id = None
            try:
                if request is not None:
                    corr_id = request.headers.get("X-Correlation-ID")
            except Exception:
                pass
            headers = {
                "Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"
            }
            if corr_id:
                headers["X-Correlation-ID"] = corr_id
            response = await client.get(
                f"{processor.storage_url}/api/storage/projects/{project_id}/files/uploads_raw",
                headers=headers,
            )
            
            if response.status_code == 200:
                storage_result = response.json()
                uploaded_files = [f["filename"] for f in storage_result.get("files", [])]
            else:
                uploaded_files = []
        
        if not uploaded_files:
            raise HTTPException(status_code=404, detail="No uploaded files found for processing")
        
        # Generate job ID
        job_id = str(uuid.uuid4())
        
        logger.info(f"Starting processing job {job_id} for project {project_id}: {len(uploaded_files)} files")
        
        # Initialize processing status
        await processor.update_processing_status(project_id, job_id, {
            "status": "started",
            "total_files": len(uploaded_files),
            "processed_files": 0,
            "failed_files": 0,
            "files_to_process": uploaded_files,
            "started_at": datetime.now().isoformat()
        })
        
        # Start background processing
        corr_id = None
        try:
            if request is not None:
                corr_id = request.headers.get("X-Correlation-ID")
        except Exception:
            pass
        background_tasks.add_task(
            _process_files_background, 
            project_id, 
            uploaded_files, 
            request_data.reprocess, 
            job_id,
            corr_id
        )
        
        return ProcessResponse(
            project_id=project_id,
            job_id=job_id,
            status="started",
            files_to_process=uploaded_files,
            message=f"Started processing {len(uploaded_files)} files in background",
            started_at=datetime.now().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Failed to start processing for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start processing: {str(e)}")

@router.post("/{project_id}/process-selected", response_model=ProcessResponse)
async def process_selected_documents(
    project_id: str,
    background_tasks: BackgroundTasks,
    request_data: ProcessRequest,
    request: Request = None,
):
    """Process selected documents"""
    if not request_data.file_names:
        raise HTTPException(status_code=400, detail="No files specified for processing")
    
    try:
        # Call Storage Service to verify files exist (NO BACKEND IMPORTS!)
        import httpx
        
        async with httpx.AsyncClient(timeout=processor.http_timeout) as client:
            corr_id = None
            try:
                if request is not None:
                    corr_id = request.headers.get("X-Correlation-ID")
            except Exception:
                pass
            headers = {
                "Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"
            }
            if corr_id:
                headers["X-Correlation-ID"] = corr_id
            response = await client.get(
                f"{processor.storage_url}/api/storage/projects/{project_id}/files/uploads_raw",
                headers=headers,
            )
            
            if response.status_code == 200:
                storage_result = response.json()
                uploaded_files = [f["filename"] for f in storage_result.get("files", [])]
            else:
                uploaded_files = []
        
        # Verify selected files exist
        missing_files = [f for f in request_data.file_names if f not in uploaded_files]
        if missing_files:
            raise HTTPException(
                status_code=404, 
                detail=f"Files not found: {', '.join(missing_files)}"
            )
        
        # Generate job ID
        job_id = str(uuid.uuid4())
        
        logger.info(f"Starting selective processing job {job_id} for project {project_id}: {len(request_data.file_names)} files")
        
        # Initialize processing status
        await processor.update_processing_status(project_id, job_id, {
            "status": "started",
            "total_files": len(request_data.file_names),
            "processed_files": 0,
            "failed_files": 0,
            "files_to_process": request_data.file_names,
            "started_at": datetime.now().isoformat()
        })
        
        # Start background processing
        corr_id = None
        try:
            if request is not None:
                corr_id = request.headers.get("X-Correlation-ID")
        except Exception:
            pass
        background_tasks.add_task(
            _process_files_background, 
            project_id, 
            request_data.file_names, 
            request_data.reprocess, 
            job_id,
            corr_id
        )
        
        return ProcessResponse(
            project_id=project_id,
            job_id=job_id,
            status="started",
            files_to_process=request_data.file_names,
            message=f"Started processing {len(request_data.file_names)} selected files",
            started_at=datetime.now().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Failed to start selective processing for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start processing: {str(e)}")

@router.get("/{project_id}/status/{job_id}", response_model=ProcessingStatus)
async def get_processing_status(project_id: str, job_id: str):
    """Get processing status for a job"""
    try:
        status = await processor.get_processing_status(project_id, job_id)
        
        if status.get("status") == "not_found":
            raise HTTPException(status_code=404, detail="Processing job not found")
        
        # Ensure required fields are present for Pydantic validation
        status["project_id"] = project_id
        status["job_id"] = job_id
        
        return ProcessingStatus(**status)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get processing status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")

async def _process_files_background(project_id: str, file_names: List[str], reprocess: bool, job_id: str, correlation_id: Optional[str] = None):
    """Background task to process files - uses HTTP calls to other services and propagates correlation ID"""
    logger.info(f"Background processing started for job {job_id}: {len(file_names)} files")

    try:
        # Use HTTP calls to Storage Service instead of direct imports
        import httpx
        import json

        processed_count = 0
        failed_count = 0
        files_status: List[FileStatus] = []

        async with httpx.AsyncClient(timeout=processor.http_timeout) as client:
            for filename in file_names:
                try:
                    # Update current processing status
                    await processor.update_processing_status(project_id, job_id, {
                        "current_file": filename,
                        "processed_files": processed_count,
                        "failed_files": failed_count
                    })

                    # Download file from Storage Service
                    headers = {
                        "Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"
                    }
                    if correlation_id:
                        headers["X-Correlation-ID"] = correlation_id
                    download_response = await client.get(
                        f"{processor.storage_url}/api/storage/projects/{project_id}/download/uploads_raw/{filename}",
                        headers=headers,
                    )

                    if download_response.status_code != 200:
                        raise Exception(f"Failed to download file from storage: {download_response.status_code}")

                    # Save to temporary file
                    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                        tmp_file.write(download_response.content)
                        tmp_file_path = tmp_file.name

                    try:
                        # Process the document using DocumentProcessor
                        result = await processor.convert_document_to_markdown(
                            tmp_file_path, filename, project_id, reprocess, correlation_id=correlation_id
                        )

                        # Upload processed markdown back to Storage Service
                        if result.get("content"):
                            md_filename = result["md_filename"]

                            # Enrichment (language, keywords, optional summary via LLM if enabled)
                            try:
                                enrichment = await enrich_text(result.get("content", ""), project_id=project_id, corr_id=correlation_id)
                            except Exception as e:
                                enrichment = {}
                                logger.warning(f"Enrichment failed for {filename}: {type(e).__name__}: {e}")

                            # Upload processed markdown
                            files_data = {
                                'files': (md_filename, result["content"].encode('utf-8'), 'text/markdown')
                            }

                            headers = {
                                "Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"
                            }
                            if correlation_id:
                                headers["X-Correlation-ID"] = correlation_id
                            upload_response = await client.post(
                                f"{processor.storage_url}/api/storage/projects/{project_id}/upload/uploads_parsed",
                                files=files_data,
                                headers=headers,
                            )

                            if upload_response.status_code != 200:
                                logger.warning(f"Failed to upload processed markdown: {upload_response.status_code} body={upload_response.text[:200]}")

                            # Save metadata
                            metadata = {
                                "original_filename": filename,
                                "md_filename": md_filename,
                                "conversion_strategy": result.get("conversion_strategy"),
                                "timestamp": result.get("timestamp"),
                                "file_size": result.get("file_size"),
                                "content_length": result.get("content_length"),
                                "status": result.get("status"),
                                "enrichment": enrichment or {}
                            }

                            metadata_filename = os.path.splitext(filename)[0] + "_metadata.json"
                            metadata_json = json.dumps(metadata, indent=2)

                            # Upload metadata to Storage Service
                            metadata_files_data = {
                                'files': (metadata_filename, metadata_json.encode('utf-8'), 'application/json')
                            }

                            headers = {
                                "Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"
                            }
                            if correlation_id:
                                headers["X-Correlation-ID"] = correlation_id
                            metadata_response = await client.post(
                                f"{processor.storage_url}/api/storage/projects/{project_id}/upload/metadata",
                                files=metadata_files_data,
                                headers=headers,
                            )

                            if metadata_response.status_code != 200:
                                logger.warning(f"Failed to upload metadata: {metadata_response.status_code} body={metadata_response.text[:200]}")

                        # Check if conversion actually succeeded
                        conversion_status = result.get("status", "error")
                        conversion_strategy = result.get("conversion_strategy", "unknown")

                        if conversion_status == "success" and conversion_strategy != "error_document":
                            # Ensure Vector collection exists
                            try:
                                headers = {
                                    "Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"
                                }
                                if correlation_id:
                                    headers["X-Correlation-ID"] = correlation_id
                                coll_resp = await client.post(
                                    f"{processor.vector_url}/api/vectors/projects/{project_id}/collection",
                                    headers=headers,
                                )
                                if coll_resp.status_code != 200:
                                    logger.warning(f"Vector collection init returned {coll_resp.status_code}")
                            except Exception as e:
                                logger.warning(f"Vector collection init failed: {e}")

                            # Chunk markdown and send to Vector Service for embeddings
                            content_text = result.get("content", "")
                            # Offload potentially heavy chunking to a thread so the event loop can serve /status
                            chunks = await asyncio.to_thread(_chunk_markdown_text, content_text)
                            # Enforce optional limit on chunks to control load
                            if getattr(processor, "max_chunks", 0):
                                chunks = chunks[: max(0, int(processor.max_chunks))]
                            logger.info(f"Chunked {filename} into {len(chunks)} chunks for embedding")
                            if not chunks:
                                logger.warning(f"No chunks produced for {filename}; skipping embeddings")
                            else:
                                # Batch embeddings to prevent timeouts
                                batch_size = max(1, int(getattr(processor, "vector_batch_size", 50)))
                                total = len(chunks)
                                embedded = 0
                                for start in range(0, total, batch_size):
                                    batch = chunks[start:start + batch_size]
                                    docs_payload = {
                                        "documents": [
                                            {
                                                "id": f"{os.path.splitext(md_filename)[0]}_{start + i}",
                                                "content": ch,
                                                "filename": md_filename,
                                                "source": "document-service"
                                            }
                                            for i, ch in enumerate(batch)
                                        ]
                                    }
                                    # simple retry loop
                                    attempt = 0
                                    while attempt < 3:
                                        try:
                                            vec_resp = await client.post(
                                                f"{processor.vector_url}/api/vectors/projects/{project_id}/documents/sync",
                                                json=docs_payload,
                                                headers=headers,
                                            )
                                            if vec_resp.status_code == 200:
                                                embedded += len(batch)
                                                break
                                            else:
                                                logger.warning(f"Vector add_documents batch returned {vec_resp.status_code}: {vec_resp.text[:300]}")
                                        except Exception as e:
                                            logger.warning(f"Vector add_documents batch failed (attempt {attempt+1}/3): {type(e).__name__}: {e}")
                                        attempt += 1
                                        # small backoff
                                        await asyncio.sleep(0.5 * attempt)
                                logger.info(f"Embedded {embedded}/{total} chunks for {filename} in batches of {batch_size}")

                            # Trigger entity extraction on full markdown via Graph Service
                            try:
                                graph_req = {
                                    "document_content": content_text,
                                    "filename": md_filename,
                                    "document_id": os.path.splitext(md_filename)[0]
                                }
                                headers = {
                                    "Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"
                                }
                                if correlation_id:
                                    headers["X-Correlation-ID"] = correlation_id
                                graph_resp = await client.post(
                                    f"{processor.graph_url}/api/graphs/projects/{project_id}/extract",
                                    json=graph_req,
                                    headers=headers,
                                )
                                if graph_resp.status_code != 200:
                                    logger.warning(f"Graph extract returned {graph_resp.status_code}: {graph_resp.text[:500]}")
                                else:
                                    logger.info(f"Graph extraction queued for {filename}")
                            except Exception as e:
                                logger.warning(f"Graph extraction call failed: {type(e).__name__}: {e}")

                            processed_count += 1
                            files_status.append(FileStatus(
                                filename=filename,
                                status="success",
                                conversion_strategy=conversion_strategy,
                                timestamp=result.get("timestamp")
                            ))
                            logger.info(f"Successfully processed {filename} for project {project_id} using {conversion_strategy}")
                        else:
                            failed_count += 1
                            error_msg = f"Conversion failed - strategy: {conversion_strategy}"
                            files_status.append(FileStatus(
                                filename=filename,
                                status="error",
                                error=error_msg,
                                conversion_strategy=conversion_strategy,
                                timestamp=result.get("timestamp")
                            ))
                            logger.error(f"Failed to process {filename} for project {project_id}: {error_msg}")

                        # Note: WebSocket broadcasting will be handled by other services
                        # Document Service should focus only on document processing

                    finally:
                        # Clean up temp file
                        os.unlink(tmp_file_path)

                except Exception as e:
                    failed_count += 1
                    files_status.append(FileStatus(
                        filename=filename,
                        status="error",
                        error=str(e),
                        timestamp=datetime.now().isoformat()
                    ))
                    logger.error(f"Failed to process {filename}: {type(e).__name__}: {e}")

        # Update final status
        await processor.update_processing_status(project_id, job_id, {
            "status": "completed" if failed_count == 0 else "completed_with_errors",
            "processed_files": processed_count,
            "failed_files": failed_count,
            "files_status": [status.dict() for status in files_status],
            "completed_at": datetime.now().isoformat(),
            "current_file": None
        })

        logger.info(f"Background processing completed for job {job_id}: {processed_count} success, {failed_count} failed")

    except Exception as e:
        logger.error(f"Background processing failed for job {job_id}: {e}")

        # Update error status
        await processor.update_processing_status(project_id, job_id, {
            "status": "failed",
            "error": str(e),
            "completed_at": datetime.now().isoformat()
        })

# Structured Processing Endpoints (Phase 2.3 Enhancement)

class StructuredProcessRequest(BaseModel):
    extract_images: bool = True
    extract_tables: bool = True
    include_coordinates: bool = True
    output_format: str = "jsonl"  # jsonl or json

class StructuredProcessResponse(BaseModel):
    project_id: str
    filename: str
    status: str
    processing_time: float
    total_elements: int
    element_types: dict
    output_file: Optional[str] = None
    errors: List[str] = []
    warnings: List[str] = []

@router.post("/{project_id}/structured-process/{filename}", response_model=StructuredProcessResponse)
async def process_document_structured(
    project_id: str,
    filename: str,
    request_data: StructuredProcessRequest = StructuredProcessRequest(),
    request: Request = None
):
    """Process a single document with structured JSONL output"""
    try:
        import httpx
        
        # Get correlation ID
        corr_id = None
        try:
            if request is not None:
                corr_id = request.headers.get("X-Correlation-ID")
        except Exception:
            pass
        
        logger.info(f"Starting structured processing for {filename} in project {project_id}")
        
        # Download file from Storage Service
        async with httpx.AsyncClient(timeout=processor.http_timeout) as client:
            headers = {
                "Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"
            }
            if corr_id:
                headers["X-Correlation-ID"] = corr_id
            
            download_response = await client.get(
                f"{processor.storage_url}/api/storage/projects/{project_id}/files/uploads_raw/{filename}",
                headers=headers
            )
            
            if download_response.status_code != 200:
                raise HTTPException(
                    status_code=404,
                    detail=f"File {filename} not found in project {project_id}"
                )
            
            # Save to temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as tmp_file:
                tmp_file.write(download_response.content)
                tmp_file_path = tmp_file.name
            
            try:
                # Process with structured processor
                result = await structured_processor.process_document(
                    file_path=tmp_file_path,
                    filename=filename,
                    project_id=project_id,
                    correlation_id=corr_id,
                    extract_images=request_data.extract_images,
                    extract_tables=request_data.extract_tables,
                    include_coordinates=request_data.include_coordinates
                )
                
                # Save structured output to Storage Service
                output_file = None
                if result.status == "success":
                    # Generate output filename
                    base_name = os.path.splitext(filename)[0]
                    output_filename = f"{base_name}_structured.{request_data.output_format}"
                    
                    # Convert to specified format
                    if request_data.output_format == "jsonl":
                        output_content = result.to_jsonl()
                        content_type = "application/jsonl"
                    else:  # json
                        output_content = json.dumps(result.to_dict(), indent=2, ensure_ascii=False)
                        content_type = "application/json"
                    
                    # Upload to Storage Service
                    files_data = {
                        'files': (output_filename, output_content.encode('utf-8'), content_type)
                    }
                    
                    upload_response = await client.post(
                        f"{processor.storage_url}/api/storage/projects/{project_id}/upload/structured",
                        files=files_data,
                        headers=headers
                    )
                    
                    if upload_response.status_code == 200:
                        output_file = output_filename
                        logger.info(f"Uploaded structured output: {output_filename}")
                    else:
                        logger.warning(f"Failed to upload structured output: {upload_response.status_code}")
                
                # Create response
                response = StructuredProcessResponse(
                    project_id=project_id,
                    filename=filename,
                    status=result.status,
                    processing_time=result.processing_stats.get("processing_time_seconds", 0),
                    total_elements=len(result.elements),
                    element_types=result.processing_stats.get("element_types", {}),
                    output_file=output_file,
                    errors=result.errors,
                    warnings=result.warnings
                )
                
                logger.info(f"Structured processing completed for {filename}: {len(result.elements)} elements")
                return response
                
            finally:
                # Clean up temp file
                os.unlink(tmp_file_path)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Structured processing failed for {filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Structured processing failed: {str(e)}")

@router.post("/{project_id}/structured-process-all")
async def process_all_documents_structured(
    project_id: str,
    background_tasks: BackgroundTasks,
    request_data: StructuredProcessRequest = StructuredProcessRequest(),
    request: Request = None
):
    """Process all documents with structured output"""
    try:
        import httpx
        
        # Get uploaded files
        async with httpx.AsyncClient(timeout=processor.http_timeout) as client:
            corr_id = None
            try:
                if request is not None:
                    corr_id = request.headers.get("X-Correlation-ID")
            except Exception:
                pass
            
            headers = {
                "Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"
            }
            if corr_id:
                headers["X-Correlation-ID"] = corr_id
            
            response = await client.get(
                f"{processor.storage_url}/api/storage/projects/{project_id}/files/uploads_raw",
                headers=headers
            )
            
            if response.status_code == 200:
                storage_result = response.json()
                uploaded_files = [f["filename"] for f in storage_result.get("files", [])]
            else:
                uploaded_files = []
        
        if not uploaded_files:
            raise HTTPException(status_code=404, detail="No uploaded files found for structured processing")
        
        # Generate job ID
        job_id = str(uuid.uuid4())
        
        logger.info(f"Starting structured processing job {job_id} for project {project_id}: {len(uploaded_files)} files")
        
        # Start background processing
        background_tasks.add_task(
            _process_structured_background,
            project_id,
            job_id,
            uploaded_files,
            request_data,
            corr_id
        )
        
        return {
            "project_id": project_id,
            "job_id": job_id,
            "status": "started",
            "files_to_process": uploaded_files,
            "message": f"Started structured processing of {len(uploaded_files)} files",
            "started_at": datetime.now().isoformat(),
            "processing_options": {
                "extract_images": request_data.extract_images,
                "extract_tables": request_data.extract_tables,
                "include_coordinates": request_data.include_coordinates,
                "output_format": request_data.output_format
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start structured processing for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start structured processing: {str(e)}")

@router.get("/{project_id}/structured-status/{job_id}")
async def get_structured_processing_status(project_id: str, job_id: str):
    """Get status of structured processing job"""
    try:
        status = await processor.get_processing_status(project_id, job_id)
        if not status:
            raise HTTPException(status_code=404, detail="Processing job not found")
        return status
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting structured processing status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def _process_structured_background(
    project_id: str,
    job_id: str,
    filenames: List[str],
    request_data: StructuredProcessRequest,
    correlation_id: Optional[str] = None
):
    """Background task for structured processing"""
    import httpx
    import json
    
    processed_count = 0
    failed_count = 0
    files_status = []
    
    # Initialize status
    await processor.update_processing_status(project_id, job_id, {
        "status": "processing",
        "total_files": len(filenames),
        "processed_files": 0,
        "failed_files": 0,
        "files_to_process": filenames,
        "started_at": datetime.now().isoformat(),
        "processing_type": "structured"
    })
    
    try:
        async with httpx.AsyncClient(timeout=processor.http_timeout) as client:
            headers = {
                "Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"
            }
            if correlation_id:
                headers["X-Correlation-ID"] = correlation_id
            
            for i, filename in enumerate(filenames):
                try:
                    # Update current file status
                    await processor.update_processing_status(project_id, job_id, {
                        "current_file": filename,
                        "processed_files": processed_count,
                        "failed_files": failed_count
                    })
                    
                    logger.info(f"Processing {filename} ({i+1}/{len(filenames)}) with structured processor")
                    
                    # Download file
                    download_response = await client.get(
                        f"{processor.storage_url}/api/storage/projects/{project_id}/files/uploads_raw/{filename}",
                        headers=headers
                    )
                    
                    if download_response.status_code != 200:
                        raise Exception(f"Failed to download file: {download_response.status_code}")
                    
                    # Save to temporary file
                    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as tmp_file:
                        tmp_file.write(download_response.content)
                        tmp_file_path = tmp_file.name
                    
                    try:
                        # Process with structured processor
                        result = await structured_processor.process_document(
                            file_path=tmp_file_path,
                            filename=filename,
                            project_id=project_id,
                            correlation_id=correlation_id,
                            extract_images=request_data.extract_images,
                            extract_tables=request_data.extract_tables,
                            include_coordinates=request_data.include_coordinates
                        )
                        
                        if result.status == "success":
                            # Save structured output
                            base_name = os.path.splitext(filename)[0]
                            output_filename = f"{base_name}_structured.{request_data.output_format}"
                            
                            # Convert to specified format
                            if request_data.output_format == "jsonl":
                                output_content = result.to_jsonl()
                                content_type = "application/jsonl"
                            else:  # json
                                output_content = json.dumps(result.to_dict(), indent=2, ensure_ascii=False)
                                content_type = "application/json"
                            
                            # Upload to Storage Service
                            files_data = {
                                'files': (output_filename, output_content.encode('utf-8'), content_type)
                            }
                            
                            upload_response = await client.post(
                                f"{processor.storage_url}/api/storage/projects/{project_id}/upload/structured",
                                files=files_data,
                                headers=headers
                            )
                            
                            if upload_response.status_code == 200:
                                processed_count += 1
                                files_status.append({
                                    "filename": filename,
                                    "status": "success",
                                    "output_file": output_filename,
                                    "elements_extracted": len(result.elements),
                                    "processing_time": result.processing_stats.get("processing_time_seconds", 0),
                                    "timestamp": datetime.now().isoformat()
                                })
                                logger.info(f"Successfully processed {filename}: {len(result.elements)} elements")
                            else:
                                raise Exception(f"Failed to upload structured output: {upload_response.status_code}")
                        else:
                            raise Exception(f"Structured processing failed: {result.errors}")
                    
                    finally:
                        # Clean up temp file
                        os.unlink(tmp_file_path)
                
                except Exception as e:
                    failed_count += 1
                    files_status.append({
                        "filename": filename,
                        "status": "error",
                        "error": str(e),
                        "timestamp": datetime.now().isoformat()
                    })
                    logger.error(f"Failed to process {filename} with structured processor: {e}")
        
        # Update final status
        await processor.update_processing_status(project_id, job_id, {
            "status": "completed" if failed_count == 0 else "completed_with_errors",
            "processed_files": processed_count,
            "failed_files": failed_count,
            "files_status": files_status,
            "completed_at": datetime.now().isoformat(),
            "current_file": None
        })
        
        logger.info(f"Structured processing completed for job {job_id}: {processed_count} success, {failed_count} failed")
    
    except Exception as e:
        logger.error(f"Structured background processing failed for job {job_id}: {e}")
        
        await processor.update_processing_status(project_id, job_id, {
            "status": "failed",
            "error": str(e),
            "completed_at": datetime.now().isoformat()
        })
