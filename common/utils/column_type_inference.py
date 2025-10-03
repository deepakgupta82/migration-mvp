"""
Column Type Inference Utility (Issue #7)

Infers data types for table columns to enrich JSONL metadata.
Helps downstream processing understand data semantics (dates, IPs, numbers, etc.).

This module analyzes column values across rows to determine:
- Data type (string, integer, float, boolean, date, datetime, ip_address, url, email)
- Format patterns (date formats, number formats)
- Nullability and uniqueness
- Value ranges and distributions

Example:
    Input columns:
        - "Server Name": ["prod-web-01", "prod-web-02", ...]  → type: string
        - "IP Address": ["10.0.1.5", "10.0.2.10", ...]        → type: ip_address
        - "CPU Cores": ["4", "8", "16", ...]                  → type: integer
        - "Created": ["2024-01-15", "2024-02-20", ...]        → type: date
    
    Output metadata enrichment:
        {
            "columns": ["Server Name", "IP Address", "CPU Cores", "Created"],
            "column_types": {
                "Server Name": {"type": "string", "pattern": "server_name"},
                "IP Address": {"type": "ip_address", "format": "ipv4"},
                "CPU Cores": {"type": "integer", "min": 4, "max": 16},
                "Created": {"type": "date", "format": "YYYY-MM-DD"}
            }
        }
"""
import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from collections import Counter

logger = logging.getLogger(__name__)


