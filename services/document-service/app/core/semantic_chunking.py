"""
Semantic/Paragraph Chunking Utility for Document Service
Lightweight port inspired by backend semantic chunkers.

- Supports strategies: 'semantic', 'paragraph', 'rule_based'
- Semantic uses sentence-transformers if available; otherwise falls back to paragraph-based
"""

from dataclasses import dataclass
from typing import List, Optional
import re
import logging
import os
import threading
import asyncio
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
    kind: str  # section | paragraph | sentence | full


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

    def chunk(self, text: str, strategy: str = "semantic") -> List[Chunk]:
        if not text:
            return []
        strat = (strategy or "semantic").strip().lower()
        
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


def chunk_text(text: str, strategy: Optional[str] = None) -> List[str]:
    """Helper to return plain text chunks according to strategy.
    Strategy resolved via CHUNKING_STRATEGY env or param.
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
    return [c.content for c in chunker.chunk(text, strat)]
