"""
Pydantic schemas for validating DocumentElement metadata structures.
Ensures type safety and prevents metadata-related runtime errors.
"""

from typing import Optional, Dict, Any, List, Union
from pydantic import BaseModel, Field, validator


class TableMetadata(BaseModel):
    """Metadata for table elements from MinerU or Unstructured."""
    
    table_data: Optional[Dict[str, Any]] = Field(
        None,
        description="Structured table data with columns and rows"
    )
    rows: Optional[int] = Field(None, description="Number of rows in table")
    columns: Optional[Union[int, List[str]]] = Field(
        None,
        description="Number of columns (int) or column headers (List[str])"
    )
    caption: Optional[str] = Field(None, description="Table caption if available")
    caption_for: Optional[str] = Field(
        None,
        description="Element ID this caption describes"
    )
    table_format: Optional[str] = Field(
        None,
        description="Table format: html, markdown, csv, etc."
    )
    page_number: Optional[int] = Field(None, description="Page number")
    bbox: Optional[List[float]] = Field(
        None,
        description="Bounding box [x1, y1, x2, y2]"
    )
    
    @validator('columns')
    def validate_columns(cls, v):
        """Ensure columns is either int or list of strings."""
        if v is not None:
            if isinstance(v, int):
                return v
            elif isinstance(v, list):
                if not all(isinstance(col, str) for col in v):
                    raise ValueError("All column names must be strings")
                return v
            else:
                raise ValueError(f"columns must be int or List[str], got {type(v)}")
        return v
    
    @validator('table_data', pre=True)
    def validate_table_data(cls, v):
        """Ensure table_data is a dict if present."""
        if v is not None and not isinstance(v, dict):
            raise ValueError(f"table_data must be a dict, got {type(v)}")
        return v
    
    @validator('bbox')
    def validate_bbox(cls, v):
        """Ensure bbox has 4 coordinates if present."""
        if v is not None and len(v) != 4:
            raise ValueError(f"bbox must have 4 coordinates, got {len(v)}")
        return v


class RowMetadata(BaseModel):
    """Metadata for table row elements from Excel/CSV parsing."""
    
    sheet_name: Optional[str] = Field(None, description="Excel sheet name")
    row_index: Optional[int] = Field(None, description="Row number (0-indexed)")
    columns: Optional[List[str]] = Field(
        None,
        description="Column headers for this row"
    )
    row_data: Optional[Dict[str, Any]] = Field(
        None,
        description="Row data as dict mapping column name to value"
    )
    is_header: Optional[bool] = Field(
        False,
        description="Whether this row is a header row"
    )
    table_name: Optional[str] = Field(
        None,
        description="Logical table name if detected"
    )
    
    @validator('row_data', pre=True)
    def validate_row_data(cls, v):
        """Ensure row_data is a dict if present."""
        if v is not None and not isinstance(v, dict):
            raise ValueError(f"row_data must be a dict, got {type(v)}")
        return v
    
    @validator('columns')
    def validate_columns(cls, v):
        """Ensure columns is a list of strings if present."""
        if v is not None:
            if not isinstance(v, list):
                raise ValueError(f"columns must be a list, got {type(v)}")
            if not all(isinstance(col, str) for col in v):
                raise ValueError("All column names must be strings")
        return v


class ImageMetadata(BaseModel):
    """Metadata for image elements."""
    
    image_path: Optional[str] = Field(None, description="Path to extracted image")
    image_format: Optional[str] = Field(
        None,
        description="Image format: png, jpg, etc."
    )
    width: Optional[int] = Field(None, description="Image width in pixels")
    height: Optional[int] = Field(None, description="Image height in pixels")
    page_number: Optional[int] = Field(None, description="Page number")
    bbox: Optional[List[float]] = Field(
        None,
        description="Bounding box [x1, y1, x2, y2]"
    )
    ocr_text: Optional[str] = Field(
        None,
        description="OCR extracted text from image"
    )
    
    @validator('bbox')
    def validate_bbox(cls, v):
        """Ensure bbox has 4 coordinates if present."""
        if v is not None and len(v) != 4:
            raise ValueError(f"bbox must have 4 coordinates, got {len(v)}")
        return v


