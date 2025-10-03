"""
Safe JSON parsing utilities with error boundaries and fallback strategies.
Prevents crashes from malformed JSON in LLM responses and external data.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Union


logger = logging.getLogger(__name__)


def safe_json_parse(
    data: str,
    default: Any = None,
    context: str = "unknown",
    attempt_repair: bool = True,
    log_errors: bool = True
) -> Any:
    """
    Safely parse JSON with multiple fallback strategies.
    
    Args:
        data: JSON string to parse
        default: Default value to return on failure
        context: Context description for error logging
        attempt_repair: Whether to attempt repairing malformed JSON
        log_errors: Whether to log parsing errors
        
    Returns:
        Parsed JSON object or default value
        
    Examples:
        >>> safe_json_parse('{"key": "value"}')
        {'key': 'value'}
        >>> safe_json_parse('invalid json', default={})
        {}
        >>> safe_json_parse('{"key": "value"', attempt_repair=True)
        {'key': 'value'}
    """
    if not data or not isinstance(data, str):
        if log_errors:
            logger.warning(f"[{context}] Invalid JSON input type: {type(data)}")
        return default
    
    # Strategy 1: Standard JSON parsing
    try:
        return json.loads(data)
    except json.JSONDecodeError as e:
        if log_errors:
            logger.debug(f"[{context}] Standard JSON parsing failed: {e}")
        
        if not attempt_repair:
            return default
    
    # Strategy 2: Try to repair common JSON issues
    repaired_data = _attempt_json_repair(data)
    if repaired_data != data:
        try:
            result = json.loads(repaired_data)
            if log_errors:
                logger.info(f"[{context}] JSON repaired successfully")
            return result
        except json.JSONDecodeError as e:
            if log_errors:
                logger.debug(f"[{context}] JSON repair failed: {e}")
    
    # Strategy 3: Extract JSON object/array from text
    extracted = _extract_json_from_text(data)
    if extracted:
        try:
            result = json.loads(extracted)
            if log_errors:
                logger.info(f"[{context}] JSON extracted from text successfully")
            return result
        except json.JSONDecodeError as e:
            if log_errors:
                logger.debug(f"[{context}] Extracted JSON parsing failed: {e}")
    
    # Strategy 4: Try eval as last resort (DANGEROUS - only for trusted sources)
    # DISABLED by default for security
    
    if log_errors:
        logger.error(f"[{context}] All JSON parsing strategies failed. Sample: {data[:200]}")
    
    return default


def _attempt_json_repair(data: str) -> str:
    """
    Attempt to repair common JSON issues.
    
    Repairs:
    - Missing closing braces/brackets
    - Trailing commas
    - Single quotes to double quotes
    - Escaped newlines
    - Unicode escapes
    
    Args:
        data: Malformed JSON string
        
    Returns:
        Repaired JSON string
    """
    repaired = data.strip()
    
    # Remove trailing commas before closing braces/brackets
    repaired = re.sub(r',(\s*[}\]])', r'\1', repaired)
    
    # Replace single quotes with double quotes (risky but common issue)
    # Only if no double quotes exist
    if '"' not in repaired:
        repaired = repaired.replace("'", '"')
    
    # Fix escaped newlines
    repaired = repaired.replace('\\n', ' ')
    
    # Remove control characters
    repaired = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', repaired)
    
    # Try to balance braces/brackets
    open_braces = repaired.count('{')
    close_braces = repaired.count('}')
    if open_braces > close_braces:
        repaired += '}' * (open_braces - close_braces)
    
    open_brackets = repaired.count('[')
    close_brackets = repaired.count(']')
    if open_brackets > close_brackets:
        repaired += ']' * (open_brackets - close_brackets)
    
    return repaired


def _extract_json_from_text(text: str) -> Optional[str]:
    """
    Extract JSON object or array from text (e.g., LLM responses with extra text).
    
    Args:
        text: Text containing JSON
        
    Returns:
        Extracted JSON string or None
    """
    # Try to find JSON object
    match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
    if match:
        return match.group(0)
    
    # Try to find JSON array
    match = re.search(r'\[[^\[\]]*(?:\[[^\[\]]*\][^\[\]]*)*\]', text, re.DOTALL)
    if match:
        return match.group(0)
    
    return None


def safe_json_loads(
    data: Union[str, bytes],
    default: Any = None,
    encoding: str = 'utf-8'
) -> Any:
    """
    Safely load JSON from string or bytes.
    
    Args:
        data: JSON data as string or bytes
        default: Default value on failure
        encoding: Encoding for bytes data
        
    Returns:
        Parsed JSON or default
    """
    if isinstance(data, bytes):
        try:
            data = data.decode(encoding)
        except UnicodeDecodeError:
            logger.warning(f"Failed to decode bytes with {encoding}")
            return default
    
    return safe_json_parse(data, default=default)


def safe_json_dumps(
    obj: Any,
    default: str = "{}",
    indent: Optional[int] = None,
    ensure_ascii: bool = False
) -> str:
    """
    Safely serialize object to JSON string.
    
    Args:
        obj: Object to serialize
        default: Default string on failure
        indent: Indentation for pretty printing
        ensure_ascii: Whether to escape non-ASCII characters
        
    Returns:
        JSON string or default
    """
    try:
        return json.dumps(obj, indent=indent, ensure_ascii=ensure_ascii, default=str)
    except (TypeError, ValueError) as e:
        logger.error(f"JSON serialization failed: {e}")
        return default


def extract_json_field(
    data: Union[str, Dict],
    field: str,
    default: Any = None,
    field_type: Optional[type] = None
) -> Any:
    """
    Extract a specific field from JSON data with type checking.
    
    Args:
        data: JSON string or dict
        field: Field name to extract
        default: Default value if field missing
        field_type: Expected type of field value
        
    Returns:
        Field value or default
        
    Examples:
        >>> extract_json_field('{"name": "test"}', 'name')
        'test'
        >>> extract_json_field({'count': 5}, 'count', field_type=int)
        5
        >>> extract_json_field('invalid', 'key', default='N/A')
        'N/A'
    """
    # Parse if string
    if isinstance(data, str):
        data = safe_json_parse(data, default={})
    
    if not isinstance(data, dict):
        return default
    
    value = data.get(field, default)
    
    # Type checking
    if field_type and value is not None and not isinstance(value, field_type):
        logger.warning(f"Field '{field}' has wrong type: expected {field_type}, got {type(value)}")
        return default
    
    return value


def extract_nested_field(
    data: Union[str, Dict],
    path: str,
    default: Any = None,
    separator: str = '.'
) -> Any:
    """
    Extract nested field from JSON data using dot notation.
    
    Args:
        data: JSON string or dict
        path: Dot-separated path (e.g., 'user.profile.name')
        default: Default value if path not found
        separator: Path separator character
        
    Returns:
        Nested field value or default
        
    Examples:
        >>> extract_nested_field({'user': {'name': 'Alice'}}, 'user.name')
        'Alice'
        >>> extract_nested_field('{"a": {"b": {"c": 123}}}', 'a.b.c')
        123
    """
    # Parse if string
    if isinstance(data, str):
        data = safe_json_parse(data, default={})
    
    if not isinstance(data, dict):
        return default
    
    keys = path.split(separator)
    current = data
    
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
        if current is None:
            return default
    
    return current


def validate_json_structure(
    data: Union[str, Dict],
    required_fields: Optional[List[str]] = None,
    optional_fields: Optional[List[str]] = None,
    strict: bool = False
) -> tuple[bool, List[str]]:
    """
    Validate JSON structure against expected fields.
    
    Args:
        data: JSON string or dict
        required_fields: List of required field names
        optional_fields: List of optional field names
        strict: If True, reject extra fields not in required/optional
        
    Returns:
        Tuple of (is_valid, list_of_errors)
        
    Examples:
        >>> validate_json_structure({'name': 'test'}, required_fields=['name'])
        (True, [])
        >>> validate_json_structure({}, required_fields=['name'])
        (False, ['Missing required field: name'])
    """
    # Parse if string
    if isinstance(data, str):
        data = safe_json_parse(data, default={})
    
    if not isinstance(data, dict):
        return False, ["Data is not a JSON object"]
    
    errors = []
    
    # Check required fields
    if required_fields:
        for field in required_fields:
            if field not in data:
                errors.append(f"Missing required field: {field}")
    
    # Check for unexpected fields in strict mode
    if strict and (required_fields or optional_fields):
        allowed = set(required_fields or []) | set(optional_fields or [])
        for field in data.keys():
            if field not in allowed:
                errors.append(f"Unexpected field: {field}")
    
    return len(errors) == 0, errors


def merge_json_safe(
    base: Dict[str, Any],
    update: Dict[str, Any],
    overwrite: bool = True
) -> Dict[str, Any]:
    """
    Safely merge two JSON objects.
    
    Args:
        base: Base dictionary
        update: Dictionary to merge in
        overwrite: Whether to overwrite existing keys
        
    Returns:
        Merged dictionary
    """
    result = base.copy()
    
    for key, value in update.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # Recursively merge nested dicts
            result[key] = merge_json_safe(result[key], value, overwrite)
        elif key not in result or overwrite:
            result[key] = value
    
    return result
