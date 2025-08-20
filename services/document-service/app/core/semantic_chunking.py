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

logger = logging.getLogger("document-service.semantic_chunking")


@dataclass
class Chunk:
    content: str
    index: int
    start: int
    end: int
    kind: str  # section | paragraph | sentence | full


class SemanticChunker:
    def __init__(self, max_len: int = None, overlap: int = None):
        try:
            from app.core.config_client import cfg_get
            self.max_len = int(cfg_get(["document_service", "semantic_max_chunk"], os.getenv("SEMANTIC_MAX_CHUNK", str(max_len or 2000))))
            self.overlap = int(cfg_get(["document_service", "semantic_overlap"], os.getenv("SEMANTIC_OVERLAP", str(overlap or 200))))
        except Exception:
            self.max_len = int(os.getenv("SEMANTIC_MAX_CHUNK", str(max_len or 2000)))
            self.overlap = int(os.getenv("SEMANTIC_OVERLAP", str(overlap or 200)))
        self._model = None

    def _ensure_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                try:
                    from app.core.config_client import cfg_get
                    model_name = cfg_get(["document_service", "semantic_model"], os.getenv("SEMANTIC_MODEL", "all-MiniLM-L6-v2"))
                except Exception:
                    model_name = os.getenv("SEMANTIC_MODEL", "all-MiniLM-L6-v2")
                self._model = SentenceTransformer(model_name)
                logger.info("Loaded sentence-transformers model for semantic chunking")
            except Exception as e:
                logger.warning(f"Semantic model unavailable, falling back to paragraph chunking: {e}")
                self._model = False

    def chunk(self, text: str, strategy: str = "semantic") -> List[Chunk]:
        if not text:
            return []
        if strategy == "semantic":
            self._ensure_model()
            if self._model:
                return self._semantic(text)
            # fall back if no model
            return self._paragraph(text)
        if strategy == "paragraph":
            return self._paragraph(text)
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
            logger.warning(f"Semantic chunking error, falling back: {e}")
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
    # Default to paragraph to keep document-service lightweight; enable semantic via env if desired
    try:
        from app.core.config_client import cfg_get
        strat = str((strategy or cfg_get(["document_service", "chunking_strategy"], os.getenv("CHUNKING_STRATEGY", "paragraph")))).lower()
    except Exception:
        strat = (strategy or os.getenv("CHUNKING_STRATEGY", "paragraph")).lower()
    chunker = SemanticChunker()
    return [c.content for c in chunker.chunk(text, strat)]
