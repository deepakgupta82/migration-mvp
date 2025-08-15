"""
Document Processing Core Logic
Extracted from backend/app/core/rag_service.py
"""

import os
import logging
import tempfile
from datetime import datetime
from typing import Optional, Dict, Any, List
import redis
import json

logger = logging.getLogger("document-service.processor")

class DocumentProcessor:
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        """Initialize document processor with Redis cache"""
        self.redis_client = redis.from_url(redis_url, decode_responses=True)
        self.debug_dir = os.path.join(os.getcwd(), "markitdown_debug")
        os.makedirs(self.debug_dir, exist_ok=True)

    async def convert_document_to_markdown(
        self, 
        file_path: str, 
        filename: str, 
        project_id: str,
        reprocess: bool = False
    ) -> Dict[str, Any]:
        """
        Convert document to Markdown using MarkItDown with fallback strategies
        Returns processing metadata and result
        """
        md_filename = os.path.splitext(filename)[0] + ".md"
        
        try:
            # Check Redis cache first unless reprocessing
            if not reprocess:
                cached_result = await self._get_cached_result(project_id, filename)
                if cached_result:
                    logger.info(f"Using cached conversion result for {filename}")
                    return cached_result

            # Check MinIO for existing canonical markdown
            if not reprocess:
                existing_content = await self._get_existing_markdown(project_id, md_filename)
                if existing_content:
                    result = {
                        "filename": filename,
                        "md_filename": md_filename,
                        "content": existing_content,
                        "conversion_strategy": "existing_md",
                        "timestamp": datetime.now().isoformat(),
                        "status": "success"
                    }
                    await self._cache_result(project_id, filename, result)
                    return result

            # Perform conversion
            result = await self._perform_conversion(file_path, filename)
            
            # Cache result
            await self._cache_result(project_id, filename, result)
            
            return result

        except Exception as e:
            logger.error(f"Document conversion failed for {filename}: {e}")
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

    async def _perform_conversion(self, file_path: str, filename: str) -> Dict[str, Any]:
        """Perform the actual document conversion with fallback strategies"""
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
                # Save debug output
                await self._save_debug_output(filename, content, conversion_strategy, file_size)
                logger.info(f"MarkItDown conversion successful for {filename} ({len(content)} chars)")
                
        except Exception as e:
            conversion_error = f"MarkItDown failed: {str(e)}"
            logger.warning(f"MarkItDown conversion failed for {filename}: {e}")
            content = None

        # Strategy 2: PyMuPDF fallback for PDFs
        if content is None and file_ext.lower() == '.pdf':
            try:
                import fitz  # PyMuPDF
                logger.info(f"Attempting PyMuPDF fallback for {filename}")
                
                doc = fitz.open(file_path)
                text_content = ""
                for page in doc:
                    text_content += page.get_text()
                doc.close()
                
                if text_content.strip():
                    content = f"# {filename}\n\n{text_content}"
                    conversion_strategy = "fallback_pymupdf"
                    await self._save_debug_output(filename, content, conversion_strategy, file_size)
                    logger.info(f"PyMuPDF fallback successful for {filename}")
                else:
                    logger.warning(f"PyMuPDF returned empty content for {filename}")
                    
            except Exception as e:
                logger.warning(f"PyMuPDF fallback failed for {filename}: {e}")

        # Strategy 3: pdfminer fallback
        if content is None and file_ext.lower() == '.pdf':
            try:
                from pdfminer.high_level import extract_text
                logger.info(f"Attempting pdfminer fallback for {filename}")
                
                text_content = extract_text(file_path)
                if text_content.strip():
                    content = f"# {filename}\n\n{text_content}"
                    conversion_strategy = "fallback_pdfminer"
                    await self._save_debug_output(filename, content, conversion_strategy, file_size)
                    logger.info(f"pdfminer fallback successful for {filename}")
                    
            except Exception as e:
                logger.warning(f"pdfminer fallback failed for {filename}: {e}")

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

    async def _get_cached_result(self, project_id: str, filename: str) -> Optional[Dict[str, Any]]:
        """Get cached conversion result from Redis"""
        try:
            cache_key = f"document_conversion:{project_id}:{filename}"
            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
        except Exception as e:
            logger.warning(f"Failed to get cached result for {filename}: {e}")
        return None

    async def _cache_result(self, project_id: str, filename: str, result: Dict[str, Any]):
        """Cache conversion result in Redis"""
        try:
            cache_key = f"document_conversion:{project_id}:{filename}"
            # Cache for 24 hours
            self.redis_client.setex(cache_key, 86400, json.dumps(result))
        except Exception as e:
            logger.warning(f"Failed to cache result for {filename}: {e}")

    async def _get_existing_markdown(self, project_id: str, md_filename: str) -> Optional[str]:
        """Get existing markdown from MinIO storage"""
        try:
            # Import storage service from main app
            import sys
            import os
            sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
            from app.core.storage_service import get_storage
            
            storage = get_storage()
            obj, content_type, size = storage.download(project_id, "uploads_parsed", md_filename)
            
            try:
                data = obj.read()
                return data.decode("utf-8", errors="replace")
            finally:
                try:
                    obj.close()
                except Exception:
                    pass
                    
        except Exception as e:
            # NoSuchKey is expected on first upload
            if "NoSuchKey" not in str(e):
                logger.warning(f"Failed to load existing markdown {md_filename}: {e}")
        return None

    async def _save_debug_output(self, filename: str, content: str, strategy: str, file_size: int):
        """Save debug output for inspection"""
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
        """Get processing status for a job"""
        try:
            status_key = f"processing_status:{project_id}:{job_id}"
            status_data = self.redis_client.get(status_key)
            if status_data:
                return json.loads(status_data)
            return {"status": "not_found"}
        except Exception as e:
            logger.error(f"Failed to get processing status: {e}")
            return {"status": "error", "error": str(e)}

    async def update_processing_status(self, project_id: str, job_id: str, status_update: Dict[str, Any]):
        """Update processing status for a job"""
        try:
            status_key = f"processing_status:{project_id}:{job_id}"
            # Merge with existing status
            existing = self.redis_client.get(status_key)
            if existing:
                current_status = json.loads(existing)
                current_status.update(status_update)
            else:
                current_status = status_update
            
            # Update timestamp
            current_status["last_updated"] = datetime.now().isoformat()
            
            # Cache for 1 hour
            self.redis_client.setex(status_key, 3600, json.dumps(current_status))
            
        except Exception as e:
            logger.error(f"Failed to update processing status: {e}")
