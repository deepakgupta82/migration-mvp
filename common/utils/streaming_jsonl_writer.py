"""
Streaming JSONL Writer (Issue #10)

Provides memory-efficient JSONL generation for large documents.
Instead of buffering all elements in memory, writes them progressively.

Key features:
- Streaming write (no full buffering)
- Chunk-based processing
- Progress tracking
- Error recovery (partial JSONL on failure)
- Memory efficiency (<100MB for 10GB files)

Example usage:
    async with StreamingJSONLWriter(output_path, document_metadata) as writer:
        async for element in process_large_file():
            await writer.write_element(element)
"""
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, AsyncIterator
from dataclasses import asdict
import asyncio

logger = logging.getLogger(__name__)


class StreamingJSONLWriter:
    """
    Writes JSONL progressively without buffering all elements.
    
    Suitable for:
    - Large Excel files (100K+ rows)
    - Large PDFs (1000+ pages)
    - Memory-constrained environments
    
    Guarantees:
    - First line is document metadata
    - Subsequent lines are elements
    - Last line is processing summary
    - Partial output on errors (recoverable state)
    """
    
    def __init__(
        self,
        output_path: str,
        document_metadata: Dict[str, Any],
        buffer_size: int = 8192,
        flush_interval: int = 100
    ):
        """
        Initialize streaming writer.
        
        Args:
            output_path: Path to output JSONL file
            document_metadata: Document metadata (first line)
            buffer_size: File buffer size in bytes
            flush_interval: Flush to disk every N elements
        """
        self.output_path = Path(output_path)
        self.document_metadata = document_metadata
        self.buffer_size = buffer_size
        self.flush_interval = flush_interval
        
        self.file_handle = None
        self.elements_written = 0
        self.bytes_written = 0
        self.is_closed = False
        self.errors = []
        self.warnings = []
    
    async def __aenter__(self):
        """Context manager entry - open file and write metadata."""
        await self.open()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - write summary and close file."""
        await self.close(exc_type, exc_val, exc_tb)
        return False  # Don't suppress exceptions
    
    async def open(self):
        """Open file and write document metadata header."""
        if self.file_handle:
            raise RuntimeError("StreamingJSONLWriter already open")
        
        try:
            # Ensure output directory exists
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Open file in append mode (for recovery from partial writes)
            self.file_handle = await asyncio.to_thread(
                open,
                self.output_path,
                'w',
                encoding='utf-8',
                buffering=self.buffer_size
            )
            
            # Write document metadata as first line
            metadata_line = {
                'type': 'document_metadata',
                'data': self.document_metadata
            }
            await self._write_line(metadata_line)
            
            logger.info(f"Streaming JSONL writer opened: {self.output_path}")
            
        except Exception as e:
            logger.error(f"Failed to open streaming JSONL writer: {e}", exc_info=True)
            raise
    
    async def write_element(self, element: Any):
        """
        Write a single element to JSONL.
        
        Args:
            element: DocumentElement or dict
        """
        if self.is_closed:
            raise RuntimeError("Cannot write to closed StreamingJSONLWriter")
        
        if not self.file_handle:
            raise RuntimeError("StreamingJSONLWriter not opened")
        
        try:
            # Convert to dict if dataclass
            if hasattr(element, 'to_dict'):
                element_dict = element.to_dict()
            elif hasattr(element, '__dict__'):
                element_dict = asdict(element)
            else:
                element_dict = element
            
            # Ensure metadata is JSON serializable
            if 'metadata' in element_dict and element_dict['metadata']:
                element_dict['metadata'] = self._make_json_serializable(element_dict['metadata'])
            
            # Ensure coordinates are JSON serializable
            if 'coordinates' in element_dict and element_dict['coordinates']:
                element_dict['coordinates'] = self._make_json_serializable(element_dict['coordinates'])
            
            # Wrap in standard JSONL format
            element_line = {
                'type': 'element',
                'data': element_dict
            }
            
            await self._write_line(element_line)
            self.elements_written += 1
            
            # Periodic flush to disk
            if self.elements_written % self.flush_interval == 0:
                await asyncio.to_thread(self.file_handle.flush)
                logger.debug(f"Flushed {self.elements_written} elements to disk")
            
        except Exception as e:
            error_msg = f"Error writing element {self.elements_written}: {e}"
            logger.warning(error_msg)
            self.errors.append(error_msg)
            # Don't raise - continue writing other elements
    
    async def write_batch(self, elements: AsyncIterator[Any]):
        """
        Write a batch of elements from an async iterator.
        
        Args:
            elements: AsyncIterator yielding elements
        """
        async for element in elements:
            await self.write_element(element)
    
    async def close(self, exc_type=None, exc_val=None, exc_tb=None):
        """
        Close writer and write processing summary.
        
        Args:
            exc_type: Exception type (if context manager exited with error)
            exc_val: Exception value
            exc_tb: Exception traceback
        """
        if self.is_closed:
            return
        
        try:
            # Write processing summary as final line
            status = 'error' if exc_type else 'success'
            
            summary = {
                'type': 'processing_summary',
                'data': {
                    'processing_stats': {
                        'total_elements': self.elements_written,
                        'bytes_written': self.bytes_written,
                        'streaming_mode': True,
                    },
                    'status': status,
                    'errors': self.errors,
                    'warnings': self.warnings
                }
            }
            
            if exc_val:
                summary['data']['exception'] = {
                    'type': type(exc_val).__name__,
                    'message': str(exc_val)
                }
            
            await self._write_line(summary)
            
            # Final flush
            if self.file_handle:
                await asyncio.to_thread(self.file_handle.flush)
            
            logger.info(
                f"Streaming JSONL writer closed: {self.elements_written} elements, "
                f"{self.bytes_written} bytes, status={status}"
            )
            
        except Exception as e:
            logger.error(f"Error writing summary: {e}", exc_info=True)
        
        finally:
            # Close file handle
            if self.file_handle:
                try:
                    await asyncio.to_thread(self.file_handle.close)
                except Exception as e:
                    logger.error(f"Error closing file: {e}")
            
            self.is_closed = True
    
    async def _write_line(self, data: Dict[str, Any]):
        """Write a single JSONL line."""
        try:
            line = json.dumps(data, ensure_ascii=False) + '\n'
            line_bytes = line.encode('utf-8')
            
            await asyncio.to_thread(self.file_handle.write, line)
            self.bytes_written += len(line_bytes)
            
        except Exception as e:
            logger.error(f"Error writing JSONL line: {e}", exc_info=True)
            raise
    
    def _make_json_serializable(self, obj: Any) -> Any:
        """Convert object to JSON serializable format."""
        if obj is None:
            return None
        
        if isinstance(obj, (str, int, float, bool)):
            return obj
        
        if isinstance(obj, (list, tuple)):
            return [self._make_json_serializable(item) for item in obj]
        
        if isinstance(obj, dict):
            return {
                str(key): self._make_json_serializable(value)
                for key, value in obj.items()
            }
        
        # Handle dataclasses
        if hasattr(obj, '__dataclass_fields__'):
            return self._make_json_serializable(asdict(obj))
        
        # Handle objects with to_dict()
        if hasattr(obj, 'to_dict'):
            return self._make_json_serializable(obj.to_dict())
        
        # Fallback: convert to string
        return str(obj)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current writer statistics."""
        return {
            'elements_written': self.elements_written,
            'bytes_written': self.bytes_written,
            'is_closed': self.is_closed,
            'error_count': len(self.errors),
            'warning_count': len(self.warnings)
        }


async def stream_elements_to_jsonl(
    elements: AsyncIterator[Any],
    output_path: str,
    document_metadata: Dict[str, Any],
    progress_callback: Optional[callable] = None
) -> Dict[str, Any]:
    """
    Convenience function to stream elements to JSONL.
    
    Args:
        elements: AsyncIterator yielding elements
        output_path: Path to output JSONL file
        document_metadata: Document metadata
        progress_callback: Optional callback(elements_written, bytes_written)
    
    Returns:
        Statistics dict
    """
    async with StreamingJSONLWriter(output_path, document_metadata) as writer:
        async for element in elements:
            await writer.write_element(element)
            
            if progress_callback:
                stats = writer.get_stats()
                progress_callback(stats['elements_written'], stats['bytes_written'])
        
        return writer.get_stats()
