"""
Semantic/Paragraph Chunking Utility for Document Service
Enhanced with JSONL-aware chunking for better context preservation.

- Supports strategies: 'semantic', 'paragraph', 'rule_based', 'jsonl_aware'
- Semantic uses sentence-transformers if available, falls back to paragraph-based
- JSONL-aware respects document structure and element boundaries
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import re
import logging
import os
import threading
import asyncio
import json
from typing import Optional

logger = logging.getLogger("document-service.semantic_chunking")

# Global model caching for improved performance
_semantic_model = None
_model_loading_lock = threading.Lock()
_model_load_failed = False

def _load_semantic_model():
    """Load semantic model with error handling and caching"""
    global _semantic_model, _model_load_failed
    
    if _semantic_model is not None:
        return _semantic_model
    
    if _model_load_failed:
        return None
    
    try:
        from sentence_transformers import SentenceTransformer
        try:
            from app.core.config_client import cfg_get
            model_name = cfg_get(["document_service", "semantic_model"], os.getenv("SEMANTIC_MODEL", "all-MiniLM-L6-v2"))
        except Exception:
            model_name = os.getenv("SEMANTIC_MODEL", "all-MiniLM-L6-v2")
        
        logger.info(f"Loading semantic model: {model_name}")
        _semantic_model = SentenceTransformer(model_name)
        logger.info("Semantic model loaded successfully")
        return _semantic_model
    except Exception as e:
        logger.warning(f"Failed to load semantic model: {e}")
        _model_load_failed = True
        return None


@dataclass
class Chunk:
    content: str
    index: int
    start: int
    end: int
    kind: str  # section | paragraph | sentence | full | element
    metadata: Optional[Dict[str, Any]] = None  # ENHANCED: Store element metadata


@dataclass
class JsonlElement:
    """Represents a structured element from JSONL processing"""
    type: str  # title, text, table, list_item, etc.
    content: str
    metadata: Dict[str, Any]
    page_number: Optional[int] = None
    element_id: Optional[str] = None


class SemanticChunker:
    def __init__(self, max_len: Optional[int] = None, overlap: Optional[int] = None):
        try:
            from app.core.config_client import cfg_get
            self.max_len = int(cfg_get(["document_service", "semantic_max_chunk"], os.getenv("SEMANTIC_MAX_CHUNK", str(max_len or 2000))))
            self.overlap = int(cfg_get(["document_service", "semantic_overlap"], os.getenv("SEMANTIC_OVERLAP", str(overlap or 200))))
        except Exception:
            self.max_len = int(os.getenv("SEMANTIC_MAX_CHUNK", str(max_len or 2000)))
            self.overlap = int(os.getenv("SEMANTIC_OVERLAP", str(overlap or 200)))
        self._model = None

    def _ensure_model(self):
        """Ensure semantic model is loaded with thread-safe caching"""
        if self._model is None:
            with _model_loading_lock:
                # Double-check pattern for thread safety
                if self._model is None:
                    try:
                        self._model = _load_semantic_model()
                        if self._model:
                            logger.info("Loaded sentence-transformers model for semantic chunking")
                        else:
                            logger.warning("Semantic model unavailable, will use paragraph chunking")
                            self._model = False
                    except Exception as e:
                        logger.warning(f"Semantic model loading failed, falling back to paragraph chunking: {e}")
                        self._model = False

    def chunk(self, text: str, strategy: str = "semantic", jsonl_data: Optional[List[Dict[str, Any]]] = None) -> List[Chunk]:
        """
        Enhanced chunking with JSONL awareness
        
        Args:
            text: Text content to chunk
            strategy: Chunking strategy ('semantic', 'paragraph', 'jsonl_aware', etc.)
            jsonl_data: Optional JSONL element data for structure-aware chunking
        """
        if not text:
            return []
        strat = (strategy or "semantic").strip().lower()
        
        # ENHANCED: JSONL-aware chunking strategy
        if strat == "jsonl_aware" and jsonl_data:
            try:
                return self._jsonl_aware(text, jsonl_data)
            except Exception as e:
                logger.warning(f"JSONL-aware chunking failed, falling back to semantic: {e}")
                # Fall through to semantic chunking
        
        # Optimize strategy selection
        if strat in ("semantic",):
            # Only try to load model if we don't know it's failed
            if not _model_load_failed:
                self._ensure_model()
                if self._model:
                    try:
                        return self._semantic(text)
                    except Exception as e:
                        logger.warning(f"Semantic chunking failed, falling back to paragraph: {e}")
            # Fall back to paragraph chunking if semantic fails
            return self._paragraph(text)
        elif strat in ("paragraph",):
            return self._paragraph(text)
        elif strat in ("words", "word", "word_based"):
            return self._words(text)
        else:
            # default fixed-size character chunks
            return self._rule_based(text)

    def _paragraph(self, text: str) -> List[Chunk]:
        paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        chunks: List[Chunk] = []
        buf = ""
        start = 0
        idx = 0
        for p in paras:
            candidate = (buf + ("\n\n" if buf else "") + p)
            if len(candidate) <= self.max_len:
                buf = candidate
            else:
                if buf:
                    chunks.append(Chunk(buf, idx, start, start + len(buf), "paragraph"))
                    idx += 1
                    start += len(buf)
                # split long paragraph
                i = 0
                while i < len(p):
                    part = p[i:i + self.max_len]
                    chunks.append(Chunk(part, idx, start, start + len(part), "paragraph"))
                    idx += 1
                    start += len(part)
                    i += self.max_len - self.overlap
                buf = ""
        if buf:
            chunks.append(Chunk(buf, idx, start, start + len(buf), "paragraph"))

        return self._add_overlap(chunks)

    def _semantic(self, text: str) -> List[Chunk]:
        # simple sentence-based semantic boundary using embeddings similarity
        try:
            # Ensure model is loaded and available
            if not self._model or self._model is False:
                logger.warning("Semantic model not available, falling back to paragraph chunking")
                return self._paragraph(text)
                
            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
            if len(sentences) < 2:
                return [Chunk(text, 0, 0, len(text), "full")]
                
            embeddings = self._model.encode(sentences)
            import numpy as np
            sims = []
            for i in range(len(embeddings) - 1):
                a, b = embeddings[i], embeddings[i + 1]
                sim = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))
                sims.append(sim)
            mean, std = float(np.mean(sims)), float(np.std(sims))
            threshold = mean - 0.5 * std
            boundaries = [0] + [i + 1 for i, s in enumerate(sims) if s < threshold]
            if boundaries[-1] != len(sentences):
                boundaries.append(len(sentences))
            pieces: List[Chunk] = []
            idx = 0
            pos = 0
            for i in range(len(boundaries) - 1):
                seg = " ".join(sentences[boundaries[i]:boundaries[i + 1]])
                while len(seg) > self.max_len:
                    part = seg[: self.max_len]
                    pieces.append(Chunk(part, idx, pos, pos + len(part), "sentence"))
                    idx += 1
                    pos += len(part)
                    seg = seg[self.max_len - self.overlap:]
                pieces.append(Chunk(seg, idx, pos, pos + len(seg), "sentence"))
                idx += 1
                pos += len(seg)
            return self._add_overlap(pieces)
        except Exception as e:
            logger.warning(f"Semantic chunking error, falling back to paragraph chunking: {e}")
            return self._paragraph(text)

    def _rule_based(self, text: str) -> List[Chunk]:
        # naive fixed-size split with overlaps
        chunks: List[Chunk] = []
        idx = 0
        start = 0
        while start < len(text):
            end = min(start + self.max_len, len(text))
            content = text[start:end]
            chunks.append(Chunk(content, idx, start, end, "fixed"))
            idx += 1
            if end == len(text):
                break
            start = end - self.overlap
        return chunks

    def _words(self, text: str) -> List[Chunk]:
        # word-count based chunking with approximate overlap
        try:
            max_words = max(50, int(os.getenv("SEMANTIC_WORDS_PER_CHUNK", "300")))
            overlap_words = max(0, int(os.getenv("SEMANTIC_WORDS_OVERLAP", "50")))
        except Exception:
            max_words = 300
            overlap_words = 50
        words = text.split()
        if not words:
            return []
        chunks: List[Chunk] = []
        idx = 0
        start_word = 0
        pos_char = 0
        # precompute word lengths incl. space
        lens = [len(w) + 1 for w in words]
        while start_word < len(words):
            end_word = min(start_word + max_words, len(words))
            content = " ".join(words[start_word:end_word])
            # approximate char positions
            start_char = sum(lens[:start_word])
            end_char = start_char + len(content)
            chunks.append(Chunk(content, idx, start_char, end_char, "words"))
            idx += 1
            if end_word >= len(words):
                break
            start_word = end_word - overlap_words if end_word - overlap_words > start_word else end_word
        return chunks

    def _jsonl_aware(self, text: str, jsonl_data: List[Dict[str, Any]]) -> List[Chunk]:
        """
        Enhanced JSONL-aware chunking that respects document structure.
        Creates chunks based on logical document boundaries and element relationships.
        """
        logger.info(f"Starting JSONL-aware chunking with {len(jsonl_data)} elements")
        
        # Parse JSONL elements into structured format
        elements = []
        for item in jsonl_data:
            element = JsonlElement(
                type=item.get('type', 'text'),
                content=item.get('text', ''),
                metadata=item.get('metadata', {}),
                page_number=item.get('metadata', {}).get('page_number'),
                element_id=item.get('element_id')
            )
            elements.append(element)
        
        chunks = []
        current_chunk_content = []
        current_chunk_metadata = []
        current_length = 0
        chunk_index = 0
        position = 0
        
        # Group elements by logical boundaries
        for i, element in enumerate(elements):
            element_text = element.content.strip()
            if not element_text:
                continue
                
            # Calculate if adding this element would exceed max length
            estimated_length = current_length + len(element_text) + 2  # +2 for spacing
            
            # Determine if we should start a new chunk
            should_chunk = False
            
            # Hard boundary: exceeds max length
            if estimated_length > self.max_len and current_chunk_content:
                should_chunk = True
            
            # Soft boundaries: logical document structure
            elif current_chunk_content and self._is_logical_boundary(element, elements, i):
                # Only chunk if we have reasonable content length
                if current_length > self.max_len * 0.5:  # At least 50% of max length
                    should_chunk = True
            
            # Create chunk if boundary detected
            if should_chunk:
                chunk_text = "\n\n".join(current_chunk_content)
                chunks.append(Chunk(
                    content=chunk_text,
                    index=chunk_index,
                    start=position,
                    end=position + len(chunk_text),
                    kind="element",
                    metadata={
                        'elements': current_chunk_metadata,
                        'page_numbers': list(set(m.get('page_number') for m in current_chunk_metadata if m.get('page_number'))),
                        'element_types': list(set(m.get('type') for m in current_chunk_metadata if m.get('type')))
                    }
                ))
                
                position += len(chunk_text)
                chunk_index += 1
                current_chunk_content = []
                current_chunk_metadata = []
                current_length = 0
            
            # Add current element to chunk
            current_chunk_content.append(element_text)
            current_chunk_metadata.append({
                'type': element.type,
                'page_number': element.page_number,
                'element_id': element.element_id,
                'metadata': element.metadata
            })
            current_length += len(element_text) + 2
        
        # Handle remaining content
        if current_chunk_content:
            chunk_text = "\n\n".join(current_chunk_content)
            chunks.append(Chunk(
                content=chunk_text,
                index=chunk_index,
                start=position,
                end=position + len(chunk_text),
                kind="element",
                metadata={
                    'elements': current_chunk_metadata,
                    'page_numbers': list(set(m.get('page_number') for m in current_chunk_metadata if m.get('page_number'))),
                    'element_types': list(set(m.get('type') for m in current_chunk_metadata if m.get('type')))
                }
            ))
        
        logger.info(f"JSONL-aware chunking created {len(chunks)} chunks")
        return self._add_jsonl_overlap(chunks)
    
    def _is_logical_boundary(self, element: JsonlElement, all_elements: List[JsonlElement], index: int) -> bool:
        """Determine if this element represents a logical chunking boundary"""
        
        # Strong boundaries - always chunk before these
        if element.type in ['title', 'header', 'heading']:
            return True
        
        # Page boundaries
        if index > 0:
            prev_page = all_elements[index - 1].page_number
            curr_page = element.page_number
            if prev_page and curr_page and prev_page != curr_page:
                return True
        
        # Section transitions (detect by content patterns)
        if element.type == 'text':
            content = element.content.strip()
            # Detect section-like patterns
            if re.match(r'^\d+\.?\s+[A-Z]', content) or re.match(r'^[A-Z][A-Z\s]+:?\s*$', content):
                return True
        
        # Table or list boundaries
        if element.type in ['table', 'list', 'figure']:
            return True
            
        return False
    
    def _add_jsonl_overlap(self, chunks: List[Chunk]) -> List[Chunk]:
        """Add intelligent overlap for JSONL chunks, preserving element boundaries"""
        if self.overlap <= 0 or len(chunks) <= 1:
            return chunks
            
        overlapped_chunks = []
        
        for i, chunk in enumerate(chunks):
            if i == 0:
                overlapped_chunks.append(chunk)
                continue
            
            # Get overlap from previous chunk
            prev_chunk = chunks[i - 1]
            prev_elements = prev_chunk.metadata.get('elements', [])
            
            # Take the last few elements from previous chunk for context
            overlap_elements = prev_elements[-2:] if len(prev_elements) > 1 else prev_elements[-1:]
            overlap_text = ""
            
            for elem_meta in overlap_elements:
                # Reconstruct text from metadata or use a portion of previous chunk
                if overlap_text:
                    overlap_text += "\n\n"
                # Use last part of previous chunk as overlap
                prev_content = prev_chunk.content
                sentences = prev_content.split('.')
                if len(sentences) > 1:
                    overlap_text = '. '.join(sentences[-2:]).strip()
                break
            
            # Combine overlap with current chunk
            if overlap_text and len(overlap_text) < self.overlap:
                enhanced_content = overlap_text + "\n\n" + chunk.content
                # Trim if too long
                if len(enhanced_content) > self.max_len + self.overlap:
                    enhanced_content = enhanced_content[:self.max_len + self.overlap]
                
                enhanced_chunk = Chunk(
                    content=enhanced_content,
                    index=chunk.index,
                    start=chunk.start,
                    end=chunk.end,
                    kind=chunk.kind,
                    metadata=chunk.metadata
                )
                overlapped_chunks.append(enhanced_chunk)
            else:
                overlapped_chunks.append(chunk)
                
        return overlapped_chunks

    def _add_overlap(self, chunks: List[Chunk]) -> List[Chunk]:
        if self.overlap <= 0 or len(chunks) <= 1:
            return chunks
        merged: List[Chunk] = []
        for i, ch in enumerate(chunks):
            if i == 0:
                merged.append(ch)
            else:
                prev_tail = merged[-1].content[-self.overlap:]
                content = (prev_tail + "\n\n" + ch.content)[: self.max_len + self.overlap]
                merged.append(Chunk(content, ch.index, ch.start, ch.end, ch.kind))
        return merged


def chunk_text(text: str, strategy: Optional[str] = None, jsonl_data: Optional[List[Dict[str, Any]]] = None) -> List[str]:
    """Helper to return plain text chunks according to strategy.
    Strategy resolved via CHUNKING_STRATEGY env or param.
    
    Args:
        text: Text to chunk
        strategy: Chunking strategy
        jsonl_data: Optional JSONL element data for structure-aware chunking
    """
    # Prefer semantic by default; support CHUNK_METHOD alias
    try:
        from app.core.config_client import cfg_get
        strat = strategy or os.getenv("CHUNK_METHOD") or cfg_get(["document_service", "chunking_strategy"], os.getenv("CHUNKING_STRATEGY", "semantic"))
        strat = str(strat).lower()
    except Exception:
        strat = (strategy or os.getenv("CHUNK_METHOD") or os.getenv("CHUNKING_STRATEGY", "semantic")).lower()
    # Map aliases: WORDS -> words, RULES -> rule_based
    alias = {
        "words": "words",
        "word": "words",
        "word_based": "words",
        "rules": "rule_based",
        "chars": "rule_based",
    }
    strat = alias.get(strat, strat)
    chunker = SemanticChunker()
    return [c.content for c in chunker.chunk(text, strat, jsonl_data)]
