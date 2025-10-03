"""
Enhanced Document Processor with Structured JSONL Output
Implements the superior structured approach using unstructured.io with detailed metadata
"""

import os
import logging
import json
import asyncio
import tempfile
import subprocess
import warnings
from datetime import datetime
from typing import Optional, Dict, Any, List, Union
from dataclasses import dataclass, asdict
from pathlib import Path
import uuid
import csv
from hashlib import sha1
from .mineru_adapter import MinerUAdapter

# Import metadata validation schemas
from app.schemas.metadata_schemas import validate_metadata, safe_get_metadata_field

# Suppress pdfminer warnings about invalid float values in PDF color specifications
# These are common in malformed PDFs and don't affect extraction quality
warnings.filterwarnings('ignore', message='.*invalid float value.*')

# Service client for cross-service calls (analytics ingest)
import sys as _sys
_sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
try:
    from services.shared.service_client import get_service_client  # type: ignore
except Exception:  # pragma: no cover - fallback when path issues occur in isolated tests
    get_service_client = None  # type: ignore

try:
    from unstructured.partition.auto import partition
    from unstructured.staging.base import dict_to_elements, elements_to_json
    from unstructured.cleaners.core import clean_extra_whitespace, clean_dashes, clean_bullets
    from unstructured.documents.elements import Element, Text, Table, Image, Title
    UNSTRUCTURED_AVAILABLE = True
except ImportError:
    UNSTRUCTURED_AVAILABLE = False
    # Provide lightweight typing fallbacks so annotations referencing Element/Text/Table do not raise NameError
    class Element:  # type: ignore
        def __init__(self, text: str = "", category: str = "Text", metadata: dict | None = None):
            self._text = text
            self.category = category
            self.metadata = metadata or {}
        def __str__(self):
            return self._text

    class Text(Element):
        pass

    class Table(Element):
        pass

    class Image(Element):
        pass

    class Title(Element):
        pass

logger = logging.getLogger("document-service.structured-processor")

@dataclass
class DocumentMetadata:
    """Enhanced document metadata structure"""
    filename: str
    file_path: str
    file_size: int
    file_type: str
    mime_type: Optional[str]
    processing_timestamp: datetime
    project_id: str
    correlation_id: Optional[str]
    page_count: Optional[int] = None
    language: Optional[str] = None
    author: Optional[str] = None
    creation_date: Optional[datetime] = None
    modification_date: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        # Convert datetime objects to ISO strings
        data['processing_timestamp'] = self.processing_timestamp.isoformat()
        if self.creation_date:
            data['creation_date'] = self.creation_date.isoformat()
        if self.modification_date:
            data['modification_date'] = self.modification_date.isoformat()
        return data