class NarrativeMetadata(BaseModel):
    """Metadata for narrative text elements (paragraphs, titles, etc.)."""
    
    page_number: Optional[int] = Field(None, description="Page number")
    section_depth: Optional[int] = Field(
        None,
        description="Heading/section depth level"
    )
    section_hierarchy: Optional[List[str]] = Field(
        None,
        description="Hierarchical section path"
    )
    parent_id: Optional[str] = Field(
        None,
        description="Parent element ID for hierarchical structure"
    )
    bbox: Optional[List[float]] = Field(
        None,
        description="Bounding box [x1, y1, x2, y2]"
    )
    font_size: Optional[float] = Field(None, description="Font size")
    is_bold: Optional[bool] = Field(None, description="Whether text is bold")
    is_italic: Optional[bool] = Field(None, description="Whether text is italic")
    
    @validator('bbox')
    def validate_bbox(cls, v):
        """Ensure bbox has 4 coordinates if present."""
        if v is not None and len(v) != 4:
            raise ValueError(f"bbox must have 4 coordinates, got {len(v)}")
        return v


class DocumentElementMetadata(BaseModel):
    """
    Unified metadata schema that can handle all element types.
    Uses union of all metadata types with dynamic validation.
    """
    
    # Common fields
    page_number: Optional[int] = None
    bbox: Optional[List[float]] = None
    
    # Table-specific
    table_data: Optional[Dict[str, Any]] = None
    rows: Optional[int] = None
    columns: Optional[Union[int, List[str]]] = None
    caption: Optional[str] = None
    caption_for: Optional[str] = None
    table_format: Optional[str] = None
    
    # Row-specific
    sheet_name: Optional[str] = None
    row_index: Optional[int] = None
    row_data: Optional[Dict[str, Any]] = None
    is_header: Optional[bool] = None
    table_name: Optional[str] = None
    
    # Image-specific
    image_path: Optional[str] = None
    image_format: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    ocr_text: Optional[str] = None
    
    # Narrative-specific
    section_depth: Optional[int] = None
    section_hierarchy: Optional[List[str]] = None
    parent_id: Optional[str] = None
    font_size: Optional[float] = None
    is_bold: Optional[bool] = None
    is_italic: Optional[bool] = None
    
    # Allow additional fields for backward compatibility
    class Config:
        extra = "allow"
    
    @validator('columns')
    def validate_columns(cls, v):
        """Ensure columns is either int or list of strings."""
        if v is not None:
            if isinstance(v, int):
                return v
            elif isinstance(v, list):
                if not all(isinstance(col, str) for col in v):
                    raise ValueError("All column names must be strings")
                return v
            else:
                raise ValueError(f"columns must be int or List[str], got {type(v)}")
        return v
    
    @validator('table_data', 'row_data', pre=True)
    def validate_dict_fields(cls, v):
        """Ensure dict fields are actually dicts."""
        if v is not None and not isinstance(v, dict):
            # Try to convert string to dict if it's JSON
            if isinstance(v, str):
                import json
                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    raise ValueError(f"Invalid JSON in dict field: {v[:100]}")
            raise ValueError(f"Dict field must be a dict, got {type(v)}")
        return v
    
    @validator('bbox')
    def validate_bbox(cls, v):
        """Ensure bbox has 4 coordinates if present."""
        if v is not None and len(v) != 4:
            raise ValueError(f"bbox must have 4 coordinates, got {len(v)}")
        return v
    
    @validator('section_hierarchy')
    def validate_section_hierarchy(cls, v):
        """Ensure section_hierarchy is a list of strings if present."""
        if v is not None:
            if not isinstance(v, list):
                raise ValueError(f"section_hierarchy must be a list, got {type(v)}")
            if not all(isinstance(s, str) for s in v):
                raise ValueError("All section hierarchy items must be strings")
        return v


def validate_metadata(metadata: Optional[Dict[str, Any]], element_type: str) -> Optional[Dict[str, Any]]:
    """
    Validate metadata structure based on element type.
    
    Args:
        metadata: Raw metadata dict
        element_type: Element type (table, table_row, image, narrativetext, etc.)
        
    Returns:
        Validated metadata dict or None if validation fails
        
    Raises:
        ValueError: If metadata structure is invalid
    """
    if metadata is None:
        return None
    
    try:
        # Use unified schema for all types (allows flexibility)
        validated = DocumentElementMetadata(**metadata)
        return validated.dict(exclude_none=True)
    except Exception as e:
        # Log the error but don't fail - return original metadata with warning
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Metadata validation failed for {element_type}: {e}. Using original metadata.")
        return metadata


def safe_get_metadata_field(metadata: Optional[Dict[str, Any]], field: str, default: Any = None) -> Any:
    """
    Safely extract a field from metadata with type checking.
    
    Args:
        metadata: Metadata dict
        field: Field name to extract
        default: Default value if field missing or invalid
        
    Returns:
        Field value or default
    """
    if metadata is None:
        return default
    
    try:
        value = metadata.get(field, default)
        return value if value is not None else default
    except Exception:
        return default
