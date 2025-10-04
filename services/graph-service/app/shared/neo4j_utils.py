"""
Neo4j Utility Functions

Provides utilities for preparing data for Neo4j storage, including:
- Property serialization to handle nested objects
- Type conversion for Neo4j compatibility
- Bidirectional conversion (to/from Neo4j format)

Neo4j Constraints:
- Property values must be primitives (str, int, float, bool, None)
- OR arrays of primitives (List[str], List[int], etc.)
- NO nested objects (dict, list of dicts) allowed
"""

import json
import logging
from typing import Any, Dict, List, Union

logger = logging.getLogger(__name__)


def prepare_properties_for_neo4j(
    props: Dict[str, Any],
    flatten_important_fields: bool = True
) -> Dict[str, Any]:
    """
    Prepare entity/relationship properties for Neo4j storage.
    
    Hybrid Strategy:
    1. Keep frequently-queried fields as primitives (for fast Cypher queries)
    2. Serialize complex nested structures as JSON strings (for complete preservation)
    
    Args:
        props: Original properties dictionary (may contain nested objects)
        flatten_important_fields: If True, extract key fields from nested objects
                                 for direct querying (e.g., validation_is_valid)
    
    Returns:
        Neo4j-compatible properties dictionary (no nested objects)
    
    Example:
        >>> props = {
        ...     "name": "server1",
        ...     "attributes": {
        ...         "ip": "10.0.0.1",
        ...         "nested_config": {"cpu": 4}
        ...     },
        ...     "validation_info": {
        ...         "is_valid": True,
        ...         "confidence_score": 0.85
        ...     }
        ... }
        >>> neo4j_props = prepare_properties_for_neo4j(props)
        >>> # Result:
        >>> # {
        >>> #     "name": "server1",
        >>> #     "attr_ip": "10.0.0.1",
        >>> #     "validation_is_valid": True,
        >>> #     "validation_confidence": 0.85,
        >>> #     "attributes_json": '{"ip": "10.0.0.1", "nested_config": {"cpu": 4}}',
        >>> #     "validation_info_json": '{"is_valid": true, "confidence_score": 0.85}'
        >>> # }
    """
    if not isinstance(props, dict):
        logger.warning(f"prepare_properties_for_neo4j received non-dict: {type(props)}")
        return {}
    
    neo4j_props = {}
    
    for key, value in props.items():
        # Handle validation_info specially (common in our entities)
        if key == 'validation_info' and isinstance(value, dict):
            if flatten_important_fields:
                # Extract key fields for direct querying
                neo4j_props['validation_is_valid'] = value.get('is_valid', True)
                neo4j_props['validation_confidence'] = value.get('confidence_score', 1.0)
                
                # Handle warnings/errors as string arrays if they're primitives
                warnings = value.get('warnings', [])
                if isinstance(warnings, list) and all(isinstance(w, str) for w in warnings):
                    neo4j_props['validation_warnings'] = warnings
                
                errors = value.get('errors', [])
                if isinstance(errors, list) and all(isinstance(e, str) for e in errors):
                    neo4j_props['validation_errors'] = errors
            
            # Preserve FULL structure as JSON for complete data retention
            neo4j_props['validation_info_json'] = json.dumps(value, ensure_ascii=False)
        
        # Handle attributes specially (common in our entities)
        elif key == 'attributes' and isinstance(value, dict):
            if flatten_important_fields:
                # Flatten top-level attributes for querying
                for attr_key, attr_value in value.items():
                    if isinstance(attr_value, (str, int, float, bool, type(None))):
                        neo4j_props[f'attr_{attr_key}'] = attr_value
                    elif isinstance(attr_value, list) and _is_primitive_list(attr_value):
                        neo4j_props[f'attr_{attr_key}'] = attr_value
            
            # Store full attributes as JSON for completeness
            neo4j_props['attributes_json'] = json.dumps(value, ensure_ascii=False)
        
        # Handle metadata (similar to attributes)
        elif key == 'metadata' and isinstance(value, dict):
            if flatten_important_fields:
                for meta_key, meta_value in value.items():
                    if isinstance(meta_value, (str, int, float, bool, type(None))):
                        neo4j_props[f'meta_{meta_key}'] = meta_value
                    elif isinstance(meta_value, list) and _is_primitive_list(meta_value):
                        neo4j_props[f'meta_{meta_key}'] = meta_value
            
            neo4j_props['metadata_json'] = json.dumps(value, ensure_ascii=False)
        
        # Handle tags (often present in entities)
        elif key == 'tags' and isinstance(value, list):
            if _is_primitive_list(value):
                neo4j_props['tags'] = value
            else:
                # Complex tags: serialize to JSON
                neo4j_props['tags_json'] = json.dumps(value, ensure_ascii=False)
        
        # Handle any other nested dict
        elif isinstance(value, dict):
            # Serialize entire dict to JSON
            neo4j_props[f'{key}_json'] = json.dumps(value, ensure_ascii=False)
        
        # Handle lists
        elif isinstance(value, list):
            if _is_primitive_list(value):
                # Neo4j allows arrays of primitives
                neo4j_props[key] = value
            else:
                # List contains complex objects: serialize
                neo4j_props[f'{key}_json'] = json.dumps(value, ensure_ascii=False)
        
        # Primitive types: store as-is
        elif isinstance(value, (str, int, float, bool, type(None))):
            neo4j_props[key] = value
        
        # Unknown type: serialize to JSON string as fallback
        else:
            try:
                neo4j_props[f'{key}_json'] = json.dumps(value, ensure_ascii=False, default=str)
            except Exception as e:
                logger.warning(f"Could not serialize property '{key}' (type={type(value)}): {e}")
                neo4j_props[key] = str(value)
    
    return neo4j_props


