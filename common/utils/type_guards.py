"""
Type guard utilities for safe handling of array vs scalar values.
Prevents runtime errors from type confusion in metadata and JSON parsing.
"""

from typing import Any, List, Optional, TypeVar, Union


T = TypeVar('T')


def is_array(value: Any) -> bool:
    """
    Check if a value is an array-like object (list or tuple).
    
    Args:
        value: Value to check
        
    Returns:
        True if value is a list or tuple, False otherwise
    """
    return isinstance(value, (list, tuple))


def is_scalar(value: Any) -> bool:
    """
    Check if a value is a scalar (not a collection).
    
    Args:
        value: Value to check
        
    Returns:
        True if value is a scalar (str, int, float, bool, None), False otherwise
    """
    return isinstance(value, (str, int, float, bool, type(None)))


def safe_get_first(value: Any, default: Any = None) -> Any:
    """
    Safely get the first element from an array, or return the value if it's a scalar.
    
    Args:
        value: Array or scalar value
        default: Default value if array is empty or value is None
        
    Returns:
        First element if array, the value itself if scalar, or default
        
    Examples:
        >>> safe_get_first([1, 2, 3])
        1
        >>> safe_get_first("hello")
        "hello"
        >>> safe_get_first([])
        None
        >>> safe_get_first([], "default")
        "default"
    """
    if value is None:
        return default
    
    if is_array(value):
        return value[0] if len(value) > 0 else default
    
    return value


def safe_iterate(value: Any) -> List[Any]:
    """
    Safely convert a value to an iterable list.
    
    Args:
        value: Array or scalar value
        
    Returns:
        List containing the value(s)
        
    Examples:
        >>> safe_iterate([1, 2, 3])
        [1, 2, 3]
        >>> safe_iterate("hello")
        ["hello"]
        >>> safe_iterate(None)
        []
    """
    if value is None:
        return []
    
    if is_array(value):
        return list(value)
    
    return [value]


def safe_get_list(value: Any, default: Optional[List[Any]] = None) -> List[Any]:
    """
    Safely convert a value to a list, handling both arrays and scalars.
    
    Args:
        value: Value to convert
        default: Default value if conversion fails
        
    Returns:
        List representation of the value
        
    Examples:
        >>> safe_get_list([1, 2, 3])
        [1, 2, 3]
        >>> safe_get_list("hello")
        ["hello"]
        >>> safe_get_list(None, [])
        []
    """
    if value is None:
        return default if default is not None else []
    
    if is_array(value):
        return list(value)
    
    return [value]


def safe_get_str(value: Any, default: str = "") -> str:
    """
    Safely convert a value to string.
    Handles arrays by joining or taking first element.
    
    Args:
        value: Value to convert
        default: Default value if conversion fails
        
    Returns:
        String representation of the value
        
    Examples:
        >>> safe_get_str("hello")
        "hello"
        >>> safe_get_str(["hello", "world"])
        "hello"
        >>> safe_get_str([])
        ""
        >>> safe_get_str(None)
        ""
    """
    if value is None:
        return default
    
    if is_array(value):
        if len(value) == 0:
            return default
        # Take first element if array
        return str(value[0]) if value[0] is not None else default
    
    return str(value)


def safe_get_int(value: Any, default: int = 0) -> int:
    """
    Safely convert a value to integer.
    Handles arrays by taking first element.
    
    Args:
        value: Value to convert
        default: Default value if conversion fails
        
    Returns:
        Integer representation of the value
        
    Examples:
        >>> safe_get_int("123")
        123
        >>> safe_get_int([456])
        456
        >>> safe_get_int("invalid")
        0
    """
    if value is None:
        return default
    
    if is_array(value):
        if len(value) == 0:
            return default
        value = value[0]
    
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def safe_get_float(value: Any, default: float = 0.0) -> float:
    """
    Safely convert a value to float.
    Handles arrays by taking first element.
    
    Args:
        value: Value to convert
        default: Default value if conversion fails
        
    Returns:
        Float representation of the value
    """
    if value is None:
        return default
    
    if is_array(value):
        if len(value) == 0:
            return default
        value = value[0]
    
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_get_bool(value: Any, default: bool = False) -> bool:
    """
    Safely convert a value to boolean.
    Handles arrays by taking first element.
    
    Args:
        value: Value to convert
        default: Default value if conversion fails
        
    Returns:
        Boolean representation of the value
    """
    if value is None:
        return default
    
    if is_array(value):
        if len(value) == 0:
            return default
        value = value[0]
    
    if isinstance(value, bool):
        return value
    
    if isinstance(value, str):
        return value.lower() in ('true', 'yes', '1', 'on')
    
    try:
        return bool(value)
    except (ValueError, TypeError):
        return default


def ensure_list(value: Any) -> List[Any]:
    """
    Ensure a value is a list. Wraps scalars in a list.
    
    Args:
        value: Value to ensure as list
        
    Returns:
        List representation of the value
        
    Examples:
        >>> ensure_list([1, 2, 3])
        [1, 2, 3]
        >>> ensure_list("hello")
        ["hello"]
        >>> ensure_list(None)
        []
    """
    if value is None:
        return []
    
    if is_array(value):
        return list(value)
    
    return [value]


def flatten_nested(value: Any, max_depth: int = 5) -> List[Any]:
    """
    Flatten nested arrays up to max_depth levels.
    
    Args:
        value: Value to flatten
        max_depth: Maximum nesting depth to flatten
        
    Returns:
        Flattened list
        
    Examples:
        >>> flatten_nested([[1, 2], [3, 4]])
        [1, 2, 3, 4]
        >>> flatten_nested([[[1, 2]], [[3, 4]]])
        [1, 2, 3, 4]
        >>> flatten_nested("hello")
        ["hello"]
    """
    if max_depth == 0:
        return ensure_list(value)
    
    if not is_array(value):
        return [value]
    
    result = []
    for item in value:
        if is_array(item):
            result.extend(flatten_nested(item, max_depth - 1))
        else:
            result.append(item)
    
    return result


def safe_dict_get(data: Any, key: str, default: Any = None, 
                  as_type: Optional[str] = None) -> Any:
    """
    Safely get a value from a dict-like object with type conversion.
    
    Args:
        data: Dict-like object
        key: Key to extract
        default: Default value if key missing
        as_type: Optional type conversion ('str', 'int', 'float', 'bool', 'list')
        
    Returns:
        Value from dict with optional type conversion
        
    Examples:
        >>> safe_dict_get({'a': '123'}, 'a', as_type='int')
        123
        >>> safe_dict_get({'a': [1, 2]}, 'a', as_type='str')
        '1'
        >>> safe_dict_get({}, 'missing', 'default')
        'default'
    """
    if not isinstance(data, dict):
        return default
    
    value = data.get(key, default)
    
    if as_type is None or value is None:
        return value
    
    type_converters = {
        'str': safe_get_str,
        'int': safe_get_int,
        'float': safe_get_float,
        'bool': safe_get_bool,
        'list': safe_get_list,
    }
    
    converter = type_converters.get(as_type)
    if converter:
        return converter(value, default)
    
    return value
