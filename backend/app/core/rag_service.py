import requests
import logging
import os
import uuid
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from .service_client import get_service_client
from app.utils.semantic_chunker import SemanticChunker
from app.utils.sanitization import sanitize_agent_output
from app.core.logging_config import correlation_id_ctx

# Database logging setup
os.makedirs("logs", exist_ok=True)
db_logger = logging.getLogger("database")
db_handler = logging.FileHandler("logs/database.log")
db_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
if not db_logger.hasHandlers():
    db_logger.addHandler(db_handler)
db_logger.setLevel(logging.INFO)

# --- Utility filters for graph hygiene ---
_ALLOWED_ENTITY_TYPES = {
    'hostname','server','database','application','service','network','storage','load_balancer','firewall',
    'switch','router','cluster','system_identifier','component_identifier','host','instance','vm','virtual_machine',
    'container','pod','node','endpoint','ip_address','subnet','url','queue','topic','bucket','table','schema'
}
_DENY_NAME_PATTERNS = (
    'http://','https://','www.','.com','.net','.org','.io','.gov','.edu','localhost','127.0.0.1','0.0.0.0'
)

def _is_valid_entity(e: Dict[str, Any]) -> bool:
    name = (e.get('name') or '').strip()
    etype = (e.get('type') or '').strip().lower()
    if not name or len(name) < 2:
        return False
    if any(pat in name.lower() for pat in _DENY_NAME_PATTERNS):
        return False
    # allow unknown types but prefer allowed infra types
    return True if not etype else True

