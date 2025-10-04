#!/usr/bin/env python3
"""
Pattern-Based Extractors
Specialized extractors for deterministic pattern matching

This module provides:
- Regex-based extraction for common patterns (IPs, emails, URLs, dates, etc.)
- Table column mapping for structured spreadsheet data
- Format-specific extractors
"""

import logging
import re
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger("pattern_extractors")


@dataclass
class PatternMatch:
    """A pattern match result"""
    pattern_type: str
    value: str
    confidence: float
    start_pos: int
    end_pos: int
    context: Optional[str] = None


class RegexPatternExtractor:
    """
    Extract entities using regex patterns
    
    Handles:
    - IP addresses (IPv4)
    - Email addresses
    - URLs
    - Phone numbers
    - Dates (various formats)
    - UUIDs
    - Version numbers
    - File paths
    """
    
    # Pattern definitions
    PATTERNS = {
        "ipv4": {
            "regex": r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b',
            "confidence": 0.95,
            "validator": lambda x: all(0 <= int(octet) <= 255 for octet in x.split('.'))
        },
        "email": {
            "regex": r'\b([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})\b',
            "confidence": 0.95
        },
        "url": {
            "regex": r'https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&/=]*)',
            "confidence": 0.98
        },
        "phone_us": {
            "regex": r'\b(\d{3}[-.]?\d{3}[-.]?\d{4})\b',
            "confidence": 0.85
        },
        "date_iso": {
            "regex": r'\b(\d{4}-\d{2}-\d{2})\b',
            "confidence": 0.90
        },
        "date_us": {
            "regex": r'\b(\d{1,2}/\d{1,2}/\d{2,4})\b',
            "confidence": 0.85
        },
        "uuid": {
            "regex": r'\b([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})\b',
            "confidence": 0.98
        },
        "version": {
            "regex": r'\bv?(\d+\.\d+(?:\.\d+)?(?:\.\d+)?)\b',
            "confidence": 0.80
        },
        "mac_address": {
            "regex": r'\b([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})\b',
            "confidence": 0.95
        },
        "port": {
            "regex": r':(\d{1,5})\b',
            "confidence": 0.75,
            "validator": lambda x: 1 <= int(x) <= 65535
        },
        "file_path_unix": {
            "regex": r'(/[a-zA-Z0-9_./\-]+)',
            "confidence": 0.70
        },
        "file_path_windows": {
            "regex": r'([A-Z]:\\[a-zA-Z0-9_\\\.\-\s]+)',
            "confidence": 0.75
        }
    }
    
    def __init__(self):
        self.compiled_patterns = {
            name: re.compile(info["regex"], re.IGNORECASE)
            for name, info in self.PATTERNS.items()
        }
        logger.info(f"Regex Pattern Extractor initialized with {len(self.PATTERNS)} patterns")
    
    def extract_all_patterns(
        self,
        content: str,
        pattern_types: Optional[List[str]] = None
    ) -> Dict[str, List[PatternMatch]]:
        """
        Extract all patterns from content
        
        Args:
            content: Text content to extract from
            pattern_types: List of specific patterns to extract (None = all)
            
        Returns:
            Dictionary mapping pattern type to matches
        """
        if pattern_types is None:
            pattern_types = list(self.PATTERNS.keys())
        
        results = {}
        
        for pattern_type in pattern_types:
            if pattern_type not in self.PATTERNS:
                logger.warning(f"Unknown pattern type: {pattern_type}")
                continue
            
            matches = self.extract_pattern(content, pattern_type)
            if matches:
                results[pattern_type] = matches
        
        total_matches = sum(len(matches) for matches in results.values())
        logger.info(
            f"Pattern extraction complete | "
            f"patterns={len(results)} "
            f"total_matches={total_matches}"
        )
        
        return results
    
    def extract_pattern(
        self,
        content: str,
        pattern_type: str
    ) -> List[PatternMatch]:
        """Extract specific pattern type"""
        if pattern_type not in self.PATTERNS:
            return []
        
        pattern_info = self.PATTERNS[pattern_type]
        compiled_pattern = self.compiled_patterns[pattern_type]
        
        matches = []
        
        for match in compiled_pattern.finditer(content):
            value = match.group(1) if match.groups() else match.group(0)
            
            # Validate if validator exists
            if "validator" in pattern_info:
                try:
                    if not pattern_info["validator"](value):
                        continue
                except Exception:
                    continue
            
            # Extract context (20 chars before and after)
            start = max(0, match.start() - 20)
            end = min(len(content), match.end() + 20)
            context = content[start:end]
            
            pattern_match = PatternMatch(
                pattern_type=pattern_type,
                value=value,
                confidence=pattern_info["confidence"],
                start_pos=match.start(),
                end_pos=match.end(),
                context=context
            )
            matches.append(pattern_match)
        
        return matches
    
    def extract_infrastructure_patterns(
        self,
        content: str
    ) -> Dict[str, List[PatternMatch]]:
        """Extract patterns relevant to infrastructure documents"""
        return self.extract_all_patterns(
            content,
            pattern_types=["ipv4", "mac_address", "port", "url", "file_path_unix", "file_path_windows"]
        )
    
    def extract_contact_patterns(
        self,
        content: str
    ) -> Dict[str, List[PatternMatch]]:
        """Extract patterns relevant to contact/people documents"""
        return self.extract_all_patterns(
            content,
            pattern_types=["email", "phone_us"]
        )