def restore_properties_from_neo4j(neo4j_props: Dict[str, Any]) -> Dict[str, Any]:
    """
    Restore original property structure from Neo4j-stored properties.
    Deserializes JSON strings back to dicts/lists.
    
    Args:
        neo4j_props: Properties retrieved from Neo4j (may contain *_json fields)
    
    Returns:
        Restored properties dictionary with original nested structure
    
    Example:
        >>> neo4j_props = {
        ...     "name": "server1",
        ...     "attr_ip": "10.0.0.1",
        ...     "validation_is_valid": True,
        ...     "attributes_json": '{"ip": "10.0.0.1", "nested": {"cpu": 4}}',
        ...     "validation_info_json": '{"is_valid": true, "confidence_score": 0.85}'
        ... }
        >>> original = restore_properties_from_neo4j(neo4j_props)
        >>> # Result:
        >>> # {
        >>> #     "name": "server1",
        >>> #     "attributes": {"ip": "10.0.0.1", "nested": {"cpu": 4}},
        >>> #     "validation_info": {"is_valid": true, "confidence_score": 0.85}
        >>> # }
    """
    if not isinstance(neo4j_props, dict):
        return {}
    
    restored = {}
    skip_keys = set()  # Keys to skip because they're flattened versions
    
    # First pass: identify and deserialize JSON fields
    for key, value in neo4j_props.items():
        if key.endswith('_json'):
            # Deserialize JSON back to dict/list
            original_key = key.replace('_json', '')
            try:
                restored[original_key] = json.loads(value) if isinstance(value, str) else value
                # Mark flattened versions for skipping
                if original_key == 'validation_info':
                    skip_keys.update(['validation_is_valid', 'validation_confidence', 
                                     'validation_warnings', 'validation_errors'])
                elif original_key == 'attributes':
                    # Skip all attr_* fields
                    skip_keys.update([k for k in neo4j_props.keys() if k.startswith('attr_')])
                elif original_key == 'metadata':
                    skip_keys.update([k for k in neo4j_props.keys() if k.startswith('meta_')])
            except json.JSONDecodeError as e:
                logger.warning(f"Could not deserialize JSON for key '{key}': {e}")
                restored[original_key] = value
    
    # Second pass: copy non-JSON, non-flattened fields
    for key, value in neo4j_props.items():
        if not key.endswith('_json') and key not in skip_keys:
            restored[key] = value
    
    return restored


def _is_primitive_list(lst: List[Any]) -> bool:
    """
    Check if a list contains only primitive types (Neo4j-compatible).
    
    Args:
        lst: List to check
    
    Returns:
        True if list contains only str/int/float/bool/None, False otherwise
    """
    if not isinstance(lst, list):
        return False
    
    if len(lst) == 0:
        return True
    
    return all(isinstance(item, (str, int, float, bool, type(None))) for item in lst)


def sanitize_property_value(value: Any) -> Any:
    """
    Sanitize a single property value for Neo4j compatibility.
    Converts unsupported types to supported ones.
    
    Args:
        value: Property value to sanitize
    
    Returns:
        Neo4j-compatible value
    """
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    
    if isinstance(value, list):
        if _is_primitive_list(value):
            return value
        else:
            return json.dumps(value, ensure_ascii=False)
    
    # Fallback: convert to string
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        return str(value)


# Convenience function for relationship properties
def prepare_relationship_properties(props: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prepare relationship properties for Neo4j storage.
    Similar to prepare_properties_for_neo4j but optimized for relationships.
    
    Relationships typically have simpler properties, so we skip flattening
    and just ensure Neo4j compatibility.
    
    Args:
        props: Relationship properties
    
    Returns:
        Neo4j-compatible relationship properties
    """
    return prepare_properties_for_neo4j(props, flatten_important_fields=False)
