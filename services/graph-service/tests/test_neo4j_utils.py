"""
Tests for Neo4j utility functions

Verifies that property serialization and deserialization work correctly
for handling nested objects in Neo4j storage.
"""

import json
import pytest
from app.shared.neo4j_utils import (
    prepare_properties_for_neo4j,
    restore_properties_from_neo4j,
    prepare_relationship_properties,
    sanitize_property_value,
    _is_primitive_list
)


class TestPreparePropertiesForNeo4j:
    """Test suite for prepare_properties_for_neo4j function"""
    
    def test_simple_primitives(self):
        """Test that simple primitive properties pass through unchanged"""
        props = {
            "name": "server1",
            "port": 8080,
            "active": True,
            "cpu_cores": 4.5,
            "description": None
        }
        result = prepare_properties_for_neo4j(props)
        
        assert result["name"] == "server1"
        assert result["port"] == 8080
        assert result["active"] is True
        assert result["cpu_cores"] == 4.5
        assert result["description"] is None
    
    def test_validation_info_flattening(self):
        """Test that validation_info is properly flattened and serialized"""
        props = {
            "name": "test",
            "validation_info": {
                "is_valid": True,
                "confidence_score": 0.85,
                "warnings": ["OS not specified", "Location missing"],
                "errors": []
            }
        }
        result = prepare_properties_for_neo4j(props)
        
        # Check flattened fields
        assert result["validation_is_valid"] is True
        assert result["validation_confidence"] == 0.85
        assert result["validation_warnings"] == ["OS not specified", "Location missing"]
        assert result["validation_errors"] == []
        
        # Check JSON preservation
        assert "validation_info_json" in result
        restored = json.loads(result["validation_info_json"])
        assert restored["is_valid"] is True
        assert restored["confidence_score"] == 0.85
    
    def test_attributes_flattening(self):
        """Test that attributes are properly flattened and serialized"""
        props = {
            "attributes": {
                "ip_address": "10.0.0.1",
                "os": "Windows Server 2016",
                "cpu_count": 4,
                "nested_config": {
                    "ram": 16,
                    "disk": "SSD"
                }
            }
        }
        result = prepare_properties_for_neo4j(props)
        
        # Check flattened primitive fields
        assert result["attr_ip_address"] == "10.0.0.1"
        assert result["attr_os"] == "Windows Server 2016"
        assert result["attr_cpu_count"] == 4
        
        # Check JSON preservation (includes nested config)
        assert "attributes_json" in result
        restored = json.loads(result["attributes_json"])
        assert restored["ip_address"] == "10.0.0.1"
        assert restored["nested_config"]["ram"] == 16
    
    def test_nested_dict_serialization(self):
        """Test that arbitrary nested dicts are serialized to JSON"""
        props = {
            "name": "test",
            "config": {
                "database": {
                    "host": "localhost",
                    "port": 5432,
                    "credentials": {
                        "user": "admin",
                        "encrypted": True
                    }
                }
            }
        }
        result = prepare_properties_for_neo4j(props)
        
        assert result["name"] == "test"
        assert "config_json" in result
        
        restored = json.loads(result["config_json"])
        assert restored["database"]["host"] == "localhost"
        assert restored["database"]["credentials"]["user"] == "admin"
    
    def test_primitive_list(self):
        """Test that lists of primitives pass through"""
        props = {
            "tags": ["production", "critical", "database"],
            "ports": [80, 443, 8080],
            "flags": [True, False, True]
        }
        result = prepare_properties_for_neo4j(props)
        
        assert result["tags"] == ["production", "critical", "database"]
        assert result["ports"] == [80, 443, 8080]
        assert result["flags"] == [True, False, True]
    
    def test_complex_list_serialization(self):
        """Test that lists containing dicts are serialized to JSON"""
        props = {
            "servers": [
                {"name": "srv1", "ip": "10.0.0.1"},
                {"name": "srv2", "ip": "10.0.0.2"}
            ]
        }
        result = prepare_properties_for_neo4j(props)
        
        assert "servers_json" in result
        restored = json.loads(result["servers_json"])
        assert len(restored) == 2
        assert restored[0]["name"] == "srv1"
    
    def test_real_world_entity_properties(self):
        """Test with real-world entity properties similar to our actual data"""
        props = {
            "ip_address": "10.1.134.25",
            "device_type": "VIRTUAL",
            "make": "Vmware",
            "model": "Vmware",
            "validation_info": {
                "errors": [],
                "is_valid": True,
                "confidence_score": 0.6,
                "warnings": [
                    "Operating system not specified",
                    "Location not specified",
                    "Domain not specified"
                ]
            },
            "attributes": {
                "os": "Windows Server 2016 Standard",
                "location": "UAQ DC",
                "domain": "nbq.ae"
            }
        }
        result = prepare_properties_for_neo4j(props)
        
        # Check primitives pass through
        assert result["ip_address"] == "10.1.134.25"
        assert result["device_type"] == "VIRTUAL"
        
        # Check validation_info flattening
        assert result["validation_is_valid"] is True
        assert result["validation_confidence"] == 0.6
        assert len(result["validation_warnings"]) == 3
        
        # Check attributes flattening
        assert result["attr_os"] == "Windows Server 2016 Standard"
        assert result["attr_location"] == "UAQ DC"
        
        # Check JSON preservation
        assert "validation_info_json" in result
        assert "attributes_json" in result
        
        # Verify no nested objects remain
        for key, value in result.items():
            assert not isinstance(value, dict), f"Found nested dict at key '{key}'"
            if isinstance(value, list):
                assert _is_primitive_list(value), f"Found complex list at key '{key}'"


