"""Vision Adapter

Provides lightweight vision handling for multimodal table/diagram extraction.
This implementation enriches prompts with actual image-derived context rather
than providing a stub. It avoids provider lock-in by not directly invoking
proprietary multimodal APIs; instead it:

1. Fetches images over HTTP(S) (or skips if httpx missing).
2. Normalizes them to base64 (prefix only injected for token efficiency).
3. Optionally performs OCR (pytesseract) if available & enabled.
4. Builds a textual segment appended to the main LLM prompt consumed by
   existing process types (TABLE_EXTRACTION, DIAGRAM_UNDERSTANDING).

If dedicated model-specific vision calls are added later, this adapter can be
extended with strategy methods while preserving current interface.
"""

from __future__ import annotations

import os
import io
import base64
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("llm-service.vision-adapter")

try:  # Optional dependency for fetching images
    import httpx  # type: ignore
except Exception:  # pragma: no cover
    httpx = None  # type: ignore

try:  # Optional OCR stack
    import pytesseract  # type: ignore
    from PIL import Image  # type: ignore
except Exception:  # pragma: no cover
    pytesseract = None  # type: ignore
    Image = None  # type: ignore


class VisionAdapter:
    """Encapsulates vision enrichment features for multimodal extraction."""

    def __init__(self) -> None:
        self.enabled = str(os.getenv("VISION_MODELS_ENABLED", "true")).lower() in ("1", "true", "yes", "on")
        # OCR enablement: default auto (enabled if pytesseract present) unless explicitly disabled
        ocr_flag = os.getenv("VISION_OCR_ENABLED")
        if ocr_flag is None:
            self.ocr_enabled = pytesseract is not None
        else:
            self.ocr_enabled = str(ocr_flag).lower() in ("1", "true", "yes", "on") and pytesseract is not None

    def is_enabled(self) -> bool:
        return self.enabled

    async def prepare_images(self, image_urls: List[str]) -> List[Dict[str, Any]]:
        """Fetch & prepare images.

        Returns list of dicts:
            { 'url': str, 'b64': str, 'mime': str, 'ocr_text': str|None, 'size_bytes': int }
        Gracefully degrades if dependencies missing.
        """
        results: List[Dict[str, Any]] = []
        if not image_urls:
            return results
        if httpx is None:
            logger.warning("httpx not installed; cannot fetch image URLs for vision enrichment")
            return results

        async with httpx.AsyncClient(timeout=10.0) as client:
            for url in image_urls[:10]:  # cap to 10
                try:
                    if not (url.startswith("http://") or url.startswith("https://")):
                        logger.debug(f"Skipping non-http(s) image ref: {url}")
                        continue
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        logger.debug(f"Non-200 ({resp.status_code}) fetching {url}")
                        continue
                    content_type = resp.headers.get("content-type", "image/png").split(";")[0]
                    data = resp.content
                    b64 = base64.b64encode(data).decode("utf-8")
                    ocr_text: Optional[str] = None
                    if self.ocr_enabled and Image is not None:
                        try:
                            img = Image.open(io.BytesIO(data))
                            ocr_text = (pytesseract.image_to_string(img) or "").strip() or None
                        except Exception as oe:  # pragma: no cover
                            logger.debug(f"OCR failed for {url}: {oe}")
                    results.append({
                        "url": url,
                        "b64": b64,
                        "mime": content_type,
                        "ocr_text": ocr_text,
                        "size_bytes": len(data)
                    })
                except Exception as e:  # pragma: no cover
                    logger.debug(f"Image fetch/prepare failed for {url}: {e}")
        return results

    async def build_enhanced_prompt_segment(self, images: List[Dict[str, Any]], mode: str) -> str:
        """Build a textual segment summarizing images + OCR excerpts.

        Only prefixes of base64 strings are included to contextualize without
        blowing token budgets.
        """
        if not images:
            return ""
        lines: List[str] = []
        lines.append(f"VISION_INPUT mode={mode} image_count={len(images)}")
        for i, img in enumerate(images):
            ocr_snip = (img.get("ocr_text") or "").replace("\n", " ").strip()
            if len(ocr_snip) > 280:
                ocr_snip = ocr_snip[:277] + "..."
            lines.append(
                f"IMAGE[{i}] mime={img['mime']} bytes={img['size_bytes']} b64_prefix={img['b64'][:56]} OCR={ocr_snip!r}"
            )
        return "\n".join(lines)
