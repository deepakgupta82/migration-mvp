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
from datetime import datetime
from typing import Optional, Dict, Any, List, Union
from dataclasses import dataclass, asdict
from pathlib import Path
import uuid

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
        }))

        # Elements as individual lines
        for element in self.elements:
            element_data = element.to_dict()
            # Add LLM confidence score to elements if available
            if llm_analysis_result and llm_analysis_result.get("status") == "success":
                element_data["llm_confidence"] = llm_analysis_result.get("metadata", {}).get("confidence_score", 0.8)
            lines.append(json.dumps({
                'type': 'element',
                'data': element_data
            }))

        # Processing summary with LLM analysis
        processing_summary = {
            'processing_stats': self.processing_stats,
            'status': self.status,
            'errors': self.errors,
            'warnings': self.warnings
        }

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
        }))

        return '\n'.join(lines)

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
            
            # Process with unstructured
            elements = await self._process_with_unstructured(
                file_path, extract_images, extract_tables, include_coordinates
            )
            
            # Post-process elements
            processed_elements = self._post_process_elements(elements)
            
            # Calculate processing stats
            end_time = datetime.now()
            processing_stats = {
                'processing_time_seconds': (end_time - start_time).total_seconds(),
                'total_elements': len(processed_elements),
                'element_types': self._get_element_type_counts(processed_elements),
                'total_text_length': sum(len(elem.text) for elem in processed_elements),
                'pages_processed': max((elem.page_number or 0 for elem in processed_elements), default=0)
            }
            
            logger.info(f"Successfully processed {filename}: {len(processed_elements)} elements in {processing_stats['processing_time_seconds']:.2f}s")
            
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
            
            return ProcessingResult(
                document_metadata=doc_metadata,
                elements=[],
                processing_stats={
                    'processing_time_seconds': (datetime.now() - start_time).total_seconds(),
                    'total_elements': 0,
                    'element_types': {},
                    'total_text_length': 0,
                    'pages_processed': 0
                },
                status='error',
                errors=errors,
                warnings=warnings
            )
    
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