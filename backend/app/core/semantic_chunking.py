"""
Intelligent Semantic Chunking for Document Processing
Implements smart chunking strategies that preserve context and reduce processing time
"""

import re
import logging
from typing import List, Dict, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class DocumentChunk:
    """Represents a semantically meaningful chunk of text"""
    content: str
    chunk_id: int
    start_pos: int
    end_pos: int
    chunk_type: str  # 'paragraph', 'section', 'table', 'list'
    metadata: Dict = None


class SemanticChunker:
    """Advanced chunking that preserves semantic meaning and context"""
    
    def __init__(self, max_chunk_size: int = 8000, overlap_size: int = 200):
        self.max_chunk_size = max_chunk_size
        self.overlap_size = overlap_size
        
    def chunk_document(self, content: str, document_type: str = "pdf") -> List[DocumentChunk]:
        """
        Intelligently chunk document based on semantic boundaries
        
        Args:
            content: Full document text
            document_type: Type of document (pdf, docx, etc.)
            
        Returns:
            List of semantic chunks with preserved context
        """
        logger.info(f"Starting semantic chunking of {len(content)} characters")
        
        # Strategy 1: Try section-based chunking first
        chunks = self._chunk_by_sections(content)
        
        # Strategy 2: If sections too large, use paragraph-based chunking
        if any(len(chunk.content) > self.max_chunk_size for chunk in chunks):
            logger.info("Sections too large, switching to paragraph-based chunking")
            chunks = self._chunk_by_paragraphs(content)
        
        # Strategy 3: If still too large, use sentence-based chunking
        if any(len(chunk.content) > self.max_chunk_size for chunk in chunks):
            logger.info("Paragraphs too large, switching to sentence-based chunking")
            chunks = self._chunk_by_sentences(content)
        
        # Add overlap between chunks to preserve context
        chunks = self._add_overlap(chunks, content)
        
        logger.info(f"Created {len(chunks)} semantic chunks (avg size: {sum(len(c.content) for c in chunks) // len(chunks)} chars)")
        
        return chunks
    
    def _chunk_by_sections(self, content: str) -> List[DocumentChunk]:
        """Chunk by document sections (headers, etc.)"""
        chunks = []
        
        # Look for section headers (various patterns)
        section_patterns = [
            r'\n\s*(?:CHAPTER|Chapter|SECTION|Section|PART|Part)\s+\d+[^\n]*\n',
            r'\n\s*\d+\.\s+[A-Z][^\n]*\n',  # 1. SECTION TITLE
            r'\n\s*[A-Z][A-Z\s]{10,}[A-Z]\s*\n',  # ALL CAPS HEADERS
            r'\n\s*#{1,6}\s+[^\n]+\n',  # Markdown headers
        ]
        
        split_positions = [0]
        
        for pattern in section_patterns:
            matches = list(re.finditer(pattern, content, re.MULTILINE))
            split_positions.extend([m.start() for m in matches])
        
        split_positions = sorted(set(split_positions))
        split_positions.append(len(content))
        
        for i in range(len(split_positions) - 1):
            start = split_positions[i]
            end = split_positions[i + 1]
            chunk_content = content[start:end].strip()
            
            if len(chunk_content) > 100:  # Skip tiny chunks
                chunks.append(DocumentChunk(
                    content=chunk_content,
                    chunk_id=i,
                    start_pos=start,
                    end_pos=end,
                    chunk_type='section',
                    metadata={'section_number': i}
                ))
        
        return chunks if chunks else [DocumentChunk(content, 0, 0, len(content), 'full_document')]
    
    def _chunk_by_paragraphs(self, content: str) -> List[DocumentChunk]:
        """Chunk by paragraphs, combining small ones"""
        paragraphs = re.split(r'\n\s*\n', content)
        chunks = []
        current_chunk = ""
        chunk_id = 0
        start_pos = 0
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
                
            # If adding this paragraph would exceed max size, finalize current chunk
            if current_chunk and len(current_chunk) + len(para) > self.max_chunk_size:
                chunks.append(DocumentChunk(
                    content=current_chunk.strip(),
                    chunk_id=chunk_id,
                    start_pos=start_pos,
                    end_pos=start_pos + len(current_chunk),
                    chunk_type='paragraph_group'
                ))
                chunk_id += 1
                start_pos += len(current_chunk)
                current_chunk = ""
            
            current_chunk += para + "\n\n"
        
        # Add final chunk
        if current_chunk.strip():
            chunks.append(DocumentChunk(
                content=current_chunk.strip(),
                chunk_id=chunk_id,
                start_pos=start_pos,
                end_pos=start_pos + len(current_chunk),
                chunk_type='paragraph_group'
            ))
        
        return chunks
    
    def _chunk_by_sentences(self, content: str) -> List[DocumentChunk]:
        """Chunk by sentences when other methods fail"""
        # Simple sentence splitting
        sentences = re.split(r'(?<=[.!?])\s+', content)
        chunks = []
        current_chunk = ""
        chunk_id = 0
        start_pos = 0
        
        for sentence in sentences:
            if current_chunk and len(current_chunk) + len(sentence) > self.max_chunk_size:
                chunks.append(DocumentChunk(
                    content=current_chunk.strip(),
                    chunk_id=chunk_id,
                    start_pos=start_pos,
                    end_pos=start_pos + len(current_chunk),
                    chunk_type='sentence_group'
                ))
                chunk_id += 1
                start_pos += len(current_chunk)
                current_chunk = ""
            
            current_chunk += sentence + " "
        
        # Add final chunk
        if current_chunk.strip():
            chunks.append(DocumentChunk(
                content=current_chunk.strip(),
                chunk_id=chunk_id,
                start_pos=start_pos,
                end_pos=start_pos + len(current_chunk),
                chunk_type='sentence_group'
            ))
        
        return chunks
    
    def _add_overlap(self, chunks: List[DocumentChunk], full_content: str) -> List[DocumentChunk]:
        """Add overlap between chunks to preserve context"""
        if len(chunks) <= 1:
            return chunks
        
        overlapped_chunks = []
        
        for i, chunk in enumerate(chunks):
            content = chunk.content
            
            # Add overlap from previous chunk
            if i > 0:
                prev_chunk = chunks[i - 1]
                overlap_start = max(0, len(prev_chunk.content) - self.overlap_size)
                overlap_text = prev_chunk.content[overlap_start:]
                content = f"[Previous context: {overlap_text}]\n\n{content}"
            
            # Add overlap from next chunk
            if i < len(chunks) - 1:
                next_chunk = chunks[i + 1]
                overlap_end = min(len(next_chunk.content), self.overlap_size)
                overlap_text = next_chunk.content[:overlap_end]
                content = f"{content}\n\n[Next context: {overlap_text}]"
            
            overlapped_chunks.append(DocumentChunk(
                content=content,
                chunk_id=chunk.chunk_id,
                start_pos=chunk.start_pos,
                end_pos=chunk.end_pos,
                chunk_type=chunk.chunk_type,
                metadata=chunk.metadata
            ))
        
        return overlapped_chunks


