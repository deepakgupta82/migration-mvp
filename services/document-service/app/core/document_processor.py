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
from typing import List

# Import service discovery
from .service_discovery import (
    get_storage_service_url,
    get_project_service_url,
    get_vector_service_url,
    get_graph_service_url,
    get_analytics_service_url
)

try:
    # Optional import; only used if available
    from unstructured.partition.auto import partition as _u_partition  # type: ignore
    from unstructured.cleaners.core import clean as _u_clean  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    _u_partition = None
    _u_clean = None


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
        
        # Configure Tesseract OCR path explicitly
        self._configure_tesseract_path()
        
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
            # Service URLs - use service discovery with fallbacks
            self.storage_url = str(cfg_get(["services", "storage_service_url"], os.getenv("STORAGE_SERVICE_URL", "http://localhost:8010")))
            self.vector_url = str(cfg_get(["services", "vector_service_url"], os.getenv("VECTOR_SERVICE_URL", "http://localhost:8005")))
            self.graph_url = str(cfg_get(["services", "graph_service_url"], os.getenv("GRAPH_SERVICE_URL", "http://localhost:8006")))
            self.project_service_url = str(cfg_get(["services", "project_service_url"], os.getenv("PROJECT_SERVICE_URL", "http://localhost:8002")))

            # Initialize service discovery for dynamic URL resolution
            self._service_discovery_initialized = False
        except Exception:
            self.http_timeout = float(os.getenv("DOCUMENT_HTTP_TIMEOUT_SEC", "30"))
            self.conversion_timeout = float(os.getenv("CONVERSION_TIMEOUT_SEC", "90"))
            self.pdf_max_pages = int(os.getenv("PDF_MAX_PAGES", "50"))
            self.vector_batch_size = int(os.getenv("VECTOR_BATCH_SIZE", "50"))
            self.max_chunks = int(os.getenv("MAX_CHUNKS", "0") or 0)
            self.storage_url = os.getenv("STORAGE_SERVICE_URL", "http://localhost:8010")
            self.vector_url = os.getenv("VECTOR_SERVICE_URL", "http://localhost:8005")
            self.graph_url = os.getenv("GRAPH_SERVICE_URL", "http://localhost:8006")
            self.project_service_url = os.getenv("PROJECT_SERVICE_URL", "http://localhost:8002")
    
    def _configure_tesseract_path(self):
        """Configure Tesseract OCR path for the processor"""
        tesseract_path = r"C:\Users\deepakgupta13\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"
        
        if os.path.exists(tesseract_path):
            # Set environment variable for unstructured and other libraries
            os.environ['TESSERACT_CMD'] = tesseract_path
            logger.info(f"Tesseract path configured for document processor: {tesseract_path}")
            
            # Configure pytesseract if available
            try:
                import pytesseract
                pytesseract.pytesseract.tesseract_cmd = tesseract_path
                logger.info("pytesseract configured for document processor")
            except ImportError:
                pass  # pytesseract is optional
        else:
            logger.warning(f"Tesseract not found at expected path: {tesseract_path}")
    
    log_json("info", "DocumentProcessor initialized without Redis cache", service="document-service")

    async def _get_storage_url(self) -> str:
        """Get storage service URL using service discovery"""
        if not self._service_discovery_initialized:
            await self._initialize_service_discovery()
        return self.storage_url

    async def _get_vector_url(self) -> str:
        """Get vector service URL using service discovery"""
        if not self._service_discovery_initialized:
            await self._initialize_service_discovery()
        return self.vector_url

    async def _get_graph_url(self) -> str:
        """Get graph service URL using service discovery"""
        if not self._service_discovery_initialized:
            await self._initialize_service_discovery()
        return self.graph_url

    async def _get_project_service_url(self) -> str:
        """Get project service URL using service discovery"""
        if not self._service_discovery_initialized:
            await self._initialize_service_discovery()
        return self.project_service_url

    async def _get_websocket_url(self) -> str:
        """Get websocket service URL using service discovery"""
        if not self._service_discovery_initialized:
            await self._initialize_service_discovery()
        # Use websocket service URL - default to localhost:8009
        websocket_url = os.getenv("WEBSOCKET_SERVICE_URL", "http://localhost:8009")
        return websocket_url

    async def _initialize_service_discovery(self):
        """Initialize service discovery and update URLs"""
        try:
            # Try to get dynamic URLs from service registry
            storage_url = await get_storage_service_url()
            if storage_url:
                self.storage_url = storage_url
                logger.info(f"Using dynamic storage service URL: {storage_url}")

            vector_url = await get_vector_service_url()
            if vector_url:
                self.vector_url = vector_url
                logger.info(f"Using dynamic vector service URL: {vector_url}")

            graph_url = await get_graph_service_url()
            if graph_url:
                self.graph_url = graph_url
                logger.info(f"Using dynamic graph service URL: {graph_url}")

            project_url = await get_project_service_url()
            if project_url:
                self.project_service_url = project_url
                logger.info(f"Using dynamic project service URL: {project_url}")

            self._service_discovery_initialized = True
            logger.info("Service discovery initialized successfully")

        except Exception as e:
            logger.warning(f"Service discovery initialization failed, using fallback URLs: {e}")
            self._service_discovery_initialized = True  # Don't retry on failure

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
            
            # Check for existing processed files (only if not reprocessing)
            if not reprocess:
                # Check if enhanced workflow is enabled
                use_enhanced_workflow = os.getenv("USE_ENHANCED_WORKFLOW", "true").lower() == "true"
                
                if use_enhanced_workflow:
                    # Check for existing JSONL structured file
                    base_name = os.path.splitext(filename)[0]
                    structured_filename = f"{base_name}_structured.jsonl"
                    existing_structured = await self._get_existing_structured_file(project_id, structured_filename, correlation_id=correlation_id)
                    
                    if existing_structured and len(existing_structured.strip()) > 200:  # JSONL files are larger
                        log_json("info", f"Found existing structured JSONL for {filename}, skipping processing", service="document-service", corr_id=correlation_id, project_id=project_id, extra={"filename": filename, "structured_file": structured_filename})
                        # Convert JSONL back to markdown format for compatibility
                        markdown_content = self._convert_jsonl_to_markdown(existing_structured)
                        return {
                            "filename": filename,
                            "md_filename": md_filename,
                            "content": markdown_content,
                            "conversion_strategy": "existing_structured",
                            "timestamp": datetime.now().isoformat(),
                            "status": "success",
                            "structured_file": structured_filename
                        }
                    elif existing_structured:
                        log_json("warning", f"Existing structured file for {filename} is too short ({len(existing_structured)} chars), will reprocess", service="document-service", corr_id=correlation_id, project_id=project_id, extra={"filename": filename, "length": len(existing_structured)})
                else:
                    # Traditional workflow - check for existing markdown
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
        """Perform the actual document conversion with Unstructured first, then fallbacks (synchronous)."""
        conversion_error = None
        content = None
        conversion_strategy = "unstructured"

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

        # IMPORTANT: Create a copy of the file for each conversion strategy
        # This prevents file access conflicts between different processing libraries
        temp_files_to_cleanup = []
        
        try:
            # Strategy 1: Unstructured auto partitioner for high-fidelity parsing
            if _u_partition is not None:
                try:
                    logger.info(f"Converting {filename} to Markdown with Unstructured")
                    
                    # Create a copy for unstructured processing to avoid file locking issues
                    import shutil
                    unstructured_temp = file_path + "_unstructured_copy"
                    shutil.copy2(file_path, unstructured_temp)
                    temp_files_to_cleanup.append(unstructured_temp)
                    
                    elements = _u_partition(filename=unstructured_temp)  # type: ignore[misc]
                    md_lines: List[str] = []
                    for el in elements:
                        # Fix API compatibility: remove deprecated bullets_to_dashes parameter
                        text = _u_clean(str(el)).strip() if _u_clean else str(el).strip()  # type: ignore[misc]
                        if not text:
                            continue
                        cat = getattr(el, "category", None)
                        if cat in ("Title", "Header"):
                            # Attempt to infer heading level; default H2
                            level = 2
                            try:
                                md = getattr(el, "metadata", None)
                                if md and hasattr(md, "to_dict"):
                                    level = int(md.to_dict().get("category_depth", 2))  # type: ignore[call-arg]
                                    level = 1 if level == 0 else min(level, 6)
                            except Exception:
                                level = 2
                            md_lines.append(f"{'#' * level} {text}")
                        elif cat in ("ListItem",):
                            md_lines.append(f"- {text}")
                        else:
                            # Tables and most other elements stringify suitably
                            md_lines.append(text)
                    if md_lines:
                        content = "\n\n".join(md_lines).strip()
                        if self.debug_conversion:
                            self._save_debug_output(filename, content, conversion_strategy, file_size)
                        logger.info(f"Unstructured conversion successful for {filename} ({len(content)} chars)")
                    else:
                        logger.warning(f"Unstructured returned no content for {filename}")
                except Exception as e:
                    error_msg = str(e)
                    if "tesseract is not installed" in error_msg.lower() or "tesseract" in error_msg.lower():
                        logger.error(f"Tesseract OCR dependency missing for Unstructured processing of {filename}: {e}")
                        logger.error("✗ Tesseract OCR required for advanced PDF processing")
                        conversion_error = f"Tesseract OCR not available: {error_msg}"
                    else:
                        logger.warning(f"Unstructured conversion failed for {filename}: {e}")
                        conversion_error = f"Unstructured failed: {e}"
                    content = None

            # Strategy 2: MarkItDown
            if content is None:
                conversion_strategy = "markitdown"
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
                    if "tesseract is not installed" in str(e).lower() or "tesseract" in str(e).lower():
                        logger.error(f"Tesseract OCR dependency missing for {filename}: {e}")
                        logger.error("✗ Tesseract OCR required for PDF processing")
                        logger.error("  Install: https://github.com/UB-Mannheim/tesseract/wiki")
                        logger.error("  Windows: Download installer and add to PATH")
                        logger.error("  Docker: Already included in service image")
                        conversion_error = f"Tesseract OCR not available: {str(e)}"
                    elif "MissingDependencyException" in str(e):
                        logger.error(f"MarkItDown missing dependencies for {filename}: {e}")
                        logger.error("MarkItDown dependencies hint: ensure poppler-utils, tesseract-ocr, ghostscript, libreoffice, pandoc, ffmpeg, libmagic1 are installed in the service image.")
                    elif "PdfConverter" in str(e):
                        logger.error(f"MarkItDown PDF converter issue for {filename}: {e}")
                    else:
                        logger.warning(f"MarkItDown conversion failed for {filename} ({error_type}): {e}")

                    content = None

            # Strategy 3: PyMuPDF fallback for PDFs
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

            # Strategy 4: pdfminer fallback
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

            # Strategy 5: pdfplumber fallback (more robust for complex PDFs)
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
                error_msg = conversion_error or "Unknown conversion error"
                if "tesseract" in error_msg.lower():
                    content = self._create_tesseract_error_document(filename, error_msg)
                else:
                    content = self._create_error_document(filename, error_msg)
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
            
        finally:
            # Clean up any temporary files created during processing
            from app.utils.file_utils import cleanup_temp_file_with_retry
            for temp_file in temp_files_to_cleanup:
                try:
                    if os.path.exists(temp_file):
                        cleanup_temp_file_with_retry(temp_file, logger=logger)
                        logger.debug(f"Cleaned up temporary file: {temp_file}")
                except Exception as e:
                    logger.warning(f"Failed to clean up temporary file {temp_file}: {e}")


    async def _get_existing_markdown(self, project_id: str, md_filename: str, correlation_id: Optional[str] = None) -> Optional[str]:
        """Check if markdown file already exists in Storage Service"""
        try:
            import httpx
            storage_url = await self._get_storage_url()
            async with httpx.AsyncClient(timeout=self.http_timeout) as client:
                headers = {
                    "Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"
                }
                if correlation_id:
                    headers["X-Correlation-ID"] = correlation_id

                response = await client.get(
                    f"{storage_url}/api/storage/projects/{project_id}/download/processed_md/{md_filename}",
                    headers=headers
                )

                if response.status_code == 200:
                    return response.text
                else:
                    return None

        except Exception as e:
            log_json("debug", f"Error checking existing markdown: {e}", service="document-service", corr_id=correlation_id, project_id=project_id)
            return None
    
    async def _get_existing_structured_file(self, project_id: str, structured_filename: str, correlation_id: Optional[str] = None) -> Optional[str]:
        """Check if structured JSONL file already exists in Storage Service"""
        try:
            import httpx
            storage_url = await self._get_storage_url()
            async with httpx.AsyncClient(timeout=self.http_timeout) as client:
                headers = {
                    "Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"
                }
                if correlation_id:
                    headers["X-Correlation-ID"] = correlation_id

                response = await client.get(
                    f"{storage_url}/api/storage/projects/{project_id}/download/structured/{structured_filename}",
                    headers=headers
                )

                if response.status_code == 200:
                    return response.text
                else:
                    return None

        except Exception as e:
            log_json("debug", f"Error checking existing structured file: {e}", service="document-service", corr_id=correlation_id, project_id=project_id)
            return None
    
    def _convert_jsonl_to_markdown(self, jsonl_content: str) -> str:
        """Convert JSONL structured content back to markdown format for compatibility"""
        try:
            import json
            
            markdown_lines = []
            
            for line in jsonl_content.strip().split('\n'):
                if not line.strip():
                    continue
                    
                try:
                    data = json.loads(line)
                    
                    if data.get('type') == 'element':
                        element_data = data.get('data', {})
                        element_type = element_data.get('type', '')
                        text = element_data.get('text', '')
                        
                        if element_type == 'title':
                            hierarchy_level = element_data.get('hierarchy_level', 1)
                            markdown_lines.append(f"{'#' * min(hierarchy_level, 6)} {text}")
                        elif element_type == 'narrative_text':
                            markdown_lines.append(text)
                        elif element_type == 'list_item':
                            markdown_lines.append(f"- {text}")
                        elif element_type == 'table':
                            # Table text is already formatted
                            markdown_lines.append(text)
                        else:
                            markdown_lines.append(text)
                        
                        markdown_lines.append("")  # Add spacing between elements
                        
                except json.JSONDecodeError:
                    continue
                    
            if markdown_lines:
                return "\n".join(markdown_lines).strip()
            else:
                return "# Processed Document\n\nContent extracted from structured format."
                
        except Exception as e:
            logger.warning(f"Error converting JSONL to markdown: {e}")
            return "# Processed Document\n\nContent extracted from structured format (conversion error)."



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

    def _create_tesseract_error_document(self, filename: str, error_message: str) -> str:
        """Create error document specifically for Tesseract OCR dependency issues"""
        return f"""# Error Processing Document: {filename}

**Status**: Tesseract OCR Dependency Missing  
**Timestamp**: {datetime.now().isoformat()}  
**Error**: {error_message or 'Tesseract OCR not available'}

## Issue Description

This PDF document requires Tesseract OCR for proper text extraction, but Tesseract is not available in the current environment.

## Resolution Steps

### For Local Development:
1. **Install Tesseract OCR**:
   - Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki
   - Run installer as Administrator
   - Ensure "Add to PATH" option is selected
   - Restart terminal/IDE after installation

2. **Verify Installation**:
   ```cmd
   tesseract --version
   ```

3. **Alternative Package Managers**:
   - Chocolatey: `choco install tesseract`
   - Scoop: `scoop install tesseract`
   - Winget: `winget install UB-Mannheim.TesseractOCR`

### For Docker Deployment:
Tesseract is already included in the Docker image. Run the service in Docker:
```bash
docker-compose up document-service
```

### Fallback Options:
If Tesseract cannot be installed, try:
1. Converting PDF to text externally before upload
2. Using the Docker version of the service
3. Processing text-based PDFs (may work without OCR)

## Technical Details
- Required for: Scanned PDFs, image-based documents
- Used by: Unstructured.io library for advanced PDF processing
- Alternative: Basic PDF text extraction (limited capability)
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

    async def increment_processed_file(self, project_id: str, job_id: str, filename: str):
        """Increment the count of successfully processed files"""
        try:
            status_key = f"{project_id}:{job_id}"
            if status_key in self.processing_status:
                current_status = self.processing_status[status_key]
                current_status["processed_files"] = current_status.get("processed_files", 0) + 1
                current_status["last_updated"] = datetime.now().isoformat()
                logger.debug(f"Incremented processed files for {status_key}: {current_status['processed_files']}")
        except Exception as e:
            logger.error(f"Failed to increment processed file count: {e}")

    async def increment_failed_file(self, project_id: str, job_id: str, filename: str, error: str):
        """Increment the count of failed files and record error"""
        try:
            status_key = f"{project_id}:{job_id}"
            if status_key in self.processing_status:
                current_status = self.processing_status[status_key]
                current_status["failed_files"] = current_status.get("failed_files", 0) + 1
                
                # Add to failed files list if it doesn't exist
                if "failed_files_list" not in current_status:
                    current_status["failed_files_list"] = []
                current_status["failed_files_list"].append({
                    "filename": filename,
                    "error": error,
                    "timestamp": datetime.now().isoformat()
                })
                
                current_status["last_updated"] = datetime.now().isoformat()
                logger.debug(f"Incremented failed files for {status_key}: {current_status['failed_files']}")
        except Exception as e:
            logger.error(f"Failed to increment failed file count: {e}")
