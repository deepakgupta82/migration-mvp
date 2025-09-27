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
import uuid
from typing import List, Dict, Any, Optional, Iterable, Tuple

logger = logging.getLogger("document-service.mineru-adapter")


class MinerUAdapter:
    def __init__(self) -> None:
        self.enabled = str(os.getenv("MINERU_ENABLED", "false")).lower() in ("1", "true", "yes", "on")
        self.fake_mode = str(os.getenv("MINERU_FAKE_MODE", "false")).lower() in ("1","true","yes","on")

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
        if mineru is None and not self.fake_mode:
            return None

        # Fake deterministic output for tests to exercise layout + hierarchy pipeline
        if self.fake_mode:
            import uuid
            logger.info("MinerU FAKE MODE active - generating synthetic layout elements (advanced mapping)")
            synthetic: List[Dict[str, Any]] = []

            # Internal helper to assign hierarchical section paths.
            section_counters: List[int] = []  # stack of counts per depth
            parent_map: Dict[str, Dict[str, Any]] = {}

            def next_section_path(depth: int) -> List[int]:
                """Increment hierarchical counters producing a stable section path.

                depth is 1-based. If we jump from depth 1 to depth 3, intermediate level is created.
                Resets counters for deeper levels when moving up.
                """
                if depth < 1:
                    depth = 1
                # Grow to required depth
                while len(section_counters) < depth:
                    section_counters.append(0)
                # Trim if we moved up
                while len(section_counters) > depth:
                    section_counters.pop()
                # Increment leaf
                section_counters[-1] += 1
                return list(section_counters)

            def mk(elem_type: str, text: str, page: int, order: int, parent: Optional[str]=None, bbox=None, header_level: Optional[int]=None, caption_for: Optional[str]=None):
                eid = str(uuid.uuid4())
                level = 1 if elem_type == "title" else (2 if elem_type == "header" else 3)
                hierarchy_level = header_level or level
                section_path: Optional[List[int]] = None
                if elem_type == "title":
                    section_path = next_section_path(1)
                elif elem_type == "header":
                    # simple heuristic: if header text contains 'Section X.Y' form, derive depth from dots
                    depth = 2
                    lowered = text.lower()
                    # Count dots in a prefix like '1.2.3' to infer depth
                    import re as _re
                    m = _re.match(r"\s*(\d+(?:\.\d+){0,5})", text.strip())
                    if m:
                        parts = m.group(1).split('.')
                        depth = min(1 + len(parts), 6)
                    section_path = next_section_path(depth)
                elif parent and parent in parent_map:
                    # Inherit parent's section path for narrative/text elements
                    psec = parent_map[parent].get("metadata", {}).get("section_path") or []
                    section_path = list(psec)
                meta = {"fake": True, "order": order, "filename": filename}
                if section_path:
                    meta["section_path"] = section_path
                if caption_for:
                    meta["caption_for"] = caption_for
                # Add table structural metadata if applicable
                if elem_type == "table":
                    # Normalize table: ensure header + at least one data row; compute columns via split respecting multiple spaces
                    lines = [ln for ln in (text or '').splitlines() if ln.strip()]
                    if lines:
                        header_line = lines[0]
                        data_lines = lines[1:]
                        header_cells = [c for c in header_line.strip().split() if c]
                        col_count = len(header_cells)
                        meta.update({
                            "table_rows": len(lines),
                            "table_cols": col_count,
                            "table_header": header_cells,
                            "table_data_row_count": len(data_lines),
                        })
                    else:
                        meta.update({"table_rows": 0, "table_cols": 0})
                obj = {
                    "element_id": eid,
                    "type": elem_type,
                    "text": text,
                    "page_number": page,
                    "coordinates": bbox or {"x1":10+order*5,"y1":50+order*10,"x2":500,"y2":100+order*10},
                    "parent_id": parent,
                    "metadata": meta,
                    "hierarchy_level": hierarchy_level,
                    "semantic_tags": [elem_type, "synthetic"],
                    "confidence_score": 0.99
                }
                parent_map[eid] = obj
                synthetic.append(obj)
                return obj

            title = mk("title", "Synthetic Document Title", 1, 0)
            header = mk("header", "1 Introduction", 1, 1, parent=title["element_id"])
            subheader = mk("header", "1.1 Background", 1, 2, parent=header["element_id"], header_level=3)
            para1 = mk("narrative_text", "This is a synthetic paragraph used for MinerU fake mode testing.", 1, 3, parent=subheader["element_id"])
            para2 = mk("narrative_text", "Another paragraph to test reading order and layout extraction.", 2, 0, parent=subheader["element_id"])
            table = mk("table", "ColA ColB\nVal1 Val2", 2, 1, parent=subheader["element_id"])
            caption = mk("caption", "Table 1: Sample values for columns A and B", 2, 2, parent=subheader["element_id"], caption_for=table["element_id"])
            return synthetic

        if mineru is None:
            return None

        try:
            raw_output = self._invoke_mineru(mineru, file_path)
            if raw_output is None:
                logger.info("MinerU returned no result; falling back to unstructured pipeline")
                return None
            blocks = self._collect_blocks(raw_output)
            if not blocks:
                logger.info("MinerU produced no content blocks; falling back to unstructured pipeline")
                return None
            canonical = self._normalize_blocks(blocks, filename)
            if not canonical:
                logger.info("MinerU normalization yielded empty output; falling back to unstructured pipeline")
                return None
            return canonical
        except Exception as e:
            logger.warning(f"MinerU parsing failed, falling back: {type(e).__name__}: {e}")
            return None

    # ------------------------------------------------------------------
    # Internal helpers for MinerU invocation and normalization
    # ------------------------------------------------------------------

    def _invoke_mineru(self, mineru_module: Any, file_path: str) -> Any:
        """Attempt to execute MinerU parsing using a variety of known API surfaces."""

        # Candidate pipeline constructors
        constructors: List[Any] = []
        for attr_path in ("Pipeline", "pipeline.Pipeline", "pipelines.Pipeline"):
            ctor = self._resolve_attr(mineru_module, attr_path)
            if callable(ctor):
                constructors.append(ctor)

        for ctor in constructors:
            try:
                pipeline_instance = ctor()
            except Exception as e:  # pragma: no cover
                logger.debug(f"MinerU pipeline init failed ({ctor}): {e}")
                continue
            for method_name in ("parse", "run", "process", "__call__"):
                method = getattr(pipeline_instance, method_name, None)
                if callable(method):
                    try:
                        result = method(file_path)
                        if result:
                            return result
                    except Exception as e:  # pragma: no cover
                        logger.debug(f"MinerU pipeline {method_name} failed: {e}")
                        continue

        # Direct module-level helpers (parse_pdf, parse, load, run)
        for fn_name in ("parse_pdf", "parse", "run", "load"):
            fn = self._resolve_attr(mineru_module, fn_name)
            if callable(fn):
                try:
                    result = fn(file_path)
                    if result:
                        return result
                except Exception as e:  # pragma: no cover
                    logger.debug(f"MinerU function {fn_name} failed: {e}")
                    continue

        return None

    def _resolve_attr(self, root: Any, dotted: str) -> Any:
        current = root
        for part in dotted.split('.'):
            current = getattr(current, part, None)
            if current is None:
                return None
        return current

    def _collect_blocks(self, raw_output: Any) -> List[Dict[str, Any]]:
        """Walk MinerU output and gather candidate block dictionaries."""

        visited: set[int] = set()
        blocks: List[Dict[str, Any]] = []

        def visit(node: Any) -> None:
            if node is None:
                return
            node_id = id(node)
            if node_id in visited:
                return
            visited.add(node_id)

            if isinstance(node, dict):
                block = self._coerce_block_dict(node)
                if self._is_content_block(block):
                    blocks.append(block)
                for val in node.values():
                    if isinstance(val, (list, tuple, set)):
                        for item in val:
                            visit(item)
                    elif isinstance(val, dict):
                        visit(val)
                return

            if isinstance(node, (list, tuple, set)):
                for item in node:
                    visit(item)
                return

            # Handle objects with useful attributes
            block = self._coerce_block_dict(node)
            if self._is_content_block(block):
                blocks.append(block)
            for attr in ("blocks", "elements", "items", "children", "pages", "content", "spans", "lines"):
                if hasattr(node, attr):
                    try:
                        attr_val = getattr(node, attr)
                    except Exception:
                        continue
                    if isinstance(attr_val, (list, tuple, set)):
                        for item in attr_val:
                            visit(item)
                    elif isinstance(attr_val, dict):
                        visit(attr_val)

        visit(raw_output)
        return blocks

    def _coerce_block_dict(self, block: Any) -> Dict[str, Any]:
        """Extract a lightweight dictionary from MinerU block/object."""
        if isinstance(block, dict):
            data = dict(block)
        else:
            data = {}
            for key in self._BLOCK_FIELDS:
                if hasattr(block, key):
                    try:
                        value = getattr(block, key)
                    except Exception:
                        continue
                    if callable(value):
                        continue
                    data[key] = value
        return data

    _BLOCK_FIELDS: Tuple[str, ...] = (
        "id", "element_id", "block_id", "uuid",
        "type", "category", "block_type", "name", "role", "label",
        "text", "content", "value", "plain_text",
        "page", "page_number", "page_index", "page_no", "page_id",
        "bbox", "bounding_box", "box", "coordinates", "rect",
        "parent", "parent_id", "parent_uuid", "parent_ref",
        "hierarchy_level", "level", "heading_level", "depth",
        "order", "index", "reading_order", "sequence",
        "confidence", "score", "probability",
        "section_path", "labels", "tags", "attributes", "metadata",
        "target_id", "caption_for", "link_target",
        "table", "table_rows", "table_cols", "table_header", "table_data"
    )

    def _is_content_block(self, block: Dict[str, Any]) -> bool:
        if not block:
            return False
        raw_type = block.get("type") or block.get("category") or block.get("block_type") or block.get("name")
        text = self._extract_text(block)
        if raw_type:
            raw_lower = raw_type.lower()
            if raw_lower in {"page", "document"} and not (text and text.strip()):
                return False
            return True
        if isinstance(text, str) and text.strip():
            return True
        return False

    def _normalize_blocks(self, blocks: List[Dict[str, Any]], filename: str) -> List[Dict[str, Any]]:
        canonical: List[Dict[str, Any]] = []
        seen_ids: set[str] = set()

        for idx, block in enumerate(blocks):
            raw_type = self._extract_raw_type(block)
            text = self._extract_text(block)
            if not raw_type and not (text and text.strip()):
                continue

            element_type = self._map_type(raw_type, block, text)
            page_number = self._extract_page_number(block)
            coordinates = self._extract_coordinates(block)
            parent_id = self._extract_parent_id(block)
            hierarchy_level = self._extract_hierarchy(block)
            semantic_tags = self._extract_semantic_tags(block, element_type)
            confidence = self._extract_confidence(block)
            metadata = self._build_metadata(block, filename, element_type, text)

            raw_element_id = self._ensure_str(
                block.get("element_id")
                or block.get("id")
                or block.get("block_id")
                or block.get("uuid")
            )
            if raw_element_id and raw_element_id in seen_ids:
                raw_element_id = None  # Avoid duplicates by regenerating
            element_id = raw_element_id or self._generate_element_id(filename, element_type, page_number, idx)
            seen_ids.add(element_id)

            canonical.append({
                "element_id": element_id,
                "type": element_type,
                "text": text or "",
                "page_number": page_number,
                "coordinates": coordinates,
                "parent_id": parent_id,
                "metadata": metadata,
                "hierarchy_level": hierarchy_level,
                "semantic_tags": semantic_tags or None,
                "confidence_score": confidence,
            })

        return canonical

    def _extract_raw_type(self, block: Dict[str, Any]) -> Optional[str]:
        for key in ("type", "category", "block_type", "name", "role", "label"):
            value = block.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def _extract_text(self, block: Dict[str, Any]) -> Optional[str]:
        for key in ("text", "content", "value", "plain_text"):
            value = block.get(key)
            if isinstance(value, str):
                return value
        return None

    def _map_type(self, raw_type: Optional[str], block: Dict[str, Any], text: Optional[str]) -> str:
        raw = (raw_type or "").strip().lower()
        if not raw and block.get("table"):
            raw = "table"
        if not raw and text:
            if text.strip().startswith("table"):
                raw = "caption"

        mapping = {
            "title": "title",
            "document_title": "title",
            "heading": "header",
            "header": "header",
            "subheading": "header",
            "subtitle": "header",
            "paragraph": "narrative_text",
            "text": "narrative_text",
            "body_text": "narrative_text",
            "list": "list_item",
            "list_item": "list_item",
            "bullet": "list_item",
            "table": "table",
            "table_cell": "table",
            "figure": "figure",
            "image": "figure",
            "picture": "figure",
            "diagram": "figure",
            "caption": "caption",
            "footnote": "footnote",
        }

        # Heuristics when raw type unknown
        if raw in mapping:
            return mapping[raw]

        if "table" in raw:
            return "table"
        if "caption" in raw:
            return "caption"
        if raw.endswith("_title"):
            return "title"
        if raw.startswith("heading"):
            return "header"
        if raw in ("line", "span") and block.get("parent_role") == "table":
            return "table"
        if raw in ("listbullet", "bullet_item"):
            return "list_item"

        return "narrative_text"

    def _extract_page_number(self, block: Dict[str, Any]) -> Optional[int]:
        for key in ("page_number", "page_no", "page", "page_id"):
            raw_value = block.get(key)
            if isinstance(raw_value, dict):
                for nested_key in ("number", "page_number", "page_no", "index", "page_index"):
                    if nested_key in raw_value:
                        nested_val = raw_value[nested_key]
                        number = self._safe_int(nested_val)
                        if number is not None:
                            if nested_key in ("index", "page_index"):
                                return number + 1
                            return number
                continue
            number = self._safe_int(raw_value)
            if number is not None:
                return number
        index = self._safe_int(block.get("page_index"))
        if index is not None:
            return index + 1
        return None

    def _extract_coordinates(self, block: Dict[str, Any]) -> Optional[Dict[str, float]]:
        bbox = block.get("bbox") or block.get("bounding_box") or block.get("box") or block.get("coordinates") or block.get("rect")
        if bbox is None:
            return None

        def _from_sequence(seq: Iterable[Any]) -> Optional[Dict[str, float]]:
            seq_list = list(seq)
            if len(seq_list) == 4 and all(self._is_number(v) for v in seq_list):
                x1, y1, x2, y2 = map(float, seq_list)
                return {"x1": x1, "y1": y1, "x2": x2, "y2": y2}
            if len(seq_list) == 2 and all(isinstance(v, (list, tuple)) and len(v) >= 2 for v in seq_list):
                x1, y1 = float(seq_list[0][0]), float(seq_list[0][1])
                x2, y2 = float(seq_list[1][0]), float(seq_list[1][1])
                return {"x1": x1, "y1": y1, "x2": x2, "y2": y2}
            return None

        if isinstance(bbox, dict):
            keys = {k.lower(): v for k, v in bbox.items() if self._is_number(v)}
            if {"x0", "y0", "x1", "y1"}.issubset(keys):
                return {"x1": float(keys["x0"]), "y1": float(keys["y0"]), "x2": float(keys["x1"]), "y2": float(keys["y1"]) }
            if {"x1", "y1", "x2", "y2"}.issubset(keys):
                return {"x1": float(keys["x1"]), "y1": float(keys["y1"]), "x2": float(keys["x2"]), "y2": float(keys["y2"]) }
            # Some APIs provide "left","top","right","bottom"
            if {"left", "top", "right", "bottom"}.issubset(keys):
                return {"x1": float(keys["left"]), "y1": float(keys["top"]), "x2": float(keys["right"]), "y2": float(keys["bottom"]) }
            # Otherwise try using numeric values directly
            numeric_values = [v for v in bbox.values() if self._is_number(v)]
            if len(numeric_values) >= 4:
                return _from_sequence(numeric_values[:4])
        elif isinstance(bbox, (list, tuple)):
            coords = _from_sequence(bbox)
            if coords:
                return coords
        return None

    def _extract_parent_id(self, block: Dict[str, Any]) -> Optional[str]:
        parent = block.get("parent_id") or block.get("parent") or block.get("parent_uuid") or block.get("parent_ref")
        if isinstance(parent, dict):
            parent = parent.get("id") or parent.get("element_id")
        if parent is None:
            return None
        return self._ensure_str(parent)

    def _extract_hierarchy(self, block: Dict[str, Any]) -> Optional[int]:
        for key in ("hierarchy_level", "level", "heading_level", "depth"):
            level = self._safe_int(block.get(key))
            if level is not None:
                return level
        return None

    def _extract_semantic_tags(self, block: Dict[str, Any], element_type: str) -> List[str]:
        tags: List[str] = []
        for key in ("labels", "tags"):
            value = block.get(key)
            if isinstance(value, (list, tuple, set)):
                tags.extend([str(v) for v in value if v is not None])
        tags = [t.lower() for t in tags]
        if element_type not in tags:
            tags.append(element_type)
        return list(dict.fromkeys(tags))  # remove duplicates preserving order

    def _extract_confidence(self, block: Dict[str, Any]) -> Optional[float]:
        for key in ("confidence", "score", "probability"):
            value = block.get(key)
            if self._is_number(value):
                try:
                    return float(value)
                except (TypeError, ValueError):
                    continue
        return None

    def _build_metadata(self, block: Dict[str, Any], filename: str, element_type: str, text: Optional[str]) -> Dict[str, Any]:
        metadata: Dict[str, Any] = {
            "source": "mineru",
            "file": filename,
        }

        raw_type_value = block.get("type")
        if isinstance(raw_type_value, str) and raw_type_value.strip():
            metadata["raw_type"] = raw_type_value.strip()

        # Section path normalization
        section_path = block.get("section_path")
        if isinstance(section_path, str):
            try:
                section_path = [int(part) for part in section_path.strip().strip('.').split('.') if part]
            except ValueError:
                section_path = [part.strip() for part in section_path.split('.') if part.strip()]
        if isinstance(section_path, (list, tuple)) and section_path:
            metadata["section_path"] = [self._safe_int(part) or str(part) for part in section_path]

        # Reading / ordering hints
        order = block.get("order") or block.get("reading_order") or block.get("index") or block.get("sequence")
        if order is not None:
            metadata["order"] = self._safe_int(order) or self._safe_float(order)

        # Caption linkage hints
        for key in ("caption_for", "target_id", "target", "link_target"):
            value = block.get(key)
            if value:
                metadata["caption_for"] = self._ensure_str(value)
                break

        # Additional descriptive fields
        for key in ("role", "category", "block_type", "name", "label"):
            value = block.get(key)
            if isinstance(value, str) and value.strip():
                metadata[f"raw_{key}"] = value.strip()

        attributes = block.get("attributes")
        if attributes:
            metadata["attributes"] = self._sanitize_metadata(attributes)

        table_info = block.get("table") or {}
        if isinstance(table_info, dict):
            metadata["table"] = self._sanitize_metadata({k: table_info.get(k) for k in ("header", "rows", "cols", "structure") if k in table_info})

        for key in ("table_rows", "table_cols", "table_header", "table_data"):
            if key in block and block[key] is not None:
                metadata[key] = self._sanitize_metadata(block[key])

        # Provide table row/col estimates when missing
        if element_type == "table":
            lines = [ln for ln in (text or "").splitlines() if ln.strip()]
            if lines:
                metadata.setdefault("table_rows", len(lines))
                metadata.setdefault("table_cols", len(lines[0].split()))

        list_level = block.get("list_level")
        if list_level is not None:
            metadata["list_level"] = self._safe_int(list_level) or list_level

        # Clean out None values and ensure JSON serializable
        cleaned: Dict[str, Any] = {}
        for key, value in metadata.items():
            if value is None:
                continue
            sanitized = self._sanitize_metadata(value)
            if sanitized is not None:
                cleaned[key] = sanitized
        metadata = cleaned
        if "caption_for" in metadata:
            metadata["caption_for"] = self._ensure_str(metadata["caption_for"])
        return metadata

    def _sanitize_metadata(self, value: Any, depth: int = 0) -> Any:
        if depth > 2:
            return None
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, (list, tuple, set)):
            return [self._sanitize_metadata(v, depth + 1) for v in list(value)[:10]]
        if isinstance(value, dict):
            sanitized: Dict[str, Any] = {}
            for i, (k, v) in enumerate(value.items()):
                if i >= 15:
                    break
                sanitized[str(k)] = self._sanitize_metadata(v, depth + 1)
            return sanitized
        if hasattr(value, "__dict__"):
            public = {k: getattr(value, k) for k in dir(value) if not k.startswith('_') and not callable(getattr(value, k))}
            return self._sanitize_metadata(public, depth + 1)
        return str(value)

    def _generate_element_id(self, filename: str, element_type: str, page_number: Optional[int], index: int) -> str:
        seed = f"mineru::{filename}::{page_number or 0}::{element_type}::{index}"
        return str(uuid.uuid5(uuid.NAMESPACE_URL, seed))

    def _safe_int(self, value: Any) -> Optional[int]:
        if isinstance(value, bool):
            return int(value)
        try:
            if isinstance(value, (int, float)):
                return int(value)
            if isinstance(value, str) and value.strip():
                return int(float(value))
        except (TypeError, ValueError):
            return None
        return None

    def _safe_float(self, value: Any) -> Optional[float]:
        try:
            if isinstance(value, (int, float)):
                return float(value)
            if isinstance(value, str) and value.strip():
                return float(value)
        except (TypeError, ValueError):
            return None
        return None

    def _is_number(self, value: Any) -> bool:
        return isinstance(value, (int, float)) or (isinstance(value, str) and value.strip().replace('.', '', 1).replace('-', '', 1).isdigit())

    def _ensure_str(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        try:
            return str(value)
        except Exception:
            return None
