"""
Server Entity Validator (Issue #6)

Validates server entities extracted from infrastructure inventories.
Ensures required properties are present and well-formed.

Required server properties:
- name: Server hostname or identifier
- os: Operating system (Windows, Linux, Unix, AIX, etc.)
- ip: IP address (IPv4 or IPv6)
- location: Physical or logical location
- domain: Network domain or environment

Example usage:
    validator = ServerEntityValidator()
    is_valid, errors = validator.validate_server(entity)
    if is_valid:
        enriched = validator.enrich_server(entity)
"""
import logging
import re
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ServerValidationResult:
    """Result of server entity validation."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    enriched_properties: Dict[str, Any]
    confidence_score: float


class ServerEntityValidator:
    """
    Validates and enriches server entities from infrastructure inventories.
    
    Validation rules:
    1. Required fields: name, os, ip, location
    2. IP address format validation
    3. OS normalization (Windows Server 2019 → Windows)
    4. Location inference (prod-web-01 → Production)
    5. Domain inference from hostname
    """
    
    # OS patterns and normalization
    OS_PATTERNS = {
        'windows': r'(?i)windows|win\s*server|win\d+|microsoft',
        'linux': r'(?i)linux|ubuntu|debian|centos|rhel|red\s*hat|fedora|suse',
        'unix': r'(?i)unix|solaris|hp-ux|aix',
        'macos': r'(?i)mac\s*os|darwin|osx',
        'other': r'(?i)other|unknown|n/a'
    }
    
    # Environment patterns
    ENV_PATTERNS = {
        'production': r'(?i)prod|prd|p-|production|live',
        'development': r'(?i)dev|d-|development|sandbox',
        'staging': r'(?i)stag|stg|s-|staging|uat|preprod',
        'testing': r'(?i)test|tst|t-|qa|quality'
    }
    
    # IP address patterns
    IPV4_PATTERN = r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
    IPV6_PATTERN = r'^(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$|^::(?:[0-9a-fA-F]{1,4}:){0,6}[0-9a-fA-F]{1,4}$'
    
    def __init__(self, strict_mode: bool = False):
        """
        Initialize validator.
        
        Args:
            strict_mode: If True, reject entities with missing required fields
        """
        self.strict_mode = strict_mode
        self.ipv4_regex = re.compile(self.IPV4_PATTERN)
        self.ipv6_regex = re.compile(self.IPV6_PATTERN)
    
    def validate_server(self, entity: Dict[str, Any]) -> ServerValidationResult:
        """
        Validate a server entity.
        
        Args:
            entity: Entity dict with properties
        
        Returns:
            ServerValidationResult with validation details
        """
        errors = []
        warnings = []
        enriched_props = {}
        confidence = 1.0
        
        # Extract properties
        entity_type = entity.get('entity_type', entity.get('type', '')).lower()
        name = entity.get('name', '')
        attributes = entity.get('attributes', entity.get('properties', {}))
        
        # Check if this is a server entity
        if not self._is_server_entity(entity_type, name, attributes):
            return ServerValidationResult(
                is_valid=False,
                errors=['Not a server entity'],
                warnings=[],
                enriched_properties={},
                confidence_score=0.0
            )
        
        # Validate name
        if not name or not isinstance(name, str) or not name.strip():
            errors.append('Server name is required')
            confidence -= 0.3
        else:
            enriched_props['name'] = name.strip()
        
        # Validate and normalize OS
        os_value = attributes.get('os', attributes.get('operating_system', ''))
        if not os_value or str(os_value).strip().lower() in ('', 'n/a', 'unknown', 'none'):
            if self.strict_mode:
                errors.append('Operating system is required')
            else:
                warnings.append('Operating system not specified')
            confidence -= 0.2
        else:
            normalized_os = self._normalize_os(str(os_value))
            enriched_props['os'] = normalized_os
            enriched_props['os_raw'] = str(os_value).strip()
        
        # Validate IP address
        ip_value = attributes.get('ip', attributes.get('ip_address', attributes.get('ipaddress', '')))
        if not ip_value or str(ip_value).strip().lower() in ('', 'n/a', 'unknown', 'none'):
            if self.strict_mode:
                errors.append('IP address is required')
            else:
                warnings.append('IP address not specified')
            confidence -= 0.2
        else:
            ip_str = str(ip_value).strip()
            is_valid_ip, ip_type = self._validate_ip(ip_str)
            if is_valid_ip:
                enriched_props['ip'] = ip_str
                enriched_props['ip_type'] = ip_type
            else:
                warnings.append(f'Invalid IP address format: {ip_str}')
                enriched_props['ip'] = ip_str  # Keep original
                confidence -= 0.1
        
        # Validate location
        location = attributes.get('location', attributes.get('datacenter', attributes.get('site', '')))
        if not location or str(location).strip().lower() in ('', 'n/a', 'unknown', 'none'):
            # Try to infer from name
            inferred_location = self._infer_location_from_name(name)
            if inferred_location:
                enriched_props['location'] = inferred_location
                enriched_props['location_inferred'] = True
                warnings.append(f'Location inferred from hostname: {inferred_location}')
            else:
                if self.strict_mode:
                    errors.append('Location is required')
                else:
                    warnings.append('Location not specified')
                confidence -= 0.15
        else:
            enriched_props['location'] = str(location).strip()
        
        # Validate domain
        domain = attributes.get('domain', attributes.get('ad_domain', ''))
        if not domain or str(domain).strip().lower() in ('', 'n/a', 'unknown', 'none'):
            # Try to infer from name
            inferred_domain = self._infer_domain_from_name(name)
            if inferred_domain:
                enriched_props['domain'] = inferred_domain
                enriched_props['domain_inferred'] = True
            else:
                warnings.append('Domain not specified')
                confidence -= 0.05
        else:
            enriched_props['domain'] = str(domain).strip()
        
        # Enrich with environment
        environment = self._infer_environment(name, attributes)
        if environment:
            enriched_props['environment'] = environment
        
        # Enrich with server role
        role = self._infer_server_role(name, attributes)
        if role:
            enriched_props['role'] = role
        
        # Additional attributes (copy over)
        for key in ['hostname', 'cpu', 'memory', 'storage', 'status', 'version']:
            if key in attributes and attributes[key]:
                enriched_props[key] = attributes[key]
        
        # Determine validity
        is_valid = len(errors) == 0
        
        return ServerValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            enriched_properties=enriched_props,
            confidence_score=max(0.0, min(1.0, confidence))
        )
    
    def enrich_server(self, entity: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enrich server entity with validated and inferred properties.
        
        Args:
            entity: Original entity dict
        
        Returns:
            Enriched entity dict
        """
        result = self.validate_server(entity)
        
        # Update attributes with enriched properties
        if 'attributes' in entity:
            entity['attributes'].update(result.enriched_properties)
        elif 'properties' in entity:
            entity['properties'].update(result.enriched_properties)
        else:
            entity['attributes'] = result.enriched_properties
        
        # Add validation metadata
        entity['validation'] = {
            'is_valid': result.is_valid,
            'confidence_score': result.confidence_score,
            'errors': result.errors,
            'warnings': result.warnings
        }
        
        return entity
    
    def _is_server_entity(self, entity_type: str, name: str, attributes: Dict[str, Any]) -> bool:
        """Check if entity is a server."""
        # Type-based check
        server_types = {'server', 'host', 'machine', 'vm', 'virtualmachine', 'instance'}
        if any(t in entity_type for t in server_types):
            return True
        
        # Attribute-based check
        server_attributes = {'os', 'operating_system', 'ip', 'ip_address', 'hostname'}
        if any(attr in attributes for attr in server_attributes):
            return True
        
        # Name-based check (common server naming patterns)
        server_patterns = [r'server', r'host', r'-\d{2}$', r'vm-', r'srv-']
        name_lower = name.lower()
        if any(re.search(pattern, name_lower) for pattern in server_patterns):
            return True
        
        return False
    
    def _normalize_os(self, os_value: str) -> str:
        """Normalize OS string to standard categories."""
        os_lower = os_value.lower().strip()
        
        for os_type, pattern in self.OS_PATTERNS.items():
            if re.search(pattern, os_lower):
                return os_type.capitalize()
        
        # Return original if no match
        return os_value.strip()
    
    def _validate_ip(self, ip_str: str) -> Tuple[bool, Optional[str]]:
        """
        Validate IP address format.
        
        Returns:
            (is_valid, ip_type) where ip_type is 'ipv4', 'ipv6', or None
        """
        # Check IPv4
        if self.ipv4_regex.match(ip_str):
            return True, 'ipv4'
        
        # Check IPv6
        if self.ipv6_regex.match(ip_str):
            return True, 'ipv6'
        
        return False, None
    
    def _infer_location_from_name(self, name: str) -> Optional[str]:
        """Infer location from hostname patterns."""
        # Common patterns: nyc-web-01, lon-db-01, us-east-srv01
        location_patterns = {
            r'(?i)^nyc': 'New York',
            r'(?i)^lon': 'London',
            r'(?i)^par': 'Paris',
            r'(?i)^tok': 'Tokyo',
            r'(?i)^syd': 'Sydney',
            r'(?i)us-east': 'US East',
            r'(?i)us-west': 'US West',
            r'(?i)eu-west': 'EU West',
            r'(?i)ap-': 'Asia Pacific',
        }
        
        for pattern, location in location_patterns.items():
            if re.search(pattern, name):
                return location
        
        return None
    
    def _infer_domain_from_name(self, name: str) -> Optional[str]:
        """Infer domain from FQDN."""
        # Check if name contains dots (FQDN pattern)
        if '.' in name:
            parts = name.split('.')
            if len(parts) >= 2:
                return '.'.join(parts[1:])  # Everything after first part
        
        return None
    
    def _infer_environment(self, name: str, attributes: Dict[str, Any]) -> Optional[str]:
        """Infer environment from name or attributes."""
        # Check attributes first
        env_attr = attributes.get('environment', attributes.get('env', ''))
        if env_attr and str(env_attr).strip():
            return str(env_attr).strip()
        
        # Infer from name
        name_lower = name.lower()
        for env, pattern in self.ENV_PATTERNS.items():
            if re.search(pattern, name_lower):
                return env.capitalize()
        
        return None
    
    def _infer_server_role(self, name: str, attributes: Dict[str, Any]) -> Optional[str]:
        """Infer server role from name or attributes."""
        # Check attributes first
        role_attr = attributes.get('role', attributes.get('function', ''))
        if role_attr and str(role_attr).strip():
            return str(role_attr).strip()
        
        # Infer from name
        role_patterns = {
            'web': r'(?i)web|www|http|nginx|apache',
            'database': r'(?i)db|database|sql|mysql|postgres|oracle',
            'application': r'(?i)app|application|tomcat|jboss',
            'file': r'(?i)file|storage|nas|san',
            'mail': r'(?i)mail|smtp|exchange',
            'dns': r'(?i)dns|nameserver',
            'proxy': r'(?i)proxy|gateway|lb|loadbalancer',
        }
        
        name_lower = name.lower()
        for role, pattern in role_patterns.items():
            if re.search(pattern, name_lower):
                return role.capitalize()
        
        return None


def validate_server_entities(
    entities: List[Dict[str, Any]],
    strict_mode: bool = False
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Validate and enrich a list of server entities.
    
    Args:
        entities: List of entity dicts
        strict_mode: If True, reject entities with missing required fields
    
    Returns:
        Tuple of (enriched_entities, stats)
    """
    validator = ServerEntityValidator(strict_mode=strict_mode)
    
    enriched = []
    stats = {
        'total': len(entities),
        'servers_found': 0,
        'valid_servers': 0,
        'invalid_servers': 0,
        'total_errors': 0,
        'total_warnings': 0
    }
    
    for entity in entities:
        result = validator.validate_server(entity)
        
        # Check if this is a server
        if result.is_valid or (not result.is_valid and 'Not a server entity' not in result.errors):
            stats['servers_found'] += 1
            
            if result.is_valid:
                stats['valid_servers'] += 1
            else:
                stats['invalid_servers'] += 1
            
            stats['total_errors'] += len(result.errors)
            stats['total_warnings'] += len(result.warnings)
            
            # Enrich entity
            enriched_entity = validator.enrich_server(entity)
            enriched.append(enriched_entity)
        else:
            # Not a server, keep original
            enriched.append(entity)
    
    return enriched, stats