class TableColumnMapper:
    """
    Map table columns to entity attributes
    
    Handles:
    - Spreadsheet-style tables
    - Column header detection
    - Row-to-entity mapping
    - Data type inference
    """
    
    # Common column name mappings
    COLUMN_MAPPINGS = {
        # Infrastructure
        "server": ["server", "hostname", "host", "server_name", "servername"],
        "ip_address": ["ip", "ip address", "ipaddress", "ip_address", "ip addr"],
        "os": ["os", "operating system", "operating_system", "platform"],
        "environment": ["env", "environment", "environ"],
        "location": ["location", "loc", "datacenter", "dc", "site"],
        
        # People
        "name": ["name", "full name", "fullname", "employee name", "person"],
        "email": ["email", "e-mail", "email address", "email_address"],
        "phone": ["phone", "telephone", "phone number", "phone_number", "tel"],
        "department": ["dept", "department", "division", "org"],
        "role": ["role", "title", "job title", "position"],
        
        # Application
        "application": ["app", "application", "app name", "app_name", "service"],
        "version": ["ver", "version", "app version", "release"],
        "port": ["port", "port number", "service_port"],
        
        # General
        "id": ["id", "identifier", "uid", "unique_id"],
        "description": ["desc", "description", "details", "notes"],
        "status": ["status", "state", "condition"]
    }
    
    def __init__(self):
        logger.info("Table Column Mapper initialized")
    
    def map_table_to_entities(
        self,
        table_data: List[Dict[str, Any]],
        entity_type: str
    ) -> List[Dict[str, Any]]:
        """
        Map table rows to entities
        
        Args:
            table_data: List of row dictionaries (from table extraction)
            entity_type: Target entity type
            
        Returns:
            List of entity dictionaries
        """
        if not table_data:
            return []
        
        # Get column mapping
        column_map = self._build_column_mapping(list(table_data[0].keys()))
        
        entities = []
        
        for row in table_data:
            entity = {
                "entity_type": entity_type,
                "attributes": {},
                "confidence": 0.85,
                "extraction_strategy": "table_mapping"
            }
            
            # Map columns to attributes
            for original_col, mapped_attr in column_map.items():
                value = row.get(original_col)
                if value and str(value).strip():
                    entity["attributes"][mapped_attr] = value
            
            # Only add if has attributes
            if entity["attributes"]:
                entities.append(entity)
        
        logger.info(
            f"Mapped {len(entities)} entities from table | "
            f"entity_type={entity_type}"
        )
        
        return entities
    
    def _build_column_mapping(
        self,
        column_names: List[str]
    ) -> Dict[str, str]:
        """Build mapping from actual columns to standard attributes"""
        mapping = {}
        
        for col in column_names:
            col_lower = col.lower().strip()
            
            # Try to find matching attribute
            for attr, variants in self.COLUMN_MAPPINGS.items():
                if col_lower in variants:
                    mapping[col] = attr
                    break
            else:
                # No match - use original column name
                mapping[col] = col.lower().replace(" ", "_")
        
        return mapping
    
    def infer_entity_type_from_columns(
        self,
        column_names: List[str]
    ) -> str:
        """Infer likely entity type from column names"""
        col_set = set(c.lower().strip() for c in column_names)
        
        # Infrastructure indicators
        infra_keywords = {"server", "hostname", "ip", "ip address", "os", "datacenter"}
        if col_set & infra_keywords:
            return "Server"
        
        # People indicators
        people_keywords = {"name", "email", "phone", "employee", "department"}
        if col_set & people_keywords:
            return "Person"
        
        # Application indicators
        app_keywords = {"application", "app", "service", "version", "port"}
        if col_set & app_keywords:
            return "Application"
        
        # Default
        return "Entity"


class DateExtractor:
    """Extract and normalize dates from text"""
    
    DATE_FORMATS = [
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%Y/%m/%d",
        "%B %d, %Y",
        "%d %B %Y",
        "%b %d, %Y",
        "%d %b %Y"
    ]
    
    def __init__(self):
        logger.info("Date Extractor initialized")
    
    def extract_dates(
        self,
        content: str
    ) -> List[Tuple[str, datetime]]:
        """Extract and parse dates from content"""
        regex_extractor = RegexPatternExtractor()
        
        # Extract date patterns
        iso_dates = regex_extractor.extract_pattern(content, "date_iso")
        us_dates = regex_extractor.extract_pattern(content, "date_us")
        
        parsed_dates = []
        
        # Parse ISO dates
        for match in iso_dates:
            try:
                dt = datetime.strptime(match.value, "%Y-%m-%d")
                parsed_dates.append((match.value, dt))
            except ValueError:
                pass
        
        # Parse US dates
        for match in us_dates:
            for fmt in ["%m/%d/%Y", "%m/%d/%y"]:
                try:
                    dt = datetime.strptime(match.value, fmt)
                    parsed_dates.append((match.value, dt))
                    break
                except ValueError:
                    continue
        
        return parsed_dates
