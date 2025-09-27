"""LayoutAwareChunker (B1 scaffolding)

Goal: Assemble chunks respecting layout structural boundaries (sections, tables, figures)
while staying within token budgets. This is a placeholder scaffold; full logic will
be implemented in subsequent B1 iterations.

Interface draft:
  chunk_sections(elements, max_tokens=2000) -> List[Dict]
    elements: iterable of layout elements each containing at least:
        {
          'id': str,
          'kind': 'paragraph'|'heading'|'table'|'figure'|'caption',
          'text': str,
          'tokens': int (optional precomputed),
          'page': int,
          'reading_order': int
        }

Environment Flag:
  LAYOUT_AWARE_ENABLED (default: true) - if disabled, upstream should fallback to legacy chunking.

Planned enhancements:
  - Table span detection (multi-page merge awareness via existing layout JSONL)
  - Figure + caption binding
  - Token estimation using model-specific tokenizer
  - Adaptive splitting of overlong paragraphs (soft wrap)
  - Emission of chunk metadata: token_count, element_ids, boundary_reasons
"""
from __future__ import annotations

import os
from typing import List, Dict, Any, Iterable, Tuple, Optional
import re
import time

LAYOUT_AWARE_ENABLED = str(os.getenv("LAYOUT_AWARE_ENABLED", "true")).lower() in ("1","true","yes","on")

class LayoutAwareChunker:
    """Production-oriented layout-aware chunker.

    Enhancements over scaffold:
      - Optional model tokenizer (tiktoken) for more accurate token estimation.
      - Table multi-part merge (consecutive table elements treated as single logical chunk).
      - Figure + caption binding.
      - Adaptive splitting for over-budget paragraphs via sentence segmentation.
      - Metrics emission (via return_metrics flag or last_metrics attribute).
    """

    def __init__(self, max_tokens: int = 2000) -> None:
        self.max_tokens = max_tokens
        self._tokenizer = None
        self._token_mode = "heuristic"
        model = os.getenv("LAYOUT_TOKEN_MODEL", "gpt-3.5-turbo")
        # Lazy import tiktoken if present
        try:
            import tiktoken  # type: ignore
            self._tokenizer = tiktoken.encoding_for_model(model)
            self._token_mode = f"tiktoken:{model}"
        except Exception:
            self._tokenizer = None
        self.last_metrics: Dict[str, Any] = {}

    # Public API
    def chunk_sections(self, elements: Iterable[Dict[str, Any]], return_metrics: bool = False) -> Any:
        elems = list(elements or [])
        if not LAYOUT_AWARE_ENABLED:
            chunks = [
                {
                    "chunk_id": f"e:{el.get('id')}",
                    "text": el.get("text") or "",
                    "element_ids": [el.get("id")],
                    "approx_tokens": self._estimate_tokens(el.get("text") or ""),
                    "boundary_reasons": ["layout_aware_disabled"],
                }
                for el in elems
                if (el.get("kind") or "").lower() in ("paragraph", "heading")
            ]
            self.last_metrics = {
                "number_of_chunks": len(chunks),
                "total_tokens": sum(c["approx_tokens"] for c in chunks),
                "avg_chunk_tokens": (sum(c["approx_tokens"] for c in chunks) / len(chunks)) if chunks else 0,
                "max_chunk_tokens": max((c["approx_tokens"] for c in chunks), default=0),
                "tables_merged": 0,
                "figures_bound": 0,
                "paragraphs_split": 0,
                "over_budget_elements": 0,
                "token_estimation_mode": self._token_mode,
                "total_elements": len(elems),
            }
            return (chunks, self.last_metrics) if return_metrics else chunks

        start_time = time.perf_counter()
        chunks: List[Dict[str, Any]] = []
        cur_text: List[str] = []
        cur_ids: List[str] = []
        cur_tokens = 0

        tables_merged = 0
        figures_bound = 0
        paragraphs_split = 0
        over_budget_elements = 0

        i = 0
        n = len(elems)
        while i < n:
            el = elems[i]
            kind = (el.get("kind") or "").lower()

            # Handle structural: table grouping
            if kind == "table":
                if cur_ids:
                    chunks.append(self._emit_chunk(cur_ids, cur_text, cur_tokens, ["token_budget"]))
                    cur_text, cur_ids, cur_tokens = [], [], 0
                table_ids = [el.get("id")]
                table_texts = [el.get("text") or ""]
                # Merge consecutive table elements (multi-page slices)
                j = i + 1
                while j < n and (elems[j].get("kind") or "").lower() == "table":
                    tables_merged += 1
                    table_ids.append(elems[j].get("id"))
                    table_texts.append(elems[j].get("text") or "")
                    j += 1
                merged_text = "\n".join(table_texts)
                tk = self._estimate_tokens(merged_text)
                if tk > self.max_tokens:
                    over_budget_elements += 1
                chunks.append({
                    "chunk_id": f"t:{table_ids[0]}:{table_ids[-1]}",
                    "text": merged_text,
                    "element_ids": table_ids,
                    "approx_tokens": tk,
                    "boundary_reasons": ["structural:table_group"],
                })
                i = j
                continue

            # Handle figure + caption binding
            if kind == "figure":
                if cur_ids:
                    chunks.append(self._emit_chunk(cur_ids, cur_text, cur_tokens, ["token_budget"]))
                    cur_text, cur_ids, cur_tokens = [], [], 0
                fig_ids = [el.get("id")]
                fig_texts = [el.get("text") or ""]
                # Bind following caption if immediate
                if i + 1 < n and (elems[i + 1].get("kind") or "").lower() == "caption":
                    figures_bound += 1
                    cap = elems[i + 1]
                    fig_ids.append(cap.get("id"))
                    fig_texts.append(cap.get("text") or "")
                    i += 1  # Skip caption
                fig_text = "\n".join(fig_texts)
                tk = self._estimate_tokens(fig_text)
                if tk > self.max_tokens:
                    over_budget_elements += 1
                chunks.append({
                    "chunk_id": f"f:{fig_ids[0]}:{fig_ids[-1]}",
                    "text": fig_text,
                    "element_ids": fig_ids,
                    "approx_tokens": tk,
                    "boundary_reasons": ["structural:figure"],
                })
                i += 1
                continue

            # Paragraph-like (heading, paragraph, caption not bound)
            if kind in ("paragraph", "heading", "caption"):
                text = el.get("text") or ""
                tks = self._estimate_tokens(text)
                # Overlong element splitting
                if tks > self.max_tokens:
                    # Flush pending group first
                    if cur_ids:
                        chunks.append(self._emit_chunk(cur_ids, cur_text, cur_tokens, ["token_budget"]))
                        cur_text, cur_ids, cur_tokens = [], [], 0
                    fragments = self._split_overlong(text)
                    paragraphs_split += 1
                    for frag in fragments:
                        fk = self._estimate_tokens(frag)
                        reason = ["split_paragraph"]
                        if fk > self.max_tokens:
                            over_budget_elements += 1
                            reason.append("still_over_budget")
                        chunks.append({
                            "chunk_id": f"p:{el.get('id')}:{len(chunks)}",
                            "text": frag,
                            "element_ids": [el.get("id")],
                            "approx_tokens": fk,
                            "boundary_reasons": reason,
                        })
                    i += 1
                    continue
                # Normal accumulation
                if cur_tokens + tks > self.max_tokens and cur_ids:
                    chunks.append(self._emit_chunk(cur_ids, cur_text, cur_tokens, ["token_budget"]))
                    cur_text, cur_ids, cur_tokens = [], [], 0
                cur_text.append(text)
                cur_ids.append(el.get("id"))
                cur_tokens += tks
                i += 1
                continue

            # Any other structural element -> standalone chunk
            if cur_ids:
                chunks.append(self._emit_chunk(cur_ids, cur_text, cur_tokens, ["token_budget"]))
                cur_text, cur_ids, cur_tokens = [], [], 0
            s_text = el.get("text") or ""
            tk = self._estimate_tokens(s_text)
            if tk > self.max_tokens:
                over_budget_elements += 1
            chunks.append({
                "chunk_id": f"e:{el.get('id')}",
                "text": s_text,
                "element_ids": [el.get("id")],
                "approx_tokens": tk,
                "boundary_reasons": [f"structural:{kind or 'unknown'}"],
            })
            i += 1

        if cur_ids:
            chunks.append(self._emit_chunk(cur_ids, cur_text, cur_tokens, ["end_of_sequence"]))

        total_tokens = sum(c["approx_tokens"] for c in chunks)
        max_chunk_tokens = max((c["approx_tokens"] for c in chunks), default=0)
        avg_chunk_tokens = total_tokens / len(chunks) if chunks else 0
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        self.last_metrics = {
            "number_of_chunks": len(chunks),
            "total_tokens": total_tokens,
            "avg_chunk_tokens": avg_chunk_tokens,
            "max_chunk_tokens": max_chunk_tokens,
            "tables_merged": tables_merged,
            "figures_bound": figures_bound,
            "paragraphs_split": paragraphs_split,
            "over_budget_elements": over_budget_elements,
            "token_estimation_mode": self._token_mode,
            "total_elements": n,
            "elapsed_ms": round(elapsed_ms, 2),
        }
        return (chunks, self.last_metrics) if return_metrics else chunks

    # --- Internal helpers ---
    def _estimate_tokens(self, text: str) -> int:
        if not text:
            return 0
        if self._tokenizer:
            try:
                return len(self._tokenizer.encode(text))
            except Exception:
                pass
        # Fallback heuristic (~4 chars per token)
        return max(1, len(text) // 4)

    def _emit_chunk(self, ids: List[str], texts: List[str], tcount: int, reasons: List[str]):
        return {
            "chunk_id": f"g:{ids[0]}:{ids[-1]}",
            "text": "\n".join(texts),
            "element_ids": list(ids),
            "approx_tokens": tcount,
            "boundary_reasons": reasons,
        }

    _SPLIT_SENT_RE = re.compile(r"(?<=[.!?])\s+")

    def _split_overlong(self, text: str) -> List[str]:
        """Split an over-budget paragraph into sub-fragments within token budget.
        Strategy: sentence segmentation then greedy grouping under max_tokens.
        """
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        frags: List[str] = []
        cur: List[str] = []
        cur_tokens = 0
        for s in sentences:
            tk = self._estimate_tokens(s)
            # If single sentence itself exceeds budget, hard-split by length chunking
            if tk > self.max_tokens:
                # naive char slicing respecting budget
                hard = self._hard_slice(s)
                frags.extend(hard)
                continue
            if cur_tokens + tk > self.max_tokens and cur:
                frags.append(" ".join(cur))
                cur, cur_tokens = [], 0
            cur.append(s)
            cur_tokens += tk
        if cur:
            frags.append(" ".join(cur))
        return frags or [text]

    def _hard_slice(self, text: str) -> List[str]:
        """Fallback slicing for a single sentence that still exceeds the token budget."""
        approx_tok = self._estimate_tokens(text)
        if approx_tok <= self.max_tokens:
            return [text]
        # Determine char window based on heuristic ratio
        chars_per_token = max(1, len(text) // max(1, approx_tok))
        window = self.max_tokens * chars_per_token
        segments: List[str] = []
        start = 0
        while start < len(text):
            end = min(len(text), start + window)
            segments.append(text[start:end])
            start = end
        return segments

__all__ = ["LayoutAwareChunker", "LAYOUT_AWARE_ENABLED"]