class OptimizedChunker:
    """Optimized chunker for faster processing with better results"""
    
    def __init__(self):
        self.semantic_chunker = SemanticChunker(max_chunk_size=12000, overlap_size=300)
    
    def get_processing_strategy(self, content: str, file_size_mb: float) -> str:
        """Determine the best processing strategy based on content size"""
        
        if file_size_mb < 0.5:  # Small files
            return "single_pass"
        elif file_size_mb < 2.0:  # Medium files
            return "semantic_chunks"
        else:  # Large files
            return "hierarchical_extraction"
    
    def process_document(self, content: str, file_size_mb: float) -> Tuple[List[DocumentChunk], str]:
        """
        Process document with optimal strategy
        
        Returns:
            Tuple of (chunks, strategy_used)
        """
        strategy = self.get_processing_strategy(content, file_size_mb)
        
        if strategy == "single_pass":
            # For small files, process as single chunk
            chunks = [DocumentChunk(
                content=content,
                chunk_id=0,
                start_pos=0,
                end_pos=len(content),
                chunk_type='full_document'
            )]
            
        elif strategy == "semantic_chunks":
            # Use semantic chunking for medium files
            chunks = self.semantic_chunker.chunk_document(content)
            
        else:  # hierarchical_extraction
            # For large files, use hierarchical approach
            chunks = self._hierarchical_chunking(content)
        
        logger.info(f"Using strategy '{strategy}' - created {len(chunks)} chunks")
        return chunks, strategy
    
    def _hierarchical_chunking(self, content: str) -> List[DocumentChunk]:
        """
        Hierarchical chunking for very large documents
        First extract high-level structure, then detailed entities
        """
        # Step 1: Create larger chunks for high-level extraction
        large_chunks = self.semantic_chunker.chunk_document(content)
        
        # Step 2: If still too many chunks, combine related ones
        if len(large_chunks) > 20:
            combined_chunks = []
            current_combined = ""
            chunk_id = 0
            
            for i, chunk in enumerate(large_chunks):
                if len(current_combined) + len(chunk.content) > 15000:
                    if current_combined:
                        combined_chunks.append(DocumentChunk(
                            content=current_combined,
                            chunk_id=chunk_id,
                            start_pos=0,
                            end_pos=len(current_combined),
                            chunk_type='combined_section'
                        ))
                        chunk_id += 1
                    current_combined = chunk.content
                else:
                    current_combined += "\n\n" + chunk.content
            
            # Add final combined chunk
            if current_combined:
                combined_chunks.append(DocumentChunk(
                    content=current_combined,
                    chunk_id=chunk_id,
                    start_pos=0,
                    end_pos=len(current_combined),
                    chunk_type='combined_section'
                ))
            
            return combined_chunks
        
        return large_chunks
