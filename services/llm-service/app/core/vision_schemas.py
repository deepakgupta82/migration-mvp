"""Vision JSON Schemas and validation helpers.

Provides strict (but permissive-enough) schemas for table and diagram
multimodal extraction outputs. These are intentionally minimal so we
can evolve without breaking early clients.
"""
from __future__ import annotations
from typing import Any, Dict
from jsonschema import validate, ValidationError

TABLE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "tables": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "caption": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                    "columns": {"type": "array", "items": {"type": "string"}},
                    "rows": {
                        "type": "array",
                        "items": {
                            "type": "array",
                            "items": {"anyOf": [{"type": "string"}, {"type": "number"}, {"type": "null"}]},
                        },
                    },
                },
                "required": ["columns", "rows"],
                "additionalProperties": True,
            },
        }
    },
    "required": ["tables"],
    "additionalProperties": True,
}

DIAGRAM_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "type": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                },
                "required": ["name"],
                "additionalProperties": True,
            },
        },
        "relationships": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source": {"type": "string"},
                    "type": {"type": "string"},
                    "target": {"type": "string"},
                },
                "required": ["source", "type", "target"],
                "additionalProperties": True,
            },
        },
    },
    "required": ["entities", "relationships"],
    "additionalProperties": True,
}


def is_valid_table_payload(data: Dict[str, Any]) -> bool:
    try:
        validate(data, TABLE_SCHEMA)
        return True
    except ValidationError:
        return False


def is_valid_diagram_payload(data: Dict[str, Any]) -> bool:
    try:
        validate(data, DIAGRAM_SCHEMA)
        return True
    except ValidationError:
        return False
