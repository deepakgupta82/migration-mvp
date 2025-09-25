"""
MinerU Adapter (scaffold)

Provides a safe, optional integration with MinerU for robust PDF parsing.
If MinerU isn't installed or callable in this environment, calls will
gracefully no-op and the caller should fall back to the existing pipeline.

This adapter returns elements in the platform's canonical structure (DocumentElement-like dicts),
so callers can directly construct ProcessingResult without additional mapping.
"""

from __future__ import annotations

import os
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("document-service.mineru-adapter")


class MinerUAdapter:
    def __init__(self) -> None:
        self.enabled = str(os.getenv("MINERU_ENABLED", "false")).lower() in ("1", "true", "yes", "on")

    def is_enabled(self) -> bool:
        return self.enabled

    def _try_import(self):
        try:
            # NOTE: Import is intentionally dynamic and guarded.
            # MinerU APIs can change; we only attempt import and leave actual calls
            # contained in try/except so we can safely fall back.
            import mineru  # type: ignore
            return mineru
        except Exception as e:
            logger.debug(f"MinerU not available: {type(e).__name__}: {e}")
            return None

    def process_pdf_to_elements(self, file_path: str, filename: str) -> Optional[List[Dict[str, Any]]]:
        """
        Attempt to parse a PDF using MinerU and return a list of canonical element dicts:
        {
          "element_id": str,
          "type": str,            # e.g., title, narrative_text, table, image
          "text": str,
          "page_number": int|None,
          "coordinates": dict|None,
          "parent_id": str|None,
          "metadata": dict,
          "hierarchy_level": int|None,
          "semantic_tags": list[str]|None,
          "confidence_score": float|None
        }

        Returns None if MinerU is unavailable or parsing fails.
        """
        if not self.enabled:
            return None

        mineru = self._try_import()
        if mineru is None:
            return None

        # Try a conservative attempt to call MinerU. Since the exact public API may vary,
        # we wrap the entire call in a try/except and return None on failure so callers
        # can transparently fall back to the default unstructured pipeline.
        try:
            # PSE code path. Replace with specific MinerU API usage when available in this env.
            # For example (illustrative only):
            #   from mineru import Pipeline
            #   pipe = Pipeline()
            #   doc = pipe.parse(file_path)
            #   elements = []
            #   for blk in doc.blocks:
            #       ... map blk to canonical element dict ...
            #   return elements

            logger.info("MinerU import succeeded but no stable API mapped yet; skipping to fallback")
            return None
        except Exception as e:
            logger.warning(f"MinerU parsing failed, falling back: {type(e).__name__}: {e}")
            return None
