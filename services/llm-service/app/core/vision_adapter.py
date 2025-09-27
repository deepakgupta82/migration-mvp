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
import time
import logging
import threading
from typing import List, Dict, Any, Optional, Tuple, Callable

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


class _TTLCache:
    """Simple thread-safe TTL cache (key -> (expires, value))."""
    def __init__(self, max_items: int = 256, ttl_seconds: int = 600):
        self.max_items = max_items
        self.ttl = ttl_seconds
        self._data: Dict[str, Tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str):
        now = time.time()
        with self._lock:
            item = self._data.get(key)
            if not item:
                return None
            exp, val = item
            if exp < now:
                self._data.pop(key, None)
                return None
            return val

    def set(self, key: str, value: Any):
        with self._lock:
            if key not in self._data and len(self._data) >= self.max_items:
                # drop oldest
                oldest_key = min(self._data.items(), key=lambda kv: kv[1][0])[0]
                self._data.pop(oldest_key, None)
            self._data[key] = (time.time() + self.ttl, value)


class VisionAdapter:
    """Encapsulates vision enrichment features for multimodal extraction with lightweight OCR and caching.

    Responsibilities:
      - Fetch and normalize remote images
      - Accept already provided base64 image strings (data URI or raw) via helper
      - Optional OCR for text extraction
      - Summarize image metadata into low-token prompt segment
      - Cache expensive OCR work (by SHA256 hash of raw bytes) for TTL window
      - Provide minimal schema validation utilities (filled later by callers)
    """

    def __init__(self) -> None:
        # Support new flag name MULTIMODAL_ENABLED with backward compat
        multimodal_flag = os.getenv("MULTIMODAL_ENABLED") or os.getenv("VISION_MODELS_ENABLED", "true")
        self.enabled = str(multimodal_flag).lower() in ("1", "true", "yes", "on")
        # OCR flag alias
        ocr_flag = os.getenv("OCR_ENABLED") or os.getenv("VISION_OCR_ENABLED")
        if ocr_flag is None:
            self.ocr_enabled = pytesseract is not None
        else:
            self.ocr_enabled = str(ocr_flag).lower() in ("1", "true", "yes", "on") and pytesseract is not None
        # OCR (text) cache
        cache_size = int(os.getenv("VISION_CACHE_SIZE", "256"))
        ttl = int(os.getenv("VISION_CACHE_TTL", "900"))  # 15m default
        self._ocr_cache = _TTLCache(max_items=cache_size, ttl_seconds=ttl)

        # Image result cache (A7) - stores fully prepared image dicts to avoid re-fetch + re-OCR
        img_cache_size = int(os.getenv("VISION_CACHE_MAX_ENTRIES", os.getenv("VISION_IMAGE_CACHE_SIZE", "128")))
        img_ttl = int(os.getenv("VISION_IMAGE_CACHE_TTL", "1800"))  # 30m default
        self._image_cache = _TTLCache(max_items=img_cache_size, ttl_seconds=img_ttl)

        # Metrics counters
        self._metrics_lock = threading.Lock()
        self._metrics = {
            "vision_cache_hits": 0,
            "vision_cache_misses": 0,
            "vision_cache_evictions": 0,  # populated opportunistically
            "images_processed": 0,
            "ocr_invocations": 0,
        }

    # ------------------ Metrics helpers ------------------
    def _metric(self, key: str, inc: int = 1):  # small inline helper
        try:
            with self._metrics_lock:
                self._metrics[key] = self._metrics.get(key, 0) + inc
        except Exception:  # pragma: no cover
            pass

    def get_cache_metrics(self) -> Dict[str, Any]:
        """Return snapshot of adapter vision/ocr cache metrics."""
        with self._metrics_lock:
            snap = dict(self._metrics)
        # Add dynamic sizes
        snap.update({
            "ocr_cache_items": len(self._ocr_cache._data),  # type: ignore[attr-defined]
            "image_cache_items": len(self._image_cache._data),  # type: ignore[attr-defined]
        })
        return snap

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

        force_refresh = str(os.getenv("FORCE_REFRESH_VISION", "false")).lower() in ("1", "true", "yes", "on")

        async with httpx.AsyncClient(timeout=10.0) as client:
            for url in image_urls[:10]:  # cap to 10
                try:
                    if not (url.startswith("http://") or url.startswith("https://")):
                        logger.debug(f"Skipping non-http(s) image ref: {url}")
                        continue

                    # Attempt cache reuse (keyed by URL) unless forced refresh
                    cached_entry = None if force_refresh else self._image_cache.get(url)
                    if cached_entry is not None:
                        self._metric("vision_cache_hits")
                        results.append(cached_entry)
                        continue
                    self._metric("vision_cache_misses")

                    resp = await client.get(url)
                    if resp.status_code != 200:
                        logger.debug(f"Non-200 ({resp.status_code}) fetching {url}")
                        continue
                    content_type = resp.headers.get("content-type", "image/png").split(";")[0]
                    data = resp.content
                    b64 = base64.b64encode(data).decode("utf-8")
                    ocr_text: Optional[str] = None
                    if self.ocr_enabled and Image is not None:
                        import hashlib
                        digest = hashlib.sha256(data).hexdigest()
                        cached = self._ocr_cache.get(digest)
                        if cached is not None:
                            ocr_text = cached
                        else:
                            try:
                                img = Image.open(io.BytesIO(data))
                                ocr_text = (pytesseract.image_to_string(img) or "").strip() or None
                                if ocr_text:
                                    self._ocr_cache.set(digest, ocr_text)
                                self._metric("ocr_invocations")
                            except Exception as oe:  # pragma: no cover
                                logger.debug(f"OCR failed for {url}: {oe}")
                    prepared = {
                        "url": url,
                        "b64": b64,
                        "mime": content_type,
                        "ocr_text": ocr_text,
                        "size_bytes": len(data)
                    }
                    results.append(prepared)
                    # Store in image cache
                    before_sz = len(self._image_cache._data)
                    self._image_cache.set(url, prepared)
                    after_sz = len(self._image_cache._data)
                    if after_sz < before_sz:  # eviction happened (oldest removed)
                        self._metric("vision_cache_evictions")
                    self._metric("images_processed")
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

    # ------------------------------------------------------------------
    # Helper utilities for direct base64 images (e.g., upload scenarios)
    # ------------------------------------------------------------------
    def prepare_base64_image(self, b64_or_data_uri: str) -> Optional[Dict[str, Any]]:
        """Prepare a single base64 (or data URI) image dict similar to prepare_images output.

        Returns None if decoding fails.
        """
        try:
            if "," in b64_or_data_uri and b64_or_data_uri.strip().lower().startswith("data:"):
                header, b64_part = b64_or_data_uri.split(",", 1)
                mime = header.split(";")[0].replace("data:", "") or "image/png"
            else:
                b64_part = b64_or_data_uri
                mime = "image/png"
            raw = base64.b64decode(b64_part)
            ocr_text = None
            if self.ocr_enabled and Image is not None:
                import hashlib
                digest = hashlib.sha256(raw).hexdigest()
                cached = self._ocr_cache.get(digest)
                if cached is not None:
                    ocr_text = cached
                else:
                    try:
                        img = Image.open(io.BytesIO(raw))
                        ocr_text = (pytesseract.image_to_string(img) or "").strip() or None
                        if ocr_text:
                            self._ocr_cache.set(digest, ocr_text)
                    except Exception as oe:
                        logger.debug(f"OCR failed (base64): {oe}")
            return {"url": None, "b64": b64_part, "mime": mime, "ocr_text": ocr_text, "size_bytes": len(raw)}
        except Exception as e:
            logger.debug(f"prepare_base64_image failed: {e}")
            return None

    # Placeholder simple schema validators (actual strict JSON schema will be added later)
    def validate_table_result(self, data: Dict[str, Any]) -> bool:
        if not isinstance(data, dict):
            return False
        if "tables" not in data or not isinstance(data["tables"], list):
            return False
        return True

    def validate_diagram_result(self, data: Dict[str, Any]) -> bool:
        if not isinstance(data, dict):
            return False
        if "entities" not in data or "relationships" not in data:
            return False
        return True