class RAGService:
    def __init__(self, project_id: str, llm=None, config: Dict[str, Any] = None):
        self.project_id = project_id
        self.config = config or {}
        self.chunking_strategy = self.config.get('chunking_strategy', 'semantic')
        self.batch_size = self.config.get('batch_size', 100)
        self.llm = llm  # Store LLM for query synthesis

        # Entity extraction parallelism/timeouts
        self.entity_parallel_workers = self.config.get('entity_parallel_workers', 4)
        self.entity_timeout_seconds = self.config.get('entity_timeout_seconds', 30)

        # Initialize helpers
        self.semantic_chunker = SemanticChunker()

        # Initialize log streaming for real-time progress
        self._init_log_streaming()

        # Log chunking strategy for verification
        db_logger.info(f"RAGService initialized with chunking strategy: {self.chunking_strategy}")

        # Note: Vector ops are delegated to vector-service, entity extraction to graph-service
        if not llm:
            db_logger.info("RAGService initialized without LLM; retrieval works, synthesis disabled")

        # No local vector DB to verify; vector-service owns collections — warm-up best effort
        try:
            import anyio
            async def _ping():
                client = await get_service_client()
                await client.create_vector_collection(self.project_id)
            anyio.run(_ping)
        except Exception as e:
            db_logger.debug(f"Vector-service warm-up skipped: {e}")

    def _init_log_streaming(self):
        """Initialize log streaming for real-time progress updates"""
        try:
            from app.core.log_stream import log_manager
            self.log_manager = log_manager
        except ImportError:
            self.log_manager = None
            db_logger.warning("Log streaming manager not available")

    async def _stream_log(self, level: str, message: str, metadata: Dict[str, Any] = None):
        """Stream a log message to connected WebSocket clients"""
        if not self.log_manager:
            return
            
        try:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "level": level.upper(),
                "service": "document_processing",
                "project_id": self.project_id,
                "message": message,
                "metadata": metadata or {}
            }
            
            # Send to both general service logs and project-specific logs
            await self.log_manager.send_log("document_processing", log_entry)
            await self.log_manager.send_log(f"project_{self.project_id}", log_entry)
            
        except Exception as e:
            db_logger.warning(f"Failed to stream log: {e}")

    def _stream_log_sync(self, level: str, message: str, metadata: Dict[str, Any] = None):
        """Synchronous wrapper for log streaming"""
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're in an async context, schedule the coroutine
                asyncio.create_task(self._stream_log(level, message, metadata))
            else:
                # If no event loop is running, run it in a new loop
                asyncio.run(self._stream_log(level, message, metadata))
        except Exception as e:
            db_logger.warning(f"Failed to stream log synchronously: {e}")

    # (moved warm-up into __init__)

    def add_file(self, file_path: str, reprocess: bool = False, source_name: Optional[str] = None):
        """Process a file by converting to canonical Markdown, indexing, and extracting entities.

        - Uses MinIO uploads_parsed as canonical .md when available (unless reprocess=True).
        - Persists converted .md keyed by the original filename (source_name).
        - Emits WS messages and writes a metadata snapshot to object storage.
        """
        import tempfile
        import asyncio
        from datetime import datetime, timezone
        import json

        filename = os.path.basename(source_name) if source_name else os.path.basename(file_path)
        try:
            # Helper to broadcast without failing the pipeline
            def _ws_broadcast(msg: str):
                try:
                    from app.core.process_ws import get_process_ws_manager
                    asyncio.create_task(get_process_ws_manager().broadcast(self.project_id, msg))
                except Exception:
                    pass

            # Storage access
            from app.core.storage_service import get_storage
            storage = get_storage()

            md_filename = os.path.splitext(filename)[0] + ".md"
            content = None
            conversion_strategy = "converted"

            # Try to reuse existing canonical Markdown
            if not reprocess:
                try:
                    obj, ct, size = storage.download(self.project_id, "uploads_parsed", md_filename)
                    try:
                        data = obj.read()
                    finally:
                        try:
                            obj.close()
                        except Exception:
                            pass
                    content = data.decode("utf-8", errors="replace")
                    conversion_strategy = "existing_md"
                    db_logger.info(
                        f"Using existing canonical markdown {md_filename} from object storage ({size} bytes) for source {filename}"
                    )
                    _ws_broadcast(f"CONVERTED_TO_MD: {md_filename} (cached)")
                except Exception as e:
                    # NoSuchKey is expected on first upload - not an error
                    if "NoSuchKey" not in str(e):
                        db_logger.warning(f"Failed to load cached markdown for {filename}: {e}")
                    content = None

            # Convert with MarkItDown if needed
            if content is None:
                conversion_error = None
                try:
                    # Validate file before conversion
                    if not os.path.exists(file_path):
                        raise ValueError(f"Source file not found: {file_path}")
                    
                    file_size = os.path.getsize(file_path)
                    if file_size == 0:
                        raise ValueError("Source file is empty")
                    
                    # Check file type for known limitations
                    file_ext = os.path.splitext(filename)[1].lower()
                    media_extensions = ['.mp4', '.avi', '.mov', '.mp3', '.wav', '.flac', '.m4a', '.aac']
                    if file_ext in media_extensions:
                        db_logger.warning(f"Media file {filename} detected - MarkItDown may require ffmpeg for audio/video conversion")
                    
                    from markitdown import MarkItDown
                    md = MarkItDown()
                    db_logger.info(f"Converting {filename} to Markdown with MarkItDown from temp path {file_path}")
                    result = md.convert(file_path)
                    content = result.text_content
                    
                    # 🔍 DEBUG: Save converted Markdown content locally for inspection
                    try:
                        debug_dir = os.path.join(os.getcwd(), "markitdown_debug")
                        os.makedirs(debug_dir, exist_ok=True)
                        
                        # Create safe filename for the debug file
                        safe_filename = "".join(c for c in filename if c.isalnum() or c in (' ', '-', '_', '.')).rstrip()
                        debug_file_path = os.path.join(debug_dir, f"{safe_filename}.converted.md")
                        
                        with open(debug_file_path, 'w', encoding='utf-8') as debug_file:
                            debug_file.write(f"# DEBUG: MarkItDown Conversion of {filename}\n")
                            debug_file.write(f"Original file: {filename}\n")
                            debug_file.write(f"File size: {file_size} bytes\n")
                            debug_file.write(f"Conversion strategy: {conversion_strategy}\n")
                            debug_file.write(f"Content length: {len(content or '')} characters\n")
                            debug_file.write(f"Content preview: {(content or '')[:200]}...\n")
                            debug_file.write("="*50 + "\n")
                            debug_file.write(content or "[EMPTY CONTENT]")
                        
                        db_logger.info(f"💾 DEBUG: Saved converted content to {debug_file_path} ({len(content or '')} chars)")
                        
                    except Exception as debug_save_error:
                        db_logger.warning(f"Could not save debug markdown file: {debug_save_error}")
                    
                    if not content or not content.strip():
                        conversion_error = "MarkItDown returned empty content"
                        db_logger.warning(f"MarkItDown returned empty content for {filename}")
                        
                        # Try alternative extraction for PDFs
                        if file_ext == '.pdf':
                            db_logger.info(f"Attempting fallback PDF extraction for {filename}")
                            try:
                                # Try pymupdf first (faster and more reliable)
                                import fitz  # pymupdf
                                pdf_doc = fitz.open(file_path)
                                fallback_content = ""
                                for page in pdf_doc:
                                    fallback_content += page.get_text() + "\n\n"
                                pdf_doc.close()
                                if fallback_content.strip():
                                    content = f"# {filename}\n\n{fallback_content.strip()}"
                                    conversion_strategy = "fallback_pymupdf"
                                    db_logger.info(f"Successfully extracted {len(content)} chars using PyMuPDF fallback")
                                    conversion_error = None
                                    
                                    # 🔍 DEBUG: Save PyMuPDF fallback content
                                    try:
                                        debug_dir = os.path.join(os.getcwd(), "markitdown_debug")
                                        os.makedirs(debug_dir, exist_ok=True)
                                        safe_filename = "".join(c for c in filename if c.isalnum() or c in (' ', '-', '_', '.')).rstrip()
                                        debug_file_path = os.path.join(debug_dir, f"{safe_filename}.pymupdf_fallback.md")
                                        
                                        with open(debug_file_path, 'w', encoding='utf-8') as debug_file:
                                            debug_file.write(f"# DEBUG: PyMuPDF Fallback Conversion of {filename}\n")
                                            debug_file.write(f"Original file: {filename}\n")
                                            debug_file.write(f"File size: {file_size} bytes\n")
                                            debug_file.write(f"Conversion strategy: {conversion_strategy}\n")
                                            debug_file.write(f"Content length: {len(content)} characters\n")
                                            debug_file.write("="*50 + "\n")
                                            debug_file.write(content)
                                        
                                        db_logger.info(f"💾 DEBUG: Saved PyMuPDF fallback content to {debug_file_path}")
                                    except Exception as debug_save_error:
                                        db_logger.warning(f"Could not save PyMuPDF debug file: {debug_save_error}")
                            except Exception as pymupdf_err:
                                db_logger.debug(f"PyMuPDF fallback failed: {pymupdf_err}")
                                try:
                                    # Try pdfminer as second fallback
                                    from pdfminer.high_level import extract_text
                                    fallback_content = extract_text(file_path)
                                    if fallback_content and fallback_content.strip():
                                        content = f"# {filename}\n\n{fallback_content.strip()}"
                                        conversion_strategy = "fallback_pdfminer"
                                        db_logger.info(f"Successfully extracted {len(content)} chars using pdfminer fallback")
                                        conversion_error = None
                                        
                                        # 🔍 DEBUG: Save pdfminer fallback content
                                        try:
                                            debug_dir = os.path.join(os.getcwd(), "markitdown_debug")
                                            os.makedirs(debug_dir, exist_ok=True)
                                            safe_filename = "".join(c for c in filename if c.isalnum() or c in (' ', '-', '_', '.')).rstrip()
                                            debug_file_path = os.path.join(debug_dir, f"{safe_filename}.pdfminer_fallback.md")
                                            
                                            with open(debug_file_path, 'w', encoding='utf-8') as debug_file:
                                                debug_file.write(f"# DEBUG: pdfminer Fallback Conversion of {filename}\n")
                                                debug_file.write(f"Original file: {filename}\n")
                                                debug_file.write(f"File size: {file_size} bytes\n")
                                                debug_file.write(f"Conversion strategy: {conversion_strategy}\n")
                                                debug_file.write(f"Content length: {len(content)} characters\n")
                                                debug_file.write("="*50 + "\n")
                                                debug_file.write(content)
                                            
                                            db_logger.info(f"💾 DEBUG: Saved pdfminer fallback content to {debug_file_path}")
                                        except Exception as debug_save_error:
                                            db_logger.warning(f"Could not save pdfminer debug file: {debug_save_error}")
                                except Exception as pdfminer_err:
                                    db_logger.debug(f"pdfminer fallback also failed: {pdfminer_err}")
                    
                    # Still no content after all attempts
                    if not content or not content.strip():
                        # Record the failure but don't stop the pipeline completely
                        content = f"# {filename}\n\n**Conversion failed**: {conversion_error or 'Unknown error'}\n\nFile size: {file_size} bytes\nFile type: {file_ext}\n\nThis document could not be processed automatically. Consider:\n- Checking if the file is corrupted\n- Ensuring the file format is supported\n- Re-uploading with a different format\n"
                        conversion_strategy = "conversion_failed"
                        
                        # 🔍 DEBUG: Save failed conversion info
                        try:
                            debug_dir = os.path.join(os.getcwd(), "markitdown_debug")
                            os.makedirs(debug_dir, exist_ok=True)
                            safe_filename = "".join(c for c in filename if c.isalnum() or c in (' ', '-', '_', '.')).rstrip()
                            debug_file_path = os.path.join(debug_dir, f"{safe_filename}.FAILED.md")
                            
                            with open(debug_file_path, 'w', encoding='utf-8') as debug_file:
                                debug_file.write(f"# DEBUG: FAILED Conversion of {filename}\n")
                                debug_file.write(f"Original file: {filename}\n")
                                debug_file.write(f"File path: {file_path}\n")
                                debug_file.write(f"File size: {file_size} bytes\n")
                                debug_file.write(f"File extension: {file_ext}\n")
                                debug_file.write(f"Conversion error: {conversion_error or 'Unknown error'}\n")
                                debug_file.write(f"Final conversion strategy: {conversion_strategy}\n")
                                debug_file.write("="*50 + "\n")
                                debug_file.write(content)
                            
                            db_logger.warning(f"💾 DEBUG: Saved FAILED conversion info to {debug_file_path}")
                        except Exception as debug_save_error:
                            db_logger.warning(f"Could not save failed conversion debug file: {debug_save_error}")
                        db_logger.error(f"All conversion attempts failed for {filename}: {conversion_error}")
                        _ws_broadcast(f"CONVERSION_FAILED: {filename} - {conversion_error}")
                
                except Exception as conv_err:
                    conversion_error = str(conv_err)
                    db_logger.error(f"Conversion error for {filename}: {conv_err}")
                    # Create error document instead of failing completely
                    file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
                    file_ext = os.path.splitext(filename)[1].lower()
                    content = f"# {filename}\n\n**Conversion error**: {conversion_error}\n\nFile size: {file_size} bytes\nFile type: {file_ext}\n\nThis document encountered an error during processing and requires manual review.\n"
                    conversion_strategy = "conversion_error"
                    _ws_broadcast(f"CONVERSION_ERROR: {filename} - {conversion_error}")

                # Always try to store the result (even if it's an error document)
                if content:
                    try:
                        storage.upload_text(
                            self.project_id,
                            "uploads_parsed",
                            md_filename,
                            content,
                            content_type="text/markdown; charset=utf-8",
                        )
                        db_logger.info(
                            f"Canonical markdown uploaded to object storage as {md_filename} for source {filename} (strategy: {conversion_strategy})"
                        )
                        try:
                            from app.core.event_bus import get_event_bus
                            asyncio.create_task(
                                get_event_bus().publish(
                                    "markdown_saved", {
                                        "project_id": self.project_id, 
                                        "filename": md_filename,
                                        "conversion_strategy": conversion_strategy,
                                        "success": conversion_strategy not in ["conversion_failed", "conversion_error"]
                                    }
                                )
                            )
                        except Exception:
                            pass
                        if conversion_strategy not in ["conversion_failed", "conversion_error"]:
                            _ws_broadcast(f"CONVERTED_TO_MD: {md_filename}")
                    except Exception as store_err:
                        db_logger.error(f"Failed to upload markdown to object storage: {store_err}")
                        # If we can't store it, we need to fail to prevent infinite retry loops
                        raise ValueError(f"Storage failure for {filename}: {store_err}")

            # Save local temp .md for troubleshooting
            try:
                md_path = os.path.join(tempfile.gettempdir(), md_filename)
                with open(md_path, "w", encoding="utf-8") as mdfile:
                    mdfile.write(content)
                db_logger.info(f"Canonical markdown saved locally at {md_path}")
            except Exception as tmp_err:
                db_logger.debug(f"Skipping local markdown save: {tmp_err}")

            # Index into vector-service (use original filename as doc_id) - skip for failed conversions
            doc_id = filename
            chunk_texts = []
            embeddings_status = "skipped"
            
            if conversion_strategy not in ["conversion_failed", "conversion_error"]:
                db_logger.info(f"Adding document {doc_id} to vector-service store...")
                chunk_texts = self.add_document(content, doc_id)
                embeddings_status = "completed"
                _ws_broadcast(f"EMBEDDINGS_ADDED: {len(chunk_texts)}")
                try:
                    from app.core.event_bus import get_event_bus
                    asyncio.create_task(
                        get_event_bus().publish(
                            "embeddings_added", {"project_id": self.project_id, "count": len(chunk_texts)}
                        )
                    )
                except Exception:
                    pass
            else:
                db_logger.info(f"Skipping embeddings for {doc_id} due to conversion failure")
                _ws_broadcast(f"EMBEDDINGS_SKIPPED: {filename} (conversion failed)")

            # Entity extraction and graph update - skip for failed conversions
            db_logger.info(f"Extracting entities from {doc_id} via graph-service...")
            try:
                file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
            except Exception:
                file_size_mb = len(content) / (1024 * 1024)
            entities_status = "skipped_conversion_failed"
            
            if conversion_strategy not in ["conversion_failed", "conversion_error"]:
                # Always delegate to graph-service regardless of local LLM availability
                self.extract_and_add_entities(content, file_size_mb, precomputed_chunks=chunk_texts)
                entities_status = "extracted"
                _ws_broadcast("GRAPH_UPDATED")
            else:
                db_logger.info(f"Skipping entity extraction for {doc_id} due to conversion failure")

            # Metadata snapshot
            try:
                raw_size = None
                try:
                    raw_size = os.path.getsize(file_path)
                except Exception:
                    pass
                meta = {
                    "project_id": self.project_id,
                    "source_filename": filename,
                    "md_filename": md_filename,
                    "conversion_strategy": conversion_strategy,
                    "reprocess": bool(reprocess),
                    "raw_size_bytes": raw_size,
                    "md_size_bytes": len(content.encode("utf-8")),
                    "processed_at": datetime.now(timezone.utc).isoformat(),
                    "embeddings_chunks": len(chunk_texts),
                    "embeddings_status": embeddings_status,
                    "entities_status": entities_status,
                    "conversion_success": conversion_strategy not in ["conversion_failed", "conversion_error"],
                }
                storage.upload_text(
                    self.project_id,
                    "metadata",
                    os.path.splitext(filename)[0] + ".json",
                    json.dumps(meta, ensure_ascii=False, indent=2),
                    content_type="application/json",
                )
            except Exception as me:
                db_logger.debug(f"Failed to write metadata for {filename}: {me}")

            chromadb_status = "delegated"
            neo4j_status = "delegated"
            llm_status = "available" if self.llm else "unavailable"
            
            if conversion_strategy in ["conversion_failed", "conversion_error"]:
                db_logger.warning(
                    f"Document processing completed with conversion failure for {doc_id}. "
                    f"Conversion: {conversion_strategy}, Embeddings: {embeddings_status}, Entities: {entities_status}"
                )
                return f"Processed {doc_id} with conversion failure - metadata recorded for retry. Enable reprocess=True to retry conversion."
            else:
                db_logger.info(
                    f"Document processing completed successfully for {doc_id}. "
                    f"Strategy: {conversion_strategy}, Chunks: {len(chunk_texts)}, "
                    f"Services: Vectors={chromadb_status}, Graph={neo4j_status}, LLM={llm_status}"
                )
                return f"Successfully processed and added {doc_id} to the knowledge base with {len(chunk_texts)} chunks."
        except Exception as e:
            db_logger.error(f"Error processing file {file_path}: {str(e)}")
            return f"Error processing file {file_path}: {str(e)}"

    def add_document(self, content: str, doc_id: str):
        """Adds a document to the vector store via vector-service and returns chunk texts."""
        try:
            clean_content = sanitize_agent_output(content)
            # Split content into chunks for better retrieval
            chunks = self._split_content(clean_content)

            # Build documents payload for vector-service
            documents = []
            for i, chunk in enumerate(chunks):
                documents.append({
                    "id": f"{doc_id}_chunk_{i}",
                    "content": chunk,
                    "filename": doc_id,
                    "source": "rag_service"
                })

            async def _push():
                client = await get_service_client()
                try:
                    await client.create_vector_collection(self.project_id)
                except Exception:
                    pass
                await client.add_documents_to_vectors(self.project_id, documents)
            import anyio
            anyio.run(_push)

            db_logger.info(f"Added document {doc_id} with {len(chunks)} chunks via vector-service")
            return chunks
        except Exception as e:
            db_logger.error(f"Error adding document {doc_id}: {str(e)}")
            raise

    def _get_project_context_preface(self):
        """Preface retrieval delegated; not available via vector-service API."""
        return None

    def _split_content(self, content: str, chunk_size: int = 500, overlap: int = 50):
        """Split content using advanced chunking strategies."""
        try:
            if self.chunking_strategy == 'semantic':
                # Use the same optimized chunking as entity extraction for consistency
                try:
                    from app.core.semantic_chunking import OptimizedChunker

                    # Calculate file size for strategy selection
                    file_size_mb = len(content) / (1024 * 1024)

                    # Use optimized chunker for consistency with entity extraction
                    optimized_chunker = OptimizedChunker()
                    chunks, strategy = optimized_chunker.process_document(content, file_size_mb)

                    # Convert DocumentChunk objects to text strings for ChromaDB
                    text_chunks = [chunk.content for chunk in chunks]

                    db_logger.info(f"Optimized chunking: {len(text_chunks)} chunks using '{strategy}' strategy, avg size: {sum(len(c) for c in text_chunks)//len(text_chunks)} chars")
                    return text_chunks

                except ImportError:
                    # Fallback to original semantic chunking if optimized not available
                    semantic_chunks = self.semantic_chunker.chunk_text(content, chunk_method="semantic")

                    # Log chunk quality metrics
                    if semantic_chunks:
                        avg_coherence = sum(chunk.coherence_score for chunk in semantic_chunks) / len(semantic_chunks)
                        avg_size = sum(len(chunk.content) for chunk in semantic_chunks) / len(semantic_chunks)
                        db_logger.info(f"Semantic chunking: {len(semantic_chunks)} chunks, avg coherence: {avg_coherence:.3f}, avg size: {avg_size:.0f} chars")

                    return [chunk.content for chunk in semantic_chunks]

            elif self.chunking_strategy == 'hybrid':
                # Use hybrid chunking (semantic + rule-based)
                hybrid_chunks = self.semantic_chunker.chunk_text(content, chunk_method="hybrid")

                # Log chunk quality metrics
                if hybrid_chunks:
                    avg_coherence = sum(chunk.coherence_score for chunk in hybrid_chunks) / len(hybrid_chunks)
                    avg_size = sum(len(chunk.content) for chunk in hybrid_chunks) / len(hybrid_chunks)
                    db_logger.info(f"Hybrid chunking: {len(hybrid_chunks)} chunks, avg coherence: {avg_coherence:.3f}, avg size: {avg_size:.0f} chars")

                return [chunk.content for chunk in hybrid_chunks]

            else:
                # Fallback to word-based chunking
                chunks = self._word_based_chunking(content, chunk_size, overlap)
                db_logger.info(f"Word-based chunking: {len(chunks)} chunks, avg size: {sum(len(c) for c in chunks) / len(chunks):.0f} chars")
                return chunks

        except Exception as e:
            db_logger.error(f"Error in semantic chunking: {str(e)}, falling back to word-based")
            chunks = self._word_based_chunking(content, chunk_size, overlap)
            db_logger.info(f"Fallback word-based chunking: {len(chunks)} chunks")
            return chunks

    def _word_based_chunking(self, content: str, chunk_size: int = 500, overlap: int = 50):
        """Fallback word-based chunking method."""
        words = content.split()
        chunks = []

        for i in range(0, len(words), chunk_size - overlap):
            chunk = ' '.join(words[i:i + chunk_size])
            if chunk.strip():  # Only add non-empty chunks
                chunks.append(chunk)

        return chunks if chunks else [content]  # Return original if no chunks created

    def _batch_insert_chunks(self, chunks: List[str], doc_id: str):
        """Deprecated: insertion handled by vector-service."""
        return

    def _sanitize_relationship_type(self, relationship_type: str) -> str:
        """
        Sanitize relationship type for Neo4j compatibility.
        Neo4j relationship types cannot contain spaces or special characters.
        Converts spaces and special characters to underscores.
        """
        if not relationship_type:
            return "RELATED_TO"
        
        # Convert to uppercase and replace problematic characters
        sanitized = relationship_type.upper()
        # Replace spaces, hyphens, dots, and other special chars with underscores
        sanitized = "".join(c if c.isalnum() else "_" for c in sanitized)
        # Remove consecutive underscores
        while "__" in sanitized:
            sanitized = sanitized.replace("__", "_")
        # Remove leading/trailing underscores
        sanitized = sanitized.strip("_")
        
        # Ensure it's not empty and starts with a letter or underscore
        if not sanitized or sanitized[0].isdigit():
            sanitized = f"REL_{sanitized}" if sanitized else "RELATED_TO"
            
        return sanitized

    def extract_and_add_entities(self, content: str, file_size_mb: float = 0.0, precomputed_chunks: list = None):
        """Extract entities/relationships via graph-service. Local Neo4j fallback removed."""
        try:
            db_logger.info(f"Starting entity extraction for project {self.project_id}, content length: {len(content)} chars")
            
            # Stream initial progress log
            self._stream_log_sync("INFO", f"Starting entity extraction process", {
                "content_length": len(content),
                "file_size_mb": file_size_mb,
                "has_precomputed_chunks": precomputed_chunks is not None,
                "chunk_count": len(precomputed_chunks) if precomputed_chunks else 0
            })

            # Always delegate to graph-service for extraction and upsert
            try:
                self._stream_log_sync("INFO", "Delegating entity extraction to graph-service", {"service": "graph-service"})
                import concurrent.futures, asyncio, contextvars, uuid as _uuid
                def run_graph_extract():
                    async def _call():
                        client = await get_service_client()
                        doc_id = f"md-{_uuid.uuid4().hex[:8]}"
                        payload = {"document_content": content, "filename": f"{doc_id}.md", "document_id": doc_id}
                        return await client.extract_entities(self.project_id, payload)
                    try:
                        cid = correlation_id_ctx.get()
                    except Exception:
                        cid = None
                    if cid:
                        ctx = contextvars.copy_context()
                        ctx.run(lambda: correlation_id_ctx.set(cid))
                    return asyncio.run(_call())
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                    result = ex.submit(run_graph_extract).result(timeout=300)
                entities_created = int(result.get("entities_found", 0))
                relationships_created = int(result.get("relationships_found", 0))
                self._stream_log_sync("INFO", "Graph-service extraction complete", {
                    "entities_created": entities_created,
                    "relationships_created": relationships_created,
                    "processing_time_ms": result.get("processing_time_ms")
                })
                db_logger.info(f"Graph-service extraction complete: entities={entities_created} relationships={relationships_created}")
                return
            except Exception as gs_err:
                msg = f"Graph-service extraction failed or unavailable: {gs_err}"
                db_logger.warning(msg)
                self._stream_log_sync("WARNING", msg)
                return
        except Exception as e:
            error_msg = f"Error in entity extraction: {str(e)}"
            db_logger.error(error_msg)
            
            # Stream extraction failure
            self._stream_log_sync("ERROR", "Entity extraction process failed", {
                "error": str(e),
                "error_type": type(e).__name__,
                "project_id": self.project_id
            })
            
            raise

    def query(self, question: str, n_results: int = 5):
        """Perform semantic search via vector-service and optionally synthesize with LLM."""
        db_logger.info(f"Querying vector-service for project {self.project_id} with question: {question}")
        try:
            import anyio
            async def _search():
                client = await get_service_client()
                try:
                    res = await client.vector_search(self.project_id, question, limit=n_results)
                except Exception as e:
                    db_logger.warning(f"Primary vector search failed, trying hybrid: {e}")
                    res = await client.hybrid_search(self.project_id, question, limit=n_results)
                return res
            result = anyio.run(_search)
            docs = []
            for item in result.get("results", []) or []:
                content = item.get("content") or ""
                meta = item.get("metadata") or {}
                filename = meta.get("filename", "unknown")
                if content:
                    docs.append(f"[From {filename}]: {content}")
            if not docs:
                return "No relevant information found in the knowledge base."
            if self.llm:
                return self._synthesize_response(question, docs)
            return "\n\n".join(docs)
        except Exception as e:
            db_logger.error(f"Error in vector-service search: {str(e)}")
            return "Error occurred while searching the knowledge base."

    def _synthesize_response(self, question: str, context_docs: list) -> str:
        """Use LLM to synthesize a coherent response from retrieved context."""
        try:
            # Combine all context documents
            context = "\n\n".join(context_docs)

            # Create a prompt for the LLM to synthesize the response
            synthesis_prompt = f"""You are an expert cloud migration consultant. Based on the following context from the project documents, provide a comprehensive and helpful answer to the user's question.

Context from project documents:
{context}

User Question: {question}

Please provide a clear, detailed answer based on the information in the context. If the context doesn't contain enough information to fully answer the question, mention what information is available and what might be missing. Format your response in a professional, consultant-like manner.

Answer:"""

            # Get response from LLM with proper method detection
            try:
                if hasattr(self.llm, 'invoke'):
                    response = self.llm.invoke(synthesis_prompt)
                elif hasattr(self.llm, 'generate'):
                    response = self.llm.generate([synthesis_prompt])
                elif hasattr(self.llm, '__call__'):
                    response = self.llm(synthesis_prompt)
                else:
                    db_logger.error(f"LLM object {type(self.llm)} has no recognized method (invoke, generate, __call__)")
                    return "\n\n".join(context_docs)
            except Exception as llm_error:
                db_logger.error(f"LLM invocation failed: {str(llm_error)}")
                return "\n\n".join(context_docs)

            # Extract content from response (handle different LLM response formats)
            if hasattr(response, 'content'):
                synthesized_answer = response.content
            elif isinstance(response, str):
                synthesized_answer = response
            elif hasattr(response, 'generations') and response.generations:
                # Handle LangChain LLMResult format
                synthesized_answer = response.generations[0][0].text
            else:
                synthesized_answer = str(response)

            db_logger.info("Successfully synthesized response using LLM")
            return synthesized_answer

        except Exception as e:
            db_logger.error(f"Error synthesizing response with LLM: {str(e)}")
            # Fallback to raw context if LLM synthesis fails
            return "\n\n".join(context_docs)

    def cleanup(self):
        """Clean up resources and connections"""
        try:
            pass
        except Exception as e:
            db_logger.warning(f"Error cleaning up ChromaDB client: {str(e)}")

        # No local graph client to release

    def get_service_status(self):
        """Get the status of all integrated services"""
        status = {
            "vector_store": {"available": False, "ready": False, "error": None},
            "graph": {"available": False, "ready": False, "error": None},
            "llm": {"available": bool(self.llm), "ready": bool(self.llm), "error": None},
        }
        try:
            import anyio
            async def _check():
                client = await get_service_client()
                try:
                    v = await client.check_service_health("vector")
                    status["vector_store"]["available"] = True
                    status["vector_store"]["ready"] = (v or {}).get("status") == "healthy"
                except Exception as e:
                    status["vector_store"]["error"] = str(e)
                try:
                    g = await client.check_service_health("graph")
                    status["graph"]["available"] = True
                    status["graph"]["ready"] = (g or {}).get("status") in ("healthy", "ok")
                except Exception as e:
                    status["graph"]["error"] = str(e)
            anyio.run(_check)
        except Exception as e:
            db_logger.debug(f"Service status probe failed: {e}")
        return status

    def _split_content_into_chunks(self, content: str, chunk_size: int) -> list:
        """Split content into chunks of specified size, trying to break at sentence boundaries."""
        if len(content) <= chunk_size:
            return [content]

        chunks = []
        current_pos = 0

        while current_pos < len(content):
            # Calculate the end position for this chunk
            end_pos = min(current_pos + chunk_size, len(content))

            # If this is not the last chunk, try to find a good break point
            if end_pos < len(content):
                # Look for sentence endings within the last 200 characters of the chunk
                search_start = max(current_pos, end_pos - 200)

                # Look for sentence endings (., !, ?, \n)
                sentence_endings = []
                for i in range(search_start, end_pos):
                    if content[i] in '.!?\n':
                        sentence_endings.append(i)

                # Use the last sentence ending if found
                if sentence_endings:
                    end_pos = sentence_endings[-1] + 1
                # Otherwise, look for word boundaries (spaces)
                else:
                    for i in range(end_pos - 1, search_start, -1):
                        if content[i] == ' ':
                            end_pos = i
                            break

            # Extract the chunk
            chunk = content[current_pos:end_pos].strip()
            if chunk:  # Only add non-empty chunks
                chunks.append(chunk)

            current_pos = end_pos

            # Skip any leading whitespace for the next chunk
            while current_pos < len(content) and content[current_pos].isspace():
                current_pos += 1

        return chunks

    def __del__(self):
        """Destructor to ensure cleanup"""
        self.cleanup()