@dataclass
class DocumentElement:
    """Structured document element with rich metadata"""
    element_id: str
    type: str  # title, narrative_text, list_item, table, image, etc.
    text: str
    page_number: Optional[int]
    coordinates: Optional[Dict[str, float]]  # x1, y1, x2, y2
    parent_id: Optional[str]
    metadata: Dict[str, Any]
    hierarchy_level: Optional[int] = None
    semantic_tags: Optional[List[str]] = None
    confidence_score: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class ProcessingResult:
    """Complete processing result with structured data"""
    document_metadata: DocumentMetadata
    elements: List[DocumentElement]
    processing_stats: Dict[str, Any]
    status: str
    errors: List[str]
    warnings: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'document_metadata': self.document_metadata.to_dict(),
            'elements': [elem.to_dict() for elem in self.elements],
            'processing_stats': self.processing_stats,
            'status': self.status,
            'errors': self.errors,
            'warnings': self.warnings
        }
    
    def to_jsonl(self, llm_analysis_result: Optional[Dict[str, Any]] = None) -> str:
        """Convert to JSONL format with one element per line"""
        lines = []

        try:
            # First line: document metadata
            doc_metadata = self.document_metadata.to_dict()
            if llm_analysis_result and llm_analysis_result.get("status") == "success":
                # Enhance document metadata with LLM analysis
                llm_metadata = llm_analysis_result.get("metadata", {})
                doc_metadata.update({
                    "llm_summary": llm_metadata.get("llm_summary", ""),
                    "llm_categories": llm_metadata.get("llm_categories", []),
                    "quality_score": llm_metadata.get("quality_score", 0.0),
                    "confidence_score": llm_metadata.get("confidence_score", 0.0),
                    "llm_processing_time": llm_metadata.get("processing_time", 0.0),
                    "llm_cached": llm_metadata.get("llm_cached", False)
                })

            lines.append(json.dumps({
                'type': 'document_metadata',
                'data': doc_metadata
            }, ensure_ascii=False))

            # Elements as individual lines
            for element in self.elements:
                try:
                    element_data = element.to_dict()
                    
                    # Ensure metadata is JSON serializable
                    if 'metadata' in element_data and element_data['metadata']:
                        element_data['metadata'] = self._make_json_serializable(element_data['metadata'])
                    
                    # Ensure coordinates are JSON serializable
                    if 'coordinates' in element_data and element_data['coordinates']:
                        element_data['coordinates'] = self._make_json_serializable(element_data['coordinates'])
                    
                    # Add LLM confidence score to elements if available
                    if llm_analysis_result and llm_analysis_result.get("status") == "success":
                        element_data["llm_confidence"] = llm_analysis_result.get("metadata", {}).get("confidence_score", 0.8)
                    
                    lines.append(json.dumps({
                        'type': 'element',
                        'data': element_data
                    }, ensure_ascii=False))
                    
                except Exception as e:
                    logger.warning(f"Error serializing element {element.element_id}: {e}")
                    # Skip problematic elements rather than failing entirely
                    continue

            # Processing summary with LLM analysis
            processing_summary = {
                'processing_stats': self.processing_stats,
                'status': self.status,
                'errors': self.errors,
                'warnings': self.warnings
            }

            # Ensure processing_stats is JSON serializable
            processing_summary['processing_stats'] = self._make_json_serializable(processing_summary['processing_stats'])

            # Add LLM analysis summary if available
            if llm_analysis_result:
                processing_summary['llm_analysis'] = {
                    'status': llm_analysis_result.get('status'),
                    'quality_score': llm_analysis_result.get('metadata', {}).get('quality_score', 0.0),
                    'processing_methods': llm_analysis_result.get('metadata', {}).get('processing_methods', []),
                    'token_usage': llm_analysis_result.get('metadata', {}).get('token_usage', {}),
                    'cached': llm_analysis_result.get('metadata', {}).get('llm_cached', False)
                }

            lines.append(json.dumps({
                'type': 'processing_summary',
                'data': processing_summary
            }, ensure_ascii=False))

            return '\n'.join(lines)
            
        except Exception as e:
            logger.error(f"Error generating JSONL: {e}")
            # Return minimal valid JSONL on error
            error_metadata = {
                'filename': self.document_metadata.filename,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
            return json.dumps({
                'type': 'error',
                'data': error_metadata
            }, ensure_ascii=False)

    def _make_json_serializable(self, obj: Any) -> Any:
        """Convert object to JSON-serializable format"""
        try:
            if obj is None:
                return None
            elif isinstance(obj, (str, int, float, bool)):
                return obj
            elif isinstance(obj, (list, tuple)):
                return [self._make_json_serializable(item) for item in obj]
            elif isinstance(obj, dict):
                return {str(k): self._make_json_serializable(v) for k, v in obj.items()}
            elif isinstance(obj, datetime):
                return obj.isoformat()
            elif hasattr(obj, 'to_dict'):
                return self._make_json_serializable(obj.to_dict())
            elif hasattr(obj, '__dict__'):
                return self._make_json_serializable(obj.__dict__)
            else:
                # Convert to string as fallback
                return str(obj)
        except Exception:
            return str(obj)

class StructuredDocumentProcessor:
    """Enhanced document processor with structured JSONL output"""
    
    def __init__(self):
        self.debug_dir = os.path.join(os.getcwd(), "structured_processing_debug")
        os.makedirs(self.debug_dir, exist_ok=True)
        
        # Configure Tesseract OCR path explicitly
        self._configure_tesseract_path()
        
        # Configuration
        self.max_file_size = 100 * 1024 * 1024  # 100MB
        self.supported_formats = {
            '.pdf', '.docx', '.doc', '.pptx', '.ppt', '.xlsx', '.xls',
            '.txt', '.md', '.html', '.htm', '.xml', '.json', '.csv',
            '.rtf', '.odt', '.ods', '.odp'
        }
        
        if not UNSTRUCTURED_AVAILABLE:
            logger.warning("unstructured library not available - structured processing will be limited")
        
        # Optional MinerU integration (gated by MINERU_ENABLED)
        self._mineru = MinerUAdapter()
    
    def _configure_tesseract_path(self):
        """Configure Tesseract OCR path for the processor"""
        tesseract_path = r"C:\Users\deepakgupta13\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"
        tesseract_dir = r"C:\Users\deepakgupta13\AppData\Local\Programs\Tesseract-OCR"
        
        if os.path.exists(tesseract_path):
            # Set environment variable for unstructured and other libraries
            os.environ['TESSERACT_CMD'] = tesseract_path
            
            # CRITICAL: Add Tesseract directory to PATH for subprocess calls
            current_path = os.environ.get('PATH', '')
            if tesseract_dir not in current_path:
                os.environ['PATH'] = f"{tesseract_dir};{current_path}"
                logger.info(f"Tesseract directory added to PATH: {tesseract_dir}")
            
            logger.info(f"Tesseract path configured for structured processor: {tesseract_path}")
            
            # Configure pytesseract if available
            try:
                import pytesseract
                pytesseract.pytesseract.tesseract_cmd = tesseract_path
                logger.info("pytesseract configured for structured processor")
            except ImportError:
                pass  # pytesseract is optional
                
            # Validate Tesseract is accessible via subprocess
            self._validate_tesseract_subprocess()
        else:
            logger.warning(f"Tesseract not found at expected path: {tesseract_path}")
    
    def _validate_tesseract_subprocess(self):
        """Validate that Tesseract is accessible via subprocess calls"""
        try:
            import subprocess
            result = subprocess.run(['tesseract', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                version_info = result.stdout.split('\n')[0] if result.stdout else "unknown version"
                logger.info(f"✓ Tesseract OCR subprocess validation successful: {version_info}")
            else:
                logger.error(f"✗ Tesseract subprocess failed: {result.stderr}")
        except subprocess.TimeoutExpired:
            logger.error("✗ Tesseract subprocess validation timed out")
        except FileNotFoundError:
            logger.error("✗ Tesseract not found in PATH for subprocess calls")
            logger.error("  This will cause unstructured.io processing to fail")
        except Exception as e:
            logger.error(f"✗ Tesseract subprocess validation failed: {e}")

    def _apply_mineru_advanced_heuristics(self, elements: List[DocumentElement]) -> tuple[List[DocumentElement], Dict[str, Any]]:
        """Apply advanced MinerU-like heuristics:
        - Multi-page table merge: consecutive table elements with same 'section_path' and within page gap 1 are merged.
        - Caption linkage already encoded via metadata.caption_for; we ensure referenced table gets 'has_caption'.
        Returns updated elements list and merge stats.
        NOTE: This is a heuristic placeholder until real MinerU structured spans are available.
        """
        if not elements:
            return elements, {}
        by_id = {e.element_id: e for e in elements}
        merged: List[DocumentElement] = []
        multi_page_merge_count = 0
        skip_ids = set()
        last_table_by_section: Dict[str, DocumentElement] = {}
        for e in elements:
            if e.element_id in skip_ids:
                continue
            if e.type == 'table':
                section_path = (e.metadata or {}).get('section_path')
                key = tuple(section_path) if isinstance(section_path, list) else None
                if key and key in last_table_by_section:
                    prev = last_table_by_section[key]
                    prev_page = prev.page_number or 0
                    cur_page = e.page_number or 0
                    # Merge if pages are increasing by <=1 and textual structure compatible (rough heuristic)
                    if 0 <= cur_page - prev_page <= 1:
                        # Combine text lines; avoid duplicates
                        prev_lines = [ln for ln in (prev.text or '').splitlines()]
                        new_lines = [ln for ln in (e.text or '').splitlines()]
                        combined = prev_lines
                        # Append new lines if not already present at end (simple heuristic)
                        if new_lines:
                            if prev_lines and new_lines[0] == prev_lines[-1]:
                                combined.extend(new_lines[1:])
                            else:
                                combined.extend(new_lines)
                        prev.text = '\n'.join([ln for ln in combined if ln.strip()])
                        # Update bounding box (coordinates) y2 to encompass new page element if coordinates numeric
                        try:
                            if prev.coordinates and e.coordinates:
                                prev.coordinates['y2'] = max(prev.coordinates.get('y2', 0), e.coordinates.get('y2', 0))
                                prev.coordinates['x2'] = max(prev.coordinates.get('x2', 0), e.coordinates.get('x2', 0))
                        except Exception:
                            pass
                        multi_page_merge_count += 1
                        skip_ids.add(e.element_id)
                        continue
                # Record this table as last seen for its section
                if key:
                    last_table_by_section[key] = e
                merged.append(e)
            else:
                merged.append(e)
        # Caption linkage augmentation
        for e in merged:
            if e.type == 'caption':
                target_id = (e.metadata or {}).get('caption_for')
                if target_id and target_id in by_id:
                    tgt = by_id[target_id]
                    md = tgt.metadata or {}
                    if not md.get('has_caption'):
                        md['has_caption'] = True
                        tgt.metadata = md
        stats = {
            'multi_page_tables_merged': multi_page_merge_count,
            'tables_after_merge': sum(1 for e in merged if e.type == 'table')
        }
        return merged, stats
    
    async def process_document(
        self,
        file_path: str,
        filename: str,
        project_id: str,
        correlation_id: Optional[str] = None,
        extract_images: bool = True,
        extract_tables: bool = True,
        include_coordinates: bool = True
    ) -> ProcessingResult:
        """
        Process document with structured JSONL output
        
        Args:
            file_path: Path to the document file
            filename: Original filename
            project_id: Project identifier
            correlation_id: Request correlation ID
            extract_images: Whether to extract image metadata
            extract_tables: Whether to extract table structure
            include_coordinates: Whether to include element coordinates
            
        Returns:
            ProcessingResult with structured elements
        """
        start_time = datetime.now()
        errors = []
        warnings = []
        
        try:
            # Validate file
            if not os.path.exists(file_path):
                raise ValueError(f"File not found: {file_path}")
            
            file_size = os.path.getsize(file_path)
            if file_size > self.max_file_size:
                raise ValueError(f"File too large: {file_size} bytes (max: {self.max_file_size})")
            
            file_ext = Path(filename).suffix.lower()
            if file_ext not in self.supported_formats:
                warnings.append(f"File format {file_ext} may not be fully supported")
            
            # Create document metadata
            doc_metadata = DocumentMetadata(
                filename=filename,
                file_path=file_path,
                file_size=file_size,
                file_type=file_ext,
                mime_type=self._get_mime_type(file_ext),
                processing_timestamp=start_time,
                project_id=project_id,
                correlation_id=correlation_id
            )
            # If spreadsheet, prefer dedicated row-wise parser to avoid flaky OCR/markdown
            processed_elements: List[DocumentElement] = []
            spreadsheet_stats: Dict[str, Any] = {}
            if file_ext in {'.xlsx', '.xls', '.csv'}:
                try:
                    processed_elements, spreadsheet_stats = await asyncio.to_thread(
                        self._process_spreadsheet_rows, file_path, filename
                    )
                except Exception as _xl_err:
                    logger.warning(f"Spreadsheet row parser failed, will fallback: {type(_xl_err).__name__}: {_xl_err}")
                    processed_elements = []

            # Try MinerU first for PDFs when enabled; otherwise fall back to unstructured
            mineru_used = False
            mineru_elements = await self._process_with_mineru_if_enabled(file_path, filename)
            if mineru_elements is not None and isinstance(mineru_elements, list) and len(mineru_elements) > 0:
                processed_elements = mineru_elements  # already in DocumentElement shape
                mineru_used = True
            else:
                if not processed_elements:
                    # Not a spreadsheet or spreadsheet parsing failed; process with unstructured
                    elements = await self._process_with_unstructured(
                        file_path, extract_images, extract_tables, include_coordinates
                    )
                    # Post-process elements
                    processed_elements = self._post_process_elements(elements)

            # If MinerU (or fake mode) provided elements, attempt advanced heuristic enhancements
            if mineru_used:
                try:
                    processed_elements, merge_stats = self._apply_mineru_advanced_heuristics(processed_elements)
                except Exception as e:
                    logger.warning(f"MinerU advanced heuristic enhancement failed: {type(e).__name__}: {e}")
                    merge_stats = {}
            
            # Calculate processing stats
            end_time = datetime.now()
            processing_stats = {
                'processing_time_seconds': (end_time - start_time).total_seconds(),
                'total_elements': len(processed_elements),
                'element_types': self._get_element_type_counts(processed_elements),
                'total_text_length': sum(len(elem.text) for elem in processed_elements),
                'pages_processed': max((elem.page_number or 0 for elem in processed_elements), default=0),
                'mineru_used': mineru_used,
            }
            # Augment stats for spreadsheet path
            if spreadsheet_stats:
                processing_stats.update(spreadsheet_stats)

            # MinerU-derived structural metrics (only meaningful if mineru_used True)
            if mineru_used:
                section_depths = [e.hierarchy_level for e in processed_elements if e.hierarchy_level is not None]
                if section_depths:
                    avg_section_depth = sum(section_depths) / len(section_depths)
                    max_section_depth = max(section_depths)
                else:
                    avg_section_depth = 0.0
                    max_section_depth = 0
                header_count = sum(1 for e in processed_elements if e.type in ('title', 'header'))
                tables = [e for e in processed_elements if e.type == 'table']
                table_rows_counts: list[int] = []
                table_cols_counts: list[int] = []
                for t_elem in tables:
                    if t_elem.text:
                        lines = [ln for ln in t_elem.text.splitlines() if ln.strip()]
                        if lines:
                            table_rows_counts.append(len(lines))
                            # naive column estimation: whitespace split on first non-empty line
                            first_line_cols = len(lines[0].strip().split())
                            table_cols_counts.append(first_line_cols)

                # Advanced heuristic metrics
                depth_histogram: Dict[int, int] = {}
                for d in section_depths:
                    depth_histogram[int(d)] = depth_histogram.get(int(d), 0) + 1

                # Caption linkage stats (caption elements with metadata.caption_for referencing a table element)
                tables_by_id = {t.element_id: t for t in tables}
                captions = [e for e in processed_elements if e.type == 'caption']
                linked_captions = [c for c in captions if (c.metadata or {}).get('caption_for') in tables_by_id]
                caption_coverage_ratio = (len(linked_captions) / len(tables)) if tables else 0.0

                # Merge stats from advanced heuristics if present
                if mineru_used and 'multi_page_tables_merged' in (merge_stats or {}):
                    processing_stats.update(merge_stats)

                processing_stats.update({
                    'avg_section_depth': round(avg_section_depth, 3),
                    'max_section_depth': max_section_depth,
                    'mineru_header_count': header_count,
                    'mineru_table_count': len(tables),
                    'mineru_avg_table_rows': (sum(table_rows_counts) / len(table_rows_counts)) if table_rows_counts else 0.0,
                    'mineru_avg_table_cols': (sum(table_cols_counts) / len(table_cols_counts)) if table_cols_counts else 0.0,
                    'section_depth_histogram': depth_histogram,
                    'captions_total': len(captions),
                    'captions_linked': len(linked_captions),
                    'caption_coverage_ratio': round(caption_coverage_ratio, 4),
                })
                def _avg(lst: list[int]) -> float:
                    return float(sum(lst)/len(lst)) if lst else 0.0
                processing_stats.update({
                    'avg_section_depth': round(avg_section_depth, 3),
                    'max_section_depth': max_section_depth,
                    'mineru_header_count': header_count,
                    'mineru_table_count': len(tables),
                    'mineru_avg_table_rows': round(_avg(table_rows_counts), 2),
                    'mineru_avg_table_cols': round(_avg(table_cols_counts), 2),
                })
            else:
                # Provide explicit zeroed keys for downstream analytics expecting them
                processing_stats.update({
                    'avg_section_depth': 0.0,
                    'max_section_depth': 0,
                })
            
            logger.info(f"Successfully processed {filename}: {len(processed_elements)} elements in {processing_stats['processing_time_seconds']:.2f}s")

            # Best-effort: emit MinerU/structured layout metrics to analytics ingest
            try:
                if get_service_client is not None:
                    client = await get_service_client()
                    # Prepare layout metrics payload (subset relevant for analytics aggregation)
                    layout_metrics: Dict[str, Any] = {
                        'mineru_used': bool(processing_stats.get('mineru_used', False)),
                        'avg_section_depth': float(processing_stats.get('avg_section_depth', 0.0)),
                        'max_section_depth': int(processing_stats.get('max_section_depth', 0)),
                        'mineru_header_count': int(processing_stats.get('mineru_header_count', 0)),
                        'mineru_table_count': int(processing_stats.get('mineru_table_count', 0)),
                        'mineru_avg_table_rows': float(processing_stats.get('mineru_avg_table_rows', 0.0)),
                        'mineru_avg_table_cols': float(processing_stats.get('mineru_avg_table_cols', 0.0)),
                        'section_depth_histogram': processing_stats.get('section_depth_histogram', {}),
                        'captions_total': int(processing_stats.get('captions_total', 0)),
                        'captions_linked': int(processing_stats.get('captions_linked', 0)),
                        'caption_coverage_ratio': float(processing_stats.get('caption_coverage_ratio', 0.0)),
                        'multi_page_tables_merged': int(processing_stats.get('multi_page_tables_merged', 0)),
                    }
                    payload = {
                        'source': 'document-service',
                        'project_id': project_id,
                        'filename': filename,
                        'metrics': {'layout': layout_metrics},
                    }
                    # Fire-and-forget semantics are fine; awaiting ensures ordering for tests
                    await client.post('analytics', '/ingest', json=payload)
            except Exception as _emit_err:  # pragma: no cover - telemetry best-effort
                logger.debug(f"Analytics ingest emit failed (non-fatal): {type(_emit_err).__name__}: {_emit_err}")
            
            return ProcessingResult(
                document_metadata=doc_metadata,
                elements=processed_elements,
                processing_stats=processing_stats,
                status='success',
                errors=errors,
                warnings=warnings
            )
            
        except Exception as e:
            logger.error(f"Error processing document {filename}: {e}")
            errors.append(str(e))
            
            # Return minimal result on error
            doc_metadata = DocumentMetadata(
                filename=filename,
                file_path=file_path,
                file_size=os.path.getsize(file_path) if os.path.exists(file_path) else 0,
                file_type=Path(filename).suffix.lower(),
                mime_type=None,
                processing_timestamp=start_time,
                project_id=project_id,
                correlation_id=correlation_id
            )

    # -------------------- Spreadsheet Row-wise Parsing --------------------
    def _process_spreadsheet_rows(self, file_path: str, filename: str) -> tuple[List[DocumentElement], Dict[str, Any]]:
        """Parse spreadsheets (.xlsx/.xls/.csv) into one DocumentElement per row with rich metadata.

        Returns a tuple of (elements, stats). Does not raise on common parse errors; returns ([], {}).
        """
        try:
            ext = Path(filename).suffix.lower()
            if ext == '.csv':
                return self._parse_csv_rows(file_path, filename)
            elif ext == '.xlsx':
                return self._parse_xlsx_rows_openpyxl(file_path, filename)
            elif ext == '.xls':
                return self._parse_xls_rows_xlrd(file_path, filename)
            else:
                return [], {}
        except Exception as e:
            logger.warning(f"Spreadsheet parsing error for {filename}: {e}")
            return [], {}

    def _stable_row_element_id(self, filename: str, sheet: str, row_idx: int, row_sig: str) -> str:
        base = f"{filename}|{sheet}|{row_idx}|{row_sig}".encode('utf-8', 'ignore')
        return sha1(base).hexdigest()

    def _make_row_element(
        self,
        filename: str,
        sheet: str,
        row_idx: int,
        headers: List[str],
        values: List[Any],
        column_types: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> DocumentElement:
        # Normalize headers and values to strings
        cols = [str(h).strip() if h is not None else f"col_{i+1}" for i, h in enumerate(headers)]
        vals = ["" if v is None else (str(v).strip() if not isinstance(v, (float, int)) else str(v)) for v in values]
        row_map = {cols[i]: (vals[i] if i < len(vals) else "") for i in range(len(cols))}
        # Build content string in a deterministic order
        content_parts = [f"{c}: {row_map.get(c, '')}" for c in cols]
        content = " | ".join(content_parts)
        # Compute a simple signature using first few characters
        sig = "\u241f".join([row_map.get(c, '')[:24] for c in cols[:6]])  # Record Separator char as delimiter
        element_id = self._stable_row_element_id(filename, sheet, row_idx, sig)
        
        # Create and validate metadata (Issue #1: Metadata validation)
        metadata = {
            'sheet_name': sheet,
            'row_index': row_idx,
            'columns': cols,
            'row_data': row_map,
            'source': 'row_wise_spreadsheet',
        }
        
        # Add column type information (Issue #7)
        if column_types:
            metadata['column_types'] = column_types
            # Add semantic tags based on detected types
            semantic_tags_from_types = []
            for col_name, type_info in column_types.items():
                col_type = type_info.get('type', 'string')
                if col_type in ['ip_address', 'email', 'url']:
                    semantic_tags_from_types.append(f'contains_{col_type}')
                elif col_type in ['date', 'datetime']:
                    semantic_tags_from_types.append('contains_temporal_data')
                elif col_type in ['integer', 'float']:
                    semantic_tags_from_types.append('contains_numeric_data')
            if semantic_tags_from_types:
                metadata['semantic_indicators'] = list(set(semantic_tags_from_types))
        
        # Validate metadata structure
        try:
            metadata = validate_metadata(metadata, 'table_row')
        except Exception as e:
            self.logger.warning(f"Metadata validation failed for row {row_idx}: {e}")
            # Continue with original metadata if validation fails
        
        # Build semantic tags
        base_tags = ['spreadsheet_row', 'short_text' if len(content) < 120 else 'long_text']
        if column_types and 'semantic_indicators' in metadata:
            base_tags.extend(metadata['semantic_indicators'])
        
        return DocumentElement(
            element_id=element_id,
            type='table_row',
            text=content,
            page_number=None,
            coordinates=None,
            parent_id=None,
            metadata=metadata,
            hierarchy_level=0,
            semantic_tags=list(set(base_tags)),  # Deduplicate tags
            confidence_score=0.95,
        )

    def _parse_csv_rows(self, file_path: str, filename: str) -> tuple[List[DocumentElement], Dict[str, Any]]:
        elements: List[DocumentElement] = []
        with open(file_path, 'r', encoding='utf-8', errors='ignore', newline='') as f:
            reader = csv.reader(f)
            rows = list(reader)
        if not rows:
            return [], {}
        headers = rows[0]
        data_rows = rows[1:]
        
        # Infer column types (Issue #7)
        column_types = {}
        try:
            from common.utils.column_type_inference import infer_column_types
            column_types = infer_column_types(
                headers=headers,
                rows=data_rows[:100],  # Sample first 100 rows
                sample_size=100,
                min_confidence=0.7,
                include_stats=True
            )
            logger.debug(f"Inferred types for {len(column_types)} columns in CSV '{filename}'")
        except Exception as type_err:
            logger.warning(f"Column type inference failed for CSV '{filename}': {type_err}")
        
        for idx, row in enumerate(data_rows, start=2):  # 1-based including header; data starts at 2
            try:
                el = self._make_row_element(filename, 'Sheet1', idx, headers, row, column_types)
                # skip empty rows
                if any(v for v in (el.metadata.get('row_data') or {}).values()):
                    elements.append(el)
            except Exception:
                continue
        stats = {
            'spreadsheet_rows': len(elements),
            'spreadsheet_sheets': ['Sheet1'],
            'spreadsheet_parser': 'csv',
        }
        return elements, stats

    def _parse_xlsx_rows_openpyxl(self, file_path: str, filename: str) -> tuple[List[DocumentElement], Dict[str, Any]]:
        try:
            import openpyxl  # type: ignore
        except Exception as e:
            logger.debug(f"openpyxl not available for XLSX parsing: {e}")
            return [], {}
        wb = openpyxl.load_workbook(file_path, data_only=True, read_only=True)
        elements: List[DocumentElement] = []
        sheets: List[str] = []
        for ws in wb.worksheets:
            try:
                sheets.append(ws.title)
                rows_iter = ws.iter_rows(values_only=True)
                headers = None
                all_rows = []
                
                # First pass: collect headers and all rows
                for r_idx, row in enumerate(rows_iter, start=1):
                    if r_idx == 1:
                        headers = [str(c).strip() if c is not None else f"col_{i+1}" for i, c in enumerate(list(row or []))]
                        continue
                    if headers is None:
                        continue
                    values = list(row or [])
                    all_rows.append((r_idx, values))
                
                if not headers or not all_rows:
                    continue
                
                # Infer column types for this sheet (Issue #7)
                column_types = {}
                try:
                    from common.utils.column_type_inference import infer_column_types
                    rows_for_inference = [row_vals for _, row_vals in all_rows[:100]]  # Sample first 100 rows
                    column_types = infer_column_types(
                        headers=headers,
                        rows=rows_for_inference,
                        sample_size=100,
                        min_confidence=0.7,
                        include_stats=True
                    )
                    logger.debug(f"Inferred types for {len(column_types)} columns in sheet '{ws.title}'")
                except Exception as type_err:
                    logger.warning(f"Column type inference failed for sheet '{ws.title}': {type_err}")
                
                # Second pass: create elements with enriched metadata
                for r_idx, values in all_rows:
                    el = self._make_row_element(filename, ws.title, r_idx, headers, values, column_types)
                    if any(v for v in (el.metadata.get('row_data') or {}).values()):
                        elements.append(el)
                        
            except Exception as se:
                logger.debug(f"Sheet parse skipped ({ws.title}): {se}")
                continue
        stats = {
            'spreadsheet_rows': len(elements),
            'spreadsheet_sheets': sheets,
            'spreadsheet_parser': 'openpyxl',
        }
        return elements, stats

    def _parse_xls_rows_xlrd(self, file_path: str, filename: str) -> tuple[List[DocumentElement], Dict[str, Any]]:
        try:
            import xlrd  # type: ignore
        except Exception as e:
            logger.debug(f"xlrd not available for XLS parsing: {e}")
            return [], {}
        book = xlrd.open_workbook(file_path)
        elements: List[DocumentElement] = []
        sheets: List[str] = []
        for sheet in book.sheets():
            try:
                sheets.append(sheet.name)
                if sheet.nrows <= 1:
                    continue
                headers = [str(sheet.cell_value(0, c)).strip() if sheet.cell_value(0, c) not in (None, '') else f"col_{c+1}" for c in range(sheet.ncols)]
                
                # Collect all rows for type inference
                all_rows = []
                for r in range(1, sheet.nrows):
                    values = [sheet.cell_value(r, c) for c in range(sheet.ncols)]
                    all_rows.append((r+1, values))
                
                # Infer column types (Issue #7)
                column_types = {}
                try:
                    from common.utils.column_type_inference import infer_column_types
                    rows_for_inference = [row_vals for _, row_vals in all_rows[:100]]  # Sample first 100 rows
                    column_types = infer_column_types(
                        headers=headers,
                        rows=rows_for_inference,
                        sample_size=100,
                        min_confidence=0.7,
                        include_stats=True
                    )
                    logger.debug(f"Inferred types for {len(column_types)} columns in sheet '{sheet.name}'")
                except Exception as type_err:
                    logger.warning(f"Column type inference failed for sheet '{sheet.name}': {type_err}")
                
                # Create elements with enriched metadata
                for r_idx, values in all_rows:
                    el = self._make_row_element(filename, sheet.name, r_idx, headers, values, column_types)
                    if any(v for v in (el.metadata.get('row_data') or {}).values()):
                        elements.append(el)
            except Exception as se:
                logger.debug(f"Sheet parse skipped ({sheet.name}): {se}")
                continue
        stats = {
            'spreadsheet_rows': len(elements),
            'spreadsheet_sheets': sheets,
            'spreadsheet_parser': 'xlrd',
        }
        return elements, stats

    async def _process_with_mineru_if_enabled(
        self,
        file_path: str,
        filename: str
    ) -> Optional[List[DocumentElement]]:
        """Attempt MinerU parsing for PDFs when enabled; return None to fallback otherwise."""
        try:
            if not self._mineru.is_enabled():
                return None
            # Only attempt for PDFs for now
            if not filename.lower().endswith('.pdf'):
                return None
            # MinerU adapter returns list of canonical dicts or None
            els = self._mineru.process_pdf_to_elements(file_path, filename)
            if not els:
                return None
            mapped: List[DocumentElement] = []
            for e in els:
                try:
                    mapped.append(DocumentElement(
                        element_id=e.get('element_id') or str(uuid.uuid4()),
                        type=str(e.get('type', 'unknown')).lower().replace(' ', '_'),
                        text=e.get('text') or '',
                        page_number=e.get('page_number'),
                        coordinates=e.get('coordinates'),
                        parent_id=e.get('parent_id'),
                        metadata=e.get('metadata') or {},
                        hierarchy_level=e.get('hierarchy_level'),
                        semantic_tags=e.get('semantic_tags'),
                        confidence_score=e.get('confidence_score'),
                    ))
                except Exception as me:
                    logger.debug(f"Skipping MinerU element mapping error: {me}")
            if mapped:
                # Perform advanced structural enhancement: section paths, caption linkage, multi-page table merging
                try:
                    self._enhance_mineru_structure(mapped)
                except Exception as enh_e:
                    logger.debug(f"MinerU structural enhancement failed (non-fatal): {enh_e}")
                logger.info(f"MinerU produced {len(mapped)} elements for {filename}")
                return mapped
            return None
        except Exception as e:
            logger.debug(f"MinerU attempt failed, will fallback: {e}")
            return None
    
    async def _process_with_unstructured(
        self,
        file_path: str,
        extract_images: bool,
        extract_tables: bool,
        include_coordinates: bool
    ) -> List[Element]:
        """Process document using unstructured library"""
        
        if not UNSTRUCTURED_AVAILABLE:
            raise ImportError("unstructured library not available")
        
        # Configure unstructured processing parameters
        partition_kwargs = {
            'filename': file_path,
            'strategy': 'hi_res',  # High resolution for better accuracy
            'include_page_breaks': True,
            'infer_table_structure': extract_tables,
            'extract_images_in_pdf': extract_images,
            'include_metadata': True,
            # Note: coordinates are now included via include_metadata=True by default
            # Setting coordinates=True separately causes "multiple values" error
        }
        
        # IMPORTANT: DO NOT add coordinates parameter separately
        # The unstructured library automatically includes coordinates when include_metadata=True
        # Adding coordinates=True again causes "got multiple values for keyword argument 'coordinates'"
        
        try:
            # Run partitioning in thread to avoid blocking
            elements = await asyncio.to_thread(partition, **partition_kwargs)
            return elements
        except Exception as e:
            # Enhanced error handling for Tesseract issues
            error_msg = str(e)
            if "tesseract is not installed" in error_msg.lower() or "tesseract" in error_msg.lower():
                logger.error(f"Tesseract OCR dependency missing for structured processing: {e}")
                logger.error("✗ Tesseract OCR required for advanced document structuring")
                logger.error("  Install: https://github.com/UB-Mannheim/tesseract/wiki")
                logger.error("  Windows: Download installer and add to PATH")
                logger.error("  Docker: Already included in service image")
                raise ImportError(f"Tesseract OCR dependency missing: {error_msg}")
            else:
                logger.error(f"Unstructured processing failed: {e}")
                raise
    
    def _post_process_elements(self, elements: List[Element]) -> List[DocumentElement]:
        """Post-process unstructured elements into our structured format"""
        processed_elements = []
        
        for i, element in enumerate(elements):
            try:
                # Extract basic information
                element_id = str(uuid.uuid4())
                element_type = getattr(element, 'category', 'unknown')
                text = str(element).strip()
                
                # Clean text
                text = clean_extra_whitespace(text)
                if element_type == 'ListItem':
                    text = clean_bullets(text)
                
                # Extract metadata
                metadata = {}
                if hasattr(element, 'metadata') and element.metadata:
                    metadata = element.metadata.to_dict() if hasattr(element.metadata, 'to_dict') else dict(element.metadata)
                
                # Extract coordinates
                coordinates = None
                if 'coordinates' in metadata:
                    coord_data = metadata['coordinates']
                    if coord_data and hasattr(coord_data, 'to_dict'):
                        coordinates = coord_data.to_dict()
                    elif isinstance(coord_data, dict):
                        coordinates = coord_data
                
                # Extract page number
                page_number = metadata.get('page_number')
                
                # Determine hierarchy level for headings
                hierarchy_level = None
                if element_type in ['Title', 'Header']:
                    hierarchy_level = metadata.get('category_depth', 1)
                
                # Generate semantic tags
                semantic_tags = self._generate_semantic_tags(element_type, text, metadata)
                
                # Calculate confidence score
                confidence_score = self._calculate_confidence_score(element_type, text, metadata)
                
                processed_element = DocumentElement(
                    element_id=element_id,
                    type=element_type.lower().replace(' ', '_'),
                    text=text,
                    page_number=page_number,
                    coordinates=coordinates,
                    parent_id=None,  # Can be enhanced with parent-child relationships
                    metadata=metadata,
                    hierarchy_level=hierarchy_level,
                    semantic_tags=semantic_tags,
                    confidence_score=confidence_score
                )
                
                processed_elements.append(processed_element)
                
            except Exception as e:
                logger.warning(f"Error processing element {i}: {e}")
                continue
        
        return processed_elements
    
    def _generate_semantic_tags(self, element_type: str, text: str, metadata: Dict) -> List[str]:
        """Generate semantic tags for better categorization"""
        tags = [element_type.lower()]
        
        # Add length-based tags
        if len(text) > 1000:
            tags.append('long_text')
        elif len(text) < 50:
            tags.append('short_text')
        
        # Add content-based tags
        if any(keyword in text.lower() for keyword in ['table', 'figure', 'chart', 'graph']):
            tags.append('visual_reference')
        
        if any(keyword in text.lower() for keyword in ['conclusion', 'summary', 'abstract']):
            tags.append('summary_content')
        
        if text.count('\n') > 5:
            tags.append('multi_line')
        
        # Add metadata-based tags
        if metadata.get('is_continuation'):
            tags.append('continuation')
        
        return tags
    
    def _calculate_confidence_score(self, element_type: str, text: str, metadata: Dict) -> float:
        """Calculate confidence score for element extraction"""
        score = 0.8  # Base score
        
        # Adjust based on element type
        high_confidence_types = ['Title', 'Header', 'Table']
        if element_type in high_confidence_types:
            score += 0.1
        
        # Adjust based on text length and quality
        if len(text.strip()) < 5:
            score -= 0.3
        elif len(text.strip()) > 20:
            score += 0.1
        
        # Adjust based on metadata availability
        if metadata.get('coordinates'):
            score += 0.05
        if metadata.get('page_number'):
            score += 0.05
        
        return min(max(score, 0.0), 1.0)
    
    def _get_element_type_counts(self, elements: List[DocumentElement]) -> Dict[str, int]:
        """Get count of each element type"""
        counts = {}
        for element in elements:
            counts[element.type] = counts.get(element.type, 0) + 1
        return counts
    
    def _get_mime_type(self, file_ext: str) -> str:
        """Get MIME type based on file extension"""
        mime_types = {
            '.pdf': 'application/pdf',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.doc': 'application/msword',
            '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            '.ppt': 'application/vnd.ms-powerpoint',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.xls': 'application/vnd.ms-excel',
            '.txt': 'text/plain',
            '.md': 'text/markdown',
            '.html': 'text/html',
            '.htm': 'text/html',
            '.xml': 'text/xml',
            '.json': 'application/json',
            '.csv': 'text/csv'
        }
        return mime_types.get(file_ext.lower(), 'application/octet-stream')

    # -------------------- MinerU Structural Enhancement --------------------
    def _enhance_mineru_structure(self, elements: List[DocumentElement]) -> None:
        """Augment MinerU-mapped elements with:
        - Canonical hierarchical section_path assignment where missing
        - Caption -> table (or figure) linkage (parent/metadata cross references)
        - Multi-page table merging (tables with identical header on consecutive pages)
        Adds lightweight metrics into element metadata for later stats aggregation.
        Mutates list in-place (may remove merged table fragments).
        """
        if not elements:
            return

        # Sort elements by (page_number, existing order hint in metadata, fallback index)
        enumerated = list(enumerate(elements))
        def _order_key(pair):
            idx, el = pair
            page = el.page_number or 0
            order = el.metadata.get('order', idx)
            return (page, order, idx)
        enumerated.sort(key=_order_key)
        elements[:] = [el for _i, el in enumerated]

        # 1. Hierarchical section path derivation
        section_counters: List[int] = []  # stack of counters per depth

        def _bump(depth: int) -> List[int]:
            if depth < 1:
                depth = 1
            # grow
            while len(section_counters) < depth:
                section_counters.append(0)
            # shrink if moving up
            while len(section_counters) > depth:
                section_counters.pop()
            # increment leaf
            section_counters[-1] += 1
            return list(section_counters)

        last_section_path: List[int] | None = None
        assigned_section_paths = 0

        import re
        header_like = {"title", "header"}
        for el in elements:
            if el.type in header_like:
                # attempt to infer depth from leading numeric enumeration (e.g., 1.2.3)
                depth = 1 if el.type == 'title' else 2
                m = re.match(r"\s*(\d+(?:\.\d+){0,10})", el.text.strip())
                if m:
                    depth = min(len(m.group(1).split('.')) + 0, 8)  # +0 to keep title depth at 1 if numeric appears
                if not el.metadata.get('section_path'):
                    sec_path = _bump(depth)
                    el.metadata['section_path'] = sec_path
                    assigned_section_paths += 1
                    last_section_path = sec_path
                else:
                    last_section_path = el.metadata.get('section_path')
            else:
                # propagate last section path to narrative / tables / images for easier grouping
                if last_section_path and not el.metadata.get('section_path'):
                    el.metadata['section_path'] = list(last_section_path)
                    assigned_section_paths += 1

        # 2. Caption linkage
        id_index: Dict[str, DocumentElement] = {el.element_id: el for el in elements}
        captions_linked = 0
        for el in elements:
            if el.type == 'caption':
                target_id = el.metadata.get('caption_for')
                if target_id and target_id in id_index:
                    target = id_index[target_id]
                    # Link caption to target via parent_id if unset, plus mutual metadata references
                    if el.parent_id is None:
                        el.parent_id = target.element_id
                    target.metadata.setdefault('captions', []).append(el.element_id)
                    el.metadata['caption_target_kind'] = target.type
                    captions_linked += 1

        # 3. Multi-page table merging
        merged_tables = 0
        # Build sequence of tables after ordering
        i = 0
        while i < len(elements) - 1:
            current = elements[i]
            if current.type != 'table':
                i += 1
                continue
            j = i + 1
            while j < len(elements):
                nxt = elements[j]
                if nxt.type != 'table':
                    break  # only merge directly following tables
                # check page adjacency (allow same page continuation if metadata suggests continuation)
                cur_page = current.page_number or 0
                nxt_page = nxt.page_number or 0
                if nxt_page - cur_page not in (0, 1):
                    break
                # simple header comparison using first line tokens
                def _header_tokens(txt: str) -> List[str]:
                    lines = [ln for ln in (txt or '').splitlines() if ln.strip()]
                    if not lines:
                        return []
                    return [c.strip().lower() for c in lines[0].split() if c.strip()]
                cur_header = _header_tokens(current.text)
                nxt_header = _header_tokens(nxt.text)
                if cur_header and nxt_header and cur_header == nxt_header:
                    # merge: append next body lines excluding header
                    cur_lines = [ln for ln in current.text.splitlines() if ln.strip()]
                    nxt_lines = [ln for ln in nxt.text.splitlines() if ln.strip()]
                    if nxt_lines:
                        body_to_add = nxt_lines[1:] if len(nxt_lines) > 1 else []
                        # avoid duplicate rows
                        existing_set = set(cur_lines)
                        for row in body_to_add:
                            if row not in existing_set:
                                cur_lines.append(row)
                                existing_set.add(row)
                        current.text = "\n".join(cur_lines)
                        current.metadata.setdefault('merged_table_source_ids', []).append(nxt.element_id)
                        nxt.metadata['merged_into'] = current.element_id
                        merged_tables += 1
                        # drop nxt
                        elements.pop(j)
                        continue  # re-evaluate same j index after pop
                break  # break if not mergeable
            i += 1

        # Store enhancement summary on first element metadata for later stats (non-intrusive)
        if elements:
            elements[0].metadata.setdefault('mineru_enhancement', {})
            elements[0].metadata['mineru_enhancement'].update({
                'assigned_section_paths': assigned_section_paths,
                'captions_linked': captions_linked,
                'merged_tables': merged_tables,
            })

    
    async def save_structured_output(
        self,
        result: ProcessingResult,
        output_path: str,
        format_type: str = 'jsonl'
    ) -> str:
        """Save processing result to file"""
        
        if format_type == 'jsonl':
            content = result.to_jsonl()
            file_ext = '.jsonl'
        elif format_type == 'json':
            content = json.dumps(result.to_dict(), indent=2, ensure_ascii=False)
            file_ext = '.json'
        else:
            raise ValueError(f"Unsupported format: {format_type}")
        
        output_file = f"{output_path}{file_ext}"
        
        # Use asyncio.to_thread to run file I/O in a thread
        await asyncio.to_thread(self._write_file_sync, output_file, content)
        
        return output_file
    
    def _write_file_sync(self, filepath: str, content: str):
        """Synchronous file writing helper"""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def get_processing_summary(self, result: ProcessingResult) -> Dict[str, Any]:
        """Get a summary of processing results"""
        return {
            'filename': result.document_metadata.filename,
            'status': result.status,
            'total_elements': len(result.elements),
            'processing_time': result.processing_stats.get('processing_time_seconds', 0),
            'element_types': result.processing_stats.get('element_types', {}),
            'pages_processed': result.processing_stats.get('pages_processed', 0),
            'errors': len(result.errors),
            'warnings': len(result.warnings)
        }

    # -------------------- Layout JSONL Generation (MinerU / Unstructured Hybrid) --------------------
    def generate_layout_jsonl(self, result: ProcessingResult, mineru_used: bool = False) -> str:
        """Generate a layout-focused JSONL capturing positional blocks independent of semantic element filtering.

        Each line (except summary) has structure:
          {"type": "layout_block", "data": {block_id, page_number, kind, bbox:[x1,y1,x2,y2], reading_order, text_preview,
                                               source, parent_id, confidence}}

        Final line:
          {"type": "layout_summary", "data": {total_blocks, pages, mineru_used, generation_time_iso}}

        Notes:
        - We derive reading_order as the index encountered per page.
        - bbox is pulled from element.coordinates when available; otherwise empty list.
        - kind is the element.type already normalized (e.g., title, narrative_text, table, image).
        - text_preview is truncated to 160 chars with newlines collapsed.
        - confidence falls back to element.confidence_score or 0.8.
        """
        try:
            import json, time
            start = time.time()
            lines: list[str] = []
            page_counters: Dict[int, int] = {}
            pages_seen = set()

            for elem in result.elements:
                page = elem.page_number or 1
                pages_seen.add(page)
                page_counters.setdefault(page, 0)
                ro = page_counters[page]
                page_counters[page] += 1

                coords = []
                if elem.coordinates and isinstance(elem.coordinates, dict):
                    # Accept either {x1,y1,x2,y2} or nested structure
                    c = elem.coordinates
                    for k in ("x1","y1","x2","y2"):
                        if k not in c:
                            break
                    if all(k in c for k in ("x1","y1","x2","y2")):
                        coords = [c.get('x1'), c.get('y1'), c.get('x2'), c.get('y2')]

                text_preview = (elem.text or "").replace('\n', ' ').strip()
                if len(text_preview) > 160:
                    text_preview = text_preview[:157] + '...'

                block = {
                    "type": "layout_block",
                    "data": {
                        "block_id": elem.element_id,
                        "page_number": page,
                        "kind": elem.type,
                        "bbox": coords,
                        "reading_order": ro,
                        "text_preview": text_preview,
                        "source": "mineru" if mineru_used else "unstructured",
                        "parent_id": elem.parent_id,
                        "confidence": elem.confidence_score or 0.8,
                    }
                }
                lines.append(json.dumps(block, ensure_ascii=False))

            summary = {
                "type": "layout_summary",
                "data": {
                    "total_blocks": len(lines),
                    "pages": sorted(pages_seen),
                    "mineru_used": bool(mineru_used),
                    "generation_time_seconds": round(time.time() - start, 4)
                }
            }
            lines.append(json.dumps(summary, ensure_ascii=False))
            return "\n".join(lines)
        except Exception as e:
            logger.error(f"Layout JSONL generation failed: {e}")
            # Return a single-line JSON object representing the error
            err = {
                "type": "layout_error",
                "data": {"error": str(e)}
            }
            try:
                return json.dumps(err, ensure_ascii=False)
            except Exception:
                return '{"type":"layout_error","data":{"error":"unserializable"}}'