class ColumnTypeInferencer:
    """
    Infers data types for table columns by analyzing sample values.
    
    Performs multi-pass analysis:
    1. Parse values to detect basic types
    2. Apply pattern matching for specialized types
    3. Calculate statistics and confidence scores
    """
    
    # Regex patterns for specialized types
    IP_ADDRESS_PATTERN = re.compile(
        r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}'
        r'(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
    )
    
    EMAIL_PATTERN = re.compile(
        r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    )
    
    URL_PATTERN = re.compile(
        r'^https?://[^\s]+$',
        re.IGNORECASE
    )
    
    # Common date formats to try
    DATE_FORMATS = [
        "%Y-%m-%d",           # 2024-01-15
        "%Y/%m/%d",           # 2024/01/15
        "%d-%m-%Y",           # 15-01-2024
        "%d/%m/%Y",           # 15/01/2024
        "%m-%d-%Y",           # 01-15-2024
        "%m/%d/%Y",           # 01/15/2024
        "%Y%m%d",             # 20240115
        "%d.%m.%Y",           # 15.01.2024
        "%Y-%m-%d %H:%M:%S",  # 2024-01-15 14:30:00
        "%Y-%m-%dT%H:%M:%S",  # 2024-01-15T14:30:00 (ISO)
        "%d %b %Y",           # 15 Jan 2024
        "%d %B %Y",           # 15 January 2024
        "%b %d, %Y",          # Jan 15, 2024
    ]
    
    # Boolean value mappings
    BOOLEAN_TRUE = {"true", "yes", "y", "1", "on", "enabled", "active"}
    BOOLEAN_FALSE = {"false", "no", "n", "0", "off", "disabled", "inactive"}
    
    def __init__(self, sample_size: int = 100, min_confidence: float = 0.7):
        """
        Initialize inferencer.
        
        Args:
            sample_size: Maximum number of values to analyze per column
            min_confidence: Minimum confidence threshold for type assignment
        """
        self.sample_size = sample_size
        self.min_confidence = min_confidence
    
    def infer_column_types(
        self,
        headers: List[str],
        rows: List[List[Any]],
        include_stats: bool = True
    ) -> Dict[str, Dict[str, Any]]:
        """
        Infer types for all columns in a table.
        
        Args:
            headers: Column names
            rows: Data rows (list of lists)
            include_stats: Whether to include statistical metadata
        
        Returns:
            Dict mapping column name to type metadata
        """
        if not headers or not rows:
            return {}
        
        column_types = {}
        
        for col_idx, col_name in enumerate(headers):
            # Extract column values
            values = []
            for row in rows[:self.sample_size]:
                if col_idx < len(row):
                    val = row[col_idx]
                    if val is not None and str(val).strip():
                        values.append(val)
            
            if not values:
                column_types[col_name] = {
                    "type": "unknown",
                    "confidence": 0.0,
                    "null_count": len(rows)
                }
                continue
            
            # Infer type for this column
            type_info = self._infer_single_column_type(col_name, values, include_stats)
            column_types[col_name] = type_info
        
        return column_types
    
    def _infer_single_column_type(
        self,
        col_name: str,
        values: List[Any],
        include_stats: bool
    ) -> Dict[str, Any]:
        """Infer type for a single column."""
        # Try type detection in order of specificity
        type_detectors = [
            self._detect_boolean,
            self._detect_ip_address,
            self._detect_email,
            self._detect_url,
            self._detect_date,
            self._detect_integer,
            self._detect_float,
            self._detect_string,
        ]
        
        for detector in type_detectors:
            result = detector(col_name, values, include_stats)
            if result and result.get("confidence", 0.0) >= self.min_confidence:
                return result
        
        # Fallback to string
        return {
            "type": "string",
            "confidence": 1.0,
            "sample_values": values[:3] if len(values) <= 3 else values[:3] + ["..."],
        }
    
    def _detect_boolean(
        self,
        col_name: str,
        values: List[Any],
        include_stats: bool
    ) -> Optional[Dict[str, Any]]:
        """Detect boolean columns."""
        boolean_count = 0
        true_count = 0
        false_count = 0
        
        for val in values:
            val_str = str(val).strip().lower()
            if val_str in self.BOOLEAN_TRUE:
                boolean_count += 1
                true_count += 1
            elif val_str in self.BOOLEAN_FALSE:
                boolean_count += 1
                false_count += 1
        
        confidence = boolean_count / len(values) if values else 0.0
        
        if confidence >= self.min_confidence:
            result = {
                "type": "boolean",
                "confidence": confidence,
            }
            if include_stats:
                result.update({
                    "true_count": true_count,
                    "false_count": false_count,
                })
            return result
        
        return None
    
    def _detect_ip_address(
        self,
        col_name: str,
        values: List[Any],
        include_stats: bool
    ) -> Optional[Dict[str, Any]]:
        """Detect IP address columns."""
        ip_count = 0
        
        for val in values:
            val_str = str(val).strip()
            if self.IP_ADDRESS_PATTERN.match(val_str):
                ip_count += 1
        
        confidence = ip_count / len(values) if values else 0.0
        
        if confidence >= self.min_confidence:
            # Check column name for IP indicators
            name_lower = col_name.lower()
            if any(keyword in name_lower for keyword in ["ip", "address", "addr"]):
                confidence = min(confidence + 0.1, 1.0)
            
            return {
                "type": "ip_address",
                "format": "ipv4",
                "confidence": confidence,
            }
        
        return None
    
    def _detect_email(
        self,
        col_name: str,
        values: List[Any],
        include_stats: bool
    ) -> Optional[Dict[str, Any]]:
        """Detect email columns."""
        email_count = 0
        
        for val in values:
            val_str = str(val).strip()
            if self.EMAIL_PATTERN.match(val_str):
                email_count += 1
        
        confidence = email_count / len(values) if values else 0.0
        
        if confidence >= self.min_confidence:
            return {
                "type": "email",
                "confidence": confidence,
            }
        
        return None
    
    def _detect_url(
        self,
        col_name: str,
        values: List[Any],
        include_stats: bool
    ) -> Optional[Dict[str, Any]]:
        """Detect URL columns."""
        url_count = 0
        
        for val in values:
            val_str = str(val).strip()
            if self.URL_PATTERN.match(val_str):
                url_count += 1
        
        confidence = url_count / len(values) if values else 0.0
        
        if confidence >= self.min_confidence:
            return {
                "type": "url",
                "confidence": confidence,
            }
        
        return None
    
    def _detect_date(
        self,
        col_name: str,
        values: List[Any],
        include_stats: bool
    ) -> Optional[Dict[str, Any]]:
        """Detect date/datetime columns."""
        date_count = 0
        detected_format = None
        
        for val in values:
            val_str = str(val).strip()
            for date_format in self.DATE_FORMATS:
                try:
                    datetime.strptime(val_str, date_format)
                    date_count += 1
                    if detected_format is None:
                        detected_format = date_format
                    break
                except (ValueError, TypeError):
                    continue
        
        confidence = date_count / len(values) if values else 0.0
        
        if confidence >= self.min_confidence:
            # Check column name for date indicators
            name_lower = col_name.lower()
            if any(keyword in name_lower for keyword in ["date", "time", "created", "updated", "modified", "timestamp"]):
                confidence = min(confidence + 0.1, 1.0)
            
            result = {
                "type": "datetime" if "T" in (detected_format or "") or "H:M" in (detected_format or "") else "date",
                "confidence": confidence,
            }
            if detected_format:
                result["format"] = detected_format
            return result
        
        return None
    
    def _detect_integer(
        self,
        col_name: str,
        values: List[Any],
        include_stats: bool
    ) -> Optional[Dict[str, Any]]:
        """Detect integer columns."""
        int_count = 0
        int_values = []
        
        for val in values:
            val_str = str(val).strip()
            try:
                # Check if it's an integer (not a float)
                if '.' not in val_str:
                    int_val = int(val_str)
                    int_count += 1
                    int_values.append(int_val)
            except (ValueError, TypeError):
                continue
        
        confidence = int_count / len(values) if values else 0.0
        
        if confidence >= self.min_confidence:
            result = {
                "type": "integer",
                "confidence": confidence,
            }
            if include_stats and int_values:
                result.update({
                    "min": min(int_values),
                    "max": max(int_values),
                    "avg": sum(int_values) / len(int_values),
                })
            return result
        
        return None
    
    def _detect_float(
        self,
        col_name: str,
        values: List[Any],
        include_stats: bool
    ) -> Optional[Dict[str, Any]]:
        """Detect float/decimal columns."""
        float_count = 0
        float_values = []
        
        for val in values:
            val_str = str(val).strip()
            try:
                float_val = float(val_str)
                float_count += 1
                float_values.append(float_val)
            except (ValueError, TypeError):
                continue
        
        confidence = float_count / len(values) if values else 0.0
        
        if confidence >= self.min_confidence:
            result = {
                "type": "float",
                "confidence": confidence,
            }
            if include_stats and float_values:
                result.update({
                    "min": min(float_values),
                    "max": max(float_values),
                    "avg": sum(float_values) / len(float_values),
                })
            return result
        
        return None
    
    def _detect_string(
        self,
        col_name: str,
        values: List[Any],
        include_stats: bool
    ) -> Dict[str, Any]:
        """Detect string columns (fallback)."""
        str_values = [str(v).strip() for v in values]
        
        # Detect common patterns
        pattern = None
        name_lower = col_name.lower()
        
        if any(keyword in name_lower for keyword in ["name", "server", "host", "hostname"]):
            pattern = "identifier"
        elif any(keyword in name_lower for keyword in ["desc", "description", "comment", "note"]):
            pattern = "text"
        elif any(keyword in name_lower for keyword in ["status", "state"]):
            pattern = "categorical"
        
        result = {
            "type": "string",
            "confidence": 1.0,
        }
        
        if pattern:
            result["pattern"] = pattern
        
        if include_stats:
            # Calculate uniqueness
            unique_count = len(set(str_values))
            result["unique_count"] = unique_count
            result["uniqueness_ratio"] = unique_count / len(str_values) if str_values else 0.0
            
            # Calculate average length
            avg_length = sum(len(s) for s in str_values) / len(str_values) if str_values else 0.0
            result["avg_length"] = round(avg_length, 1)
            
            # Sample values
            result["sample_values"] = str_values[:3] if len(str_values) <= 3 else str_values[:3] + ["..."]
        
        return result


def infer_column_types(
    headers: List[str],
    rows: List[List[Any]],
    sample_size: int = 100,
    min_confidence: float = 0.7,
    include_stats: bool = True
) -> Dict[str, Dict[str, Any]]:
    """
    Convenience function to infer column types.
    
    Args:
        headers: Column names
        rows: Data rows
        sample_size: Max rows to analyze
        min_confidence: Minimum confidence threshold
        include_stats: Include statistical metadata
    
    Returns:
        Dict mapping column name to type metadata
    """
    inferencer = ColumnTypeInferencer(sample_size=sample_size, min_confidence=min_confidence)
    return inferencer.infer_column_types(headers, rows, include_stats=include_stats)