class TestRestorePropertiesFromNeo4j:
    """Test suite for restore_properties_from_neo4j function"""
    
    def test_restore_validation_info(self):
        """Test restoring validation_info from flattened format"""
        neo4j_props = {
            "name": "server1",
            "validation_is_valid": True,
            "validation_confidence": 0.85,
            "validation_warnings": ["warning1", "warning2"],
            "validation_info_json": json.dumps({
                "is_valid": True,
                "confidence_score": 0.85,
                "warnings": ["warning1", "warning2"],
                "errors": []
            })
        }
        result = restore_properties_from_neo4j(neo4j_props)
        
        assert result["name"] == "server1"
        assert "validation_info" in result
        assert result["validation_info"]["is_valid"] is True
        assert result["validation_info"]["confidence_score"] == 0.85
        
        # Flattened fields should be removed
        assert "validation_is_valid" not in result
        assert "validation_confidence" not in result
    
    def test_restore_attributes(self):
        """Test restoring attributes from flattened format"""
        neo4j_props = {
            "name": "server1",
            "attr_ip_address": "10.0.0.1",
            "attr_os": "Linux",
            "attributes_json": json.dumps({
                "ip_address": "10.0.0.1",
                "os": "Linux",
                "nested": {"cpu": 4}
            })
        }
        result = restore_properties_from_neo4j(neo4j_props)
        
        assert result["name"] == "server1"
        assert "attributes" in result
        assert result["attributes"]["ip_address"] == "10.0.0.1"
        assert result["attributes"]["nested"]["cpu"] == 4
        
        # Flattened fields should be removed
        assert "attr_ip_address" not in result
        assert "attr_os" not in result
    
    def test_roundtrip_conversion(self):
        """Test that prepare -> restore is lossless"""
        original = {
            "name": "test_server",
            "port": 8080,
            "active": True,
            "tags": ["prod", "critical"],
            "validation_info": {
                "is_valid": True,
                "confidence_score": 0.9,
                "warnings": ["minor issue"],
                "errors": []
            },
            "attributes": {
                "ip": "10.0.0.1",
                "nested": {
                    "cpu": 4,
                    "ram": 16
                }
            },
            "config": {
                "setting1": "value1",
                "setting2": 42
            }
        }
        
        # Prepare for Neo4j
        neo4j_props = prepare_properties_for_neo4j(original)
        
        # Restore from Neo4j
        restored = restore_properties_from_neo4j(neo4j_props)
        
        # Check critical fields are preserved
        assert restored["name"] == original["name"]
        assert restored["port"] == original["port"]
        assert restored["active"] == original["active"]
        assert restored["tags"] == original["tags"]
        assert restored["validation_info"]["is_valid"] == original["validation_info"]["is_valid"]
        assert restored["attributes"]["ip"] == original["attributes"]["ip"]
        assert restored["attributes"]["nested"]["cpu"] == original["attributes"]["nested"]["cpu"]
        assert restored["config"]["setting1"] == original["config"]["setting1"]


class TestHelperFunctions:
    """Test suite for helper functions"""
    
    def test_is_primitive_list(self):
        """Test _is_primitive_list function"""
        assert _is_primitive_list([]) is True
        assert _is_primitive_list(["a", "b", "c"]) is True
        assert _is_primitive_list([1, 2, 3]) is True
        assert _is_primitive_list([True, False]) is True
        assert _is_primitive_list([None, "test"]) is True
        assert _is_primitive_list([1.5, 2.5]) is True
        
        # Complex lists should return False
        assert _is_primitive_list([{"key": "value"}]) is False
        assert _is_primitive_list([["nested"]]) is False
        assert _is_primitive_list([1, {"key": "value"}]) is False
    
    def test_sanitize_property_value(self):
        """Test sanitize_property_value function"""
        # Primitives pass through
        assert sanitize_property_value("test") == "test"
        assert sanitize_property_value(42) == 42
        assert sanitize_property_value(True) is True
        assert sanitize_property_value(None) is None
        
        # Dicts are serialized
        result = sanitize_property_value({"key": "value"})
        assert isinstance(result, str)
        assert json.loads(result) == {"key": "value"}
        
        # Complex lists are serialized
        result = sanitize_property_value([{"a": 1}])
        assert isinstance(result, str)
        assert json.loads(result) == [{"a": 1}]
        
        # Primitive lists pass through
        assert sanitize_property_value([1, 2, 3]) == [1, 2, 3]
    
    def test_prepare_relationship_properties(self):
        """Test prepare_relationship_properties function"""
        props = {
            "type": "CONNECTS_TO",
            "confidence": 0.95,
            "metadata": {
                "source": "llm_extraction",
                "timestamp": "2025-10-04"
            }
        }
        result = prepare_relationship_properties(props)
        
        # Should have serialized the nested metadata
        assert result["type"] == "CONNECTS_TO"
        assert result["confidence"] == 0.95
        assert "metadata_json" in result
        
        restored = json.loads(result["metadata_json"])
        assert restored["source"] == "llm_extraction"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
