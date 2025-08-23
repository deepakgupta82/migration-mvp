"""
Document Processing Core Logic
Extracted from backend/app/core/rag_service.py
"""

import os
import logging
import json
import tempfile
from datetime import datetime
from typing import Optional, Dict, Any, List
import json
import asyncio


def log_json(level, msg, service="document-service", corr_id=None, project_id=None, extra=None):
    log_entry = {
        "ts": datetime.utcnow().isoformat(),
        "level": level,
        "service": service,
        "corr_id": corr_id,
        "project_id": project_id,
        "msg": msg,
    }
    if extra:
        log_entry.update(extra)
    log_str = json.dumps(log_entry, ensure_ascii=False)
    getattr(logging, level.lower(), logging.info)(log_str)

logger = logging.getLogger("document-service.processor")

class DocumentProcessor:
    def __init__(self):
        """Initialize document processor without Redis cache for now"""
        self.debug_dir = os.path.join(os.getcwd(), "markitdown_debug")
        os.makedirs(self.debug_dir, exist_ok=True)
        # Configurable debug flag for conversion logs
        try:
            from app.core.config_client import cfg_get as _cfg
            dbg = _cfg(["document_service", "debug_conversion_logs"], os.getenv("DEBUG_DOCUMENT_CONVERSION_LOGS", "0"))
            self.debug_conversion = bool(dbg) if isinstance(dbg, bool) else str(dbg).lower() in ("1", "true", "yes", "on")
        except Exception:
            self.debug_conversion = str(os.getenv("DEBUG_DOCUMENT_CONVERSION_LOGS", "0")).lower() in ("1", "true", "yes", "on")
        # In-memory status tracking (temporary replacement for Redis)
        self.processing_status = {}
        # Configurable HTTP timeouts for dependent service calls and other knobs
        try:
            from app.core.config_client import cfg_get
            self.http_timeout = float(cfg_get(["document_service", "http_timeout_sec"], os.getenv("DOCUMENT_HTTP_TIMEOUT_SEC", "30")))
            self.conversion_timeout = float(cfg_get(["document_service", "conversion_timeout_sec"], os.getenv("CONVERSION_TIMEOUT_SEC", "90")))
            self.pdf_max_pages = int(cfg_get(["document_service", "pdf_max_pages"], os.getenv("PDF_MAX_PAGES", "50")))
            self.vector_batch_size = int(cfg_get(["document_service", "vector_batch_size"], os.getenv("VECTOR_BATCH_SIZE", "50")))
            self.max_chunks = int(cfg_get(["document_service", "max_chunks"], os.getenv("MAX_CHUNKS", "0")) or 0)
            # Service URLs (can be overridden by env)
            self.storage_url = str(cfg_get(["services", "storage_service_url"], os.getenv("STORAGE_SERVICE_URL", "http://localhost:8010")))
            self.vector_url = str(cfg_get(["services", "vector_service_url"], os.getenv("VECTOR_SERVICE_URL", "http://localhost:8005")))
            self.graph_url = str(cfg_get(["services", "graph_service_url"], os.getenv("GRAPH_SERVICE_URL", "http://localhost:8006")))
        except Exception:
            self.http_timeout = float(os.getenv("DOCUMENT_HTTP_TIMEOUT_SEC", "30"))
            self.conversion_timeout = float(os.getenv("CONVERSION_TIMEOUT_SEC", "90"))
            self.pdf_max_pages = int(os.getenv("PDF_MAX_PAGES", "50"))
            self.vector_batch_size = int(os.getenv("VECTOR_BATCH_SIZE", "50"))
            self.max_chunks = int(os.getenv("MAX_CHUNKS", "0") or 0)
            self.storage_url = os.getenv("STORAGE_SERVICE_URL", "http://localhost:8010")
            self.vector_url = os.getenv("VECTOR_SERVICE_URL", "http://localhost:8005")
            self.graph_url = os.getenv("GRAPH_SERVICE_URL", "http://localhost:8006")
    log_json("info", "DocumentProcessor initialized without Redis cache", service="document-service")

    async def convert_document_to_markdown(
        self, 
        file_path: str, 
        filename: str, 
        project_id: str,
    reprocess: bool = False,
    correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Convert document to Markdown using MarkItDown with fallback strategies
        Returns processing metadata and result
        NO REDIS CACHE - Direct conversion for now
        """
        md_filename = os.path.splitext(filename)[0] + ".md"
        
        try:
            log_json("info", f"Converting {filename} to markdown (no cache)", service="document-service", corr_id=correlation_id, project_id=project_id, extra={"filename": filename})
            
            # Check MinIO for existing canonical markdown (only if not reprocessing)
            if not reprocess:
                existing_content = await self._get_existing_markdown(project_id, md_filename, correlation_id=correlation_id)
                if existing_content and len(existing_content.strip()) > 100:  # Ensure meaningful content
                    log_json("info", f"Found existing valid markdown for {filename}, skipping conversion", service="document-service", corr_id=correlation_id, project_id=project_id, extra={"filename": filename})
                    return {
                        "filename": filename,
                        "md_filename": md_filename,
                        "content": existing_content,
                        "conversion_strategy": "existing_md",
                        "timestamp": datetime.now().isoformat(),
                        "status": "success"
                    }
                elif existing_content:
                    log_json("warning", f"Existing markdown for {filename} is too short ({len(existing_content)} chars), will reprocess", service="document-service", corr_id=correlation_id, project_id=project_id, extra={"filename": filename, "length": len(existing_content)})

            # Perform fresh conversion with an overall timeout
            # Offload CPU/IO heavy conversion to a thread to keep event loop responsive
            try:
                result = await asyncio.wait_for(
                    asyncio.to_thread(self._perform_conversion_sync, file_path, filename),
                    timeout=self.conversion_timeout,
                )
            except asyncio.TimeoutError:
                log_json(
                    "error",
                    f"Conversion timed out after {self.conversion_timeout}s for {filename}",
                    service="document-service",
                    corr_id=correlation_id,
                    project_id=project_id,
                    extra={"filename": filename},
                )
                return {
                    "filename": filename,
                    "md_filename": md_filename,
                    "content": self._create_error_document(filename, f"Conversion timed out after {self.conversion_timeout}s"),
                    "conversion_strategy": "timeout_markitdown",
                    "timestamp": datetime.now().isoformat(),
                    "status": "error",
                }
            
            log_json("info", f"Conversion completed for {filename}", service="document-service", corr_id=correlation_id, project_id=project_id, extra={"filename": filename, "strategy": result.get('conversion_strategy'), "status": result.get('status')})
            return result

        except Exception as e:
            log_json("error", f"Document conversion failed for {filename}: {e}", service="document-service", corr_id=correlation_id, project_id=project_id, extra={"filename": filename, "error": str(e)})
            error_result = {
                "filename": filename,
                "md_filename": md_filename,
                "content": f"# Error Processing Document\n\nFailed to convert {filename}: {str(e)}",
                "conversion_strategy": "error_document",
                "timestamp": datetime.now().isoformat(),
                "status": "error",
                "error": str(e)
            }
            return error_result

    def _perform_conversion_sync(self, file_path: str, filename: str) -> Dict[str, Any]:
        """Perform the actual document conversion with fallback strategies (synchronous)."""
        conversion_error = None
        content = None
        conversion_strategy = "markitdown"

        # Validate file
        if not os.path.exists(file_path):
            raise ValueError(f"Source file not found: {file_path}")
        
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            raise ValueError("Source file is empty")

        # Check for media files that may need special handling
        file_ext = os.path.splitext(filename)[1].lower()
        media_extensions = ['.mp4', '.avi', '.mov', '.mp3', '.wav', '.flac', '.m4a', '.aac']
        if file_ext in media_extensions:
            logger.warning(f"Media file {filename} detected - MarkItDown may require ffmpeg")

        # Strategy 1: MarkItDown
        try:
            from markitdown import MarkItDown
            md = MarkItDown()
            logger.info(f"Converting {filename} to Markdown with MarkItDown")
            result = md.convert(file_path)
            content = result.text_content

            if not content or content.strip() == "":
                conversion_error = "MarkItDown returned empty content"
                logger.warning(f"MarkItDown returned empty content for {filename}")
                content = None
            else:
                # Save debug output (conditional)
                if self.debug_conversion:
                    self._save_debug_output(filename, content, conversion_strategy, file_size)
                logger.info(f"MarkItDown conversion successful for {filename} ({len(content)} chars)")

        except Exception as e:
            conversion_error = f"MarkItDown failed: {str(e)}"
            error_type = type(e).__name__

            # Log specific error types for better debugging
            if "MissingDependencyException" in str(e):
                logger.error(f"MarkItDown missing dependencies for {filename}: {e}")
                logger.error("MarkItDown dependencies hint: ensure poppler-utils, tesseract-ocr, ghostscript, libreoffice, pandoc, ffmpeg, libmagic1 are installed in the service image.")
            elif "PdfConverter" in str(e):
                logger.error(f"MarkItDown PDF converter issue for {filename}: {e}")
            else:
                logger.warning(f"MarkItDown conversion failed for {filename} ({error_type}): {e}")

            content = None

        # Strategy 2: PyMuPDF fallback for PDFs
        if content is None and file_ext.lower() == '.pdf':
            try:
                import fitz  # PyMuPDF
                logger.info(f"Attempting PyMuPDF fallback for {filename}")

                doc = fitz.open(file_path)
                text_content = ""

                # Extract text with better handling
                for page_num in range(min(doc.page_count, max(1, int(self.pdf_max_pages)))):  # Limit pages
                    page = doc[page_num]
                    page_text = page.get_text()
                    if page_text.strip():
                        text_content += f"\n\n--- Page {page_num + 1} ---\n\n{page_text}"

                doc.close()

                if text_content.strip():
                    content = f"# {filename}\n\n{text_content}"
                    conversion_strategy = "fallback_pymupdf"
                    if self.debug_conversion:
                        self._save_debug_output(filename, content, conversion_strategy, file_size)
                    logger.info(f"PyMuPDF fallback successful for {filename} ({len(text_content)} chars)")
                else:
                    logger.warning(f"PyMuPDF returned empty content for {filename}")

            except Exception as e:
                logger.warning(f"PyMuPDF fallback failed for {filename}: {e}")

        # Strategy 3: pdfminer fallback
        if content is None and file_ext.lower() == '.pdf':
            try:
                from pdfminer.high_level import extract_text
                logger.info(f"Attempting pdfminer fallback for {filename}")

                # Use pdfminer with better error handling
                text_content = extract_text(file_path, maxpages=max(1, int(self.pdf_max_pages)), caching=True)
                if text_content and text_content.strip():
                    content = f"# {filename}\n\n{text_content}"
                    conversion_strategy = "fallback_pdfminer"
                    if self.debug_conversion:
                        self._save_debug_output(filename, content, conversion_strategy, file_size)
                    logger.info(f"pdfminer fallback successful for {filename}")
                else:
                    logger.warning(f"pdfminer returned empty content for {filename}")

            except Exception as e:
                logger.warning(f"pdfminer fallback failed for {filename}: {e}")

        # Strategy 4: pdfplumber fallback (more robust for complex PDFs)
        if content is None and file_ext.lower() == '.pdf':
            try:
                import pdfplumber
                logger.info(f"Attempting pdfplumber fallback for {filename}")

                text_content = ""
                with pdfplumber.open(file_path) as pdf:
                    for page in pdf.pages[: max(1, int(self.pdf_max_pages))]:  # Limit pages
                        page_text = page.extract_text()
                        if page_text:
                            text_content += page_text + "\n\n"

                if text_content.strip():
                    content = f"# {filename}\n\n{text_content}"
                    conversion_strategy = "fallback_pdfplumber"
                    if self.debug_conversion:
                        self._save_debug_output(filename, content, conversion_strategy, file_size)
                    logger.info(f"pdfplumber fallback successful for {filename}")
                else:
                    logger.warning(f"pdfplumber returned empty content for {filename}")

            except Exception as e:
                logger.warning(f"pdfplumber fallback failed for {filename}: {e}")

        # Create error document if all strategies failed
        if content is None:
            content = self._create_error_document(filename, conversion_error)
            conversion_strategy = "error_document"

        return {
            "filename": filename,
            "md_filename": os.path.splitext(filename)[0] + ".md",
            "content": content,
            "conversion_strategy": conversion_strategy,
            "timestamp": datetime.now().isoformat(),
            "status": "success" if conversion_strategy != "error_document" else "error",
            "file_size": file_size,
            "content_length": len(content or "")
        }


    async def _get_existing_markdown(self, project_id: str, md_filename: str, correlation_id: Optional[str] = None) -> Optional[str]:
        """Get existing markdown from MinIO storage"""
        try:
            # Use Storage Service HTTP API instead of backend imports
            import httpx

            async with httpx.AsyncClient(timeout=self.http_timeout) as client:
                headers = {
                    "Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"
                }
                if correlation_id:
                    headers["X-Correlation-ID"] = correlation_id
                resp = await client.get(
                    f"{self.storage_url}/api/storage/projects/{project_id}/download/uploads_parsed/{md_filename}",
                    headers=headers
                )

                if resp.status_code == 200:
                    # Return decoded text content
                    try:
                        return resp.content.decode("utf-8", errors="replace")
                    except Exception:
                        # Fallback if decode fails
                        return resp.text
                elif resp.status_code == 404:
                    # Expected when markdown doesn't exist yet
                    return None
                else:
                    logger.warning(
                        f"Storage service returned {resp.status_code} for existing markdown {md_filename}"
                    )
                    return None
            
        except Exception as e:
            # NoSuchKey is expected on first upload
            if "NoSuchKey" not in str(e):
                logger.warning(f"Failed to load existing markdown {md_filename}: {e}")
        return None

    def _save_debug_output(self, filename: str, content: str, strategy: str, file_size: int):
        """Save debug output for inspection (synchronous)."""
        try:
            safe_filename = "".join(c for c in filename if c.isalnum() or c in (' ', '-', '_', '.')).rstrip()
            debug_file_path = os.path.join(self.debug_dir, f"{safe_filename}.{strategy}.md")
            
            with open(debug_file_path, 'w', encoding='utf-8') as debug_file:
                debug_file.write(f"# DEBUG: {strategy} Conversion of {filename}\n")
                debug_file.write(f"Original file: {filename}\n")
                debug_file.write(f"File size: {file_size} bytes\n")
                debug_file.write(f"Conversion strategy: {strategy}\n")
                debug_file.write(f"Content length: {len(content or '')} characters\n")
                debug_file.write(f"Content preview: {(content or '')[:200]}...\n")
                debug_file.write("="*50 + "\n")
                debug_file.write(content or "[EMPTY CONTENT]")
                
        except Exception as e:
            logger.warning(f"Failed to save debug output for {filename}: {e}")

    def _create_error_document(self, filename: str, error_message: str) -> str:
        """Create error document when all conversion strategies fail"""
        return f"""# Error Processing Document: {filename}

**Status**: Document conversion failed  
**Timestamp**: {datetime.now().isoformat()}  
**Error**: {error_message or 'Unknown error occurred during conversion'}

## Attempted Conversion Strategies

1. **MarkItDown**: Primary conversion method
2. **PyMuPDF**: PDF-specific fallback (for PDF files)
3. **pdfminer**: Alternative PDF extraction (for PDF files)

All conversion strategies failed for this document. The file may be:
- Corrupted or incomplete
- In an unsupported format
- Password-protected
- Contains non-standard encoding

Please verify the file integrity and try uploading again.
"""

    async def get_processing_status(self, project_id: str, job_id: str) -> Dict[str, Any]:
        """Get processing status for a job - using in-memory storage for now"""
        try:
            status_key = f"{project_id}:{job_id}"
            if status_key in self.processing_status:
                return self.processing_status[status_key]
            return {"status": "not_found"}
        except Exception as e:
            logger.error(f"Failed to get processing status: {e}")
            return {"status": "error", "error": str(e)}

    async def update_processing_status(self, project_id: str, job_id: str, status_update: Dict[str, Any]):
        """Update processing status for a job - using in-memory storage for now"""
        try:
            status_key = f"{project_id}:{job_id}"
            
            # Merge with existing status
            if status_key in self.processing_status:
                current_status = self.processing_status[status_key].copy()
                current_status.update(status_update)
            else:
                current_status = status_update.copy()
            
            # Update timestamp
            current_status["last_updated"] = datetime.now().isoformat()
            
            # Store in memory
            self.processing_status[status_key] = current_status
            
            logger.debug(f"Updated processing status for {status_key}: {current_status.get('status', 'unknown')}")
            
        except Exception as e:
            logger.error(f"Failed to update processing status: {e}")
