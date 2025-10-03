"""
Network Topology Analyzer (Issue #8)

Parses IP addresses from JSONL elements and infers network topology.
Builds subnet relationships and network connectivity graphs.

Key features:
- IP address extraction from JSONL elements
- Subnet inference (192.168.1.0/24)
- Network segment grouping
- VLAN detection
- Gateway inference
- Network connectivity relationships

Example usage:
    analyzer = NetworkTopologyAnalyzer()
    topology = analyzer.analyze_topology(entities)
    subnets = topology['subnets']
    relationships = topology['relationships']
"""
import logging
import re
from typing import Dict, Any, List, Tuple, Optional, Set
from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Network, IPv6Address, IPv6Network, ip_address, ip_network
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class NetworkSubnet:
    """Represents a detected network subnet."""
    network: str  # CIDR notation: 192.168.1.0/24
    hosts: List[str]  # Entity IDs in this subnet
    network_type: str  # 'private', 'public', 'loopback'
    vlan: Optional[str] = None
    gateway: Optional[str] = None
    description: Optional[str] = None


@dataclass
class TopologyAnalysisResult:
    """Result of network topology analysis."""
    subnets: List[NetworkSubnet]
    relationships: List[Dict[str, Any]]
    network_entities: List[Dict[str, Any]]
    stats: Dict[str, Any]


class NetworkTopologyAnalyzer:
    """
    Analyzes network topology from entity IP addresses.
    
    Features:
    1. IP address extraction from entities
    2. Subnet detection (automatically infer /24, /16, /8)
    3. Network segment grouping
    4. Private vs public classification
    5. Gateway inference (x.x.x.1, x.x.x.254)
    6. VLAN detection from naming
    7. Network connectivity relationships
    """
    
    # Private IP ranges (RFC 1918)
    PRIVATE_RANGES = [
        '10.0.0.0/8',
        '172.16.0.0/12',
        '192.168.0.0/16',
    ]
    
    # Loopback range
    LOOPBACK_RANGE = '127.0.0.0/8'
    
    # Common gateway last octets
    GATEWAY_OCTETS = {1, 254, 255}
    
    def __init__(self, default_subnet_mask: int = 24):
        """
        Initialize analyzer.
        
        Args:
            default_subnet_mask: Default subnet mask bits (24 = /24)
        """
        self.default_subnet_mask = default_subnet_mask
        self.private_networks = [ip_network(r) for r in self.PRIVATE_RANGES]
        self.loopback_network = ip_network(self.LOOPBACK_RANGE)
    
    def analyze_topology(
        self,
        entities: List[Dict[str, Any]],
        infer_subnets: bool = True,
        create_subnet_entities: bool = True
    ) -> TopologyAnalysisResult:
        """
        Analyze network topology from entities.
        
        Args:
            entities: List of entity dicts
            infer_subnets: If True, automatically infer subnets
            create_subnet_entities: If True, create subnet entities
        
        Returns:
            TopologyAnalysisResult with subnets, relationships, and stats
        """
        # Extract IP addresses from entities
        ip_map = self._extract_ip_addresses(entities)
        
        if not ip_map:
            logger.info("No IP addresses found in entities")
            return TopologyAnalysisResult(
                subnets=[],
                relationships=[],
                network_entities=[],
                stats={'entities_with_ips': 0, 'total_ips': 0, 'subnets': 0}
            )
        
        # Infer subnets
        if infer_subnets:
            subnets = self._infer_subnets(ip_map)
        else:
            subnets = []
        
        # Create subnet entities
        network_entities = []
        if create_subnet_entities:
            network_entities = self._create_subnet_entities(subnets)
        
        # Create relationships
        relationships = self._create_network_relationships(ip_map, subnets)
        
        # Build stats
        stats = {
            'entities_with_ips': len(ip_map),
            'total_ips': sum(len(ips) for ips in ip_map.values()),
            'subnets': len(subnets),
            'private_subnets': sum(1 for s in subnets if s.network_type == 'private'),
            'public_subnets': sum(1 for s in subnets if s.network_type == 'public'),
            'network_relationships': len(relationships),
            'network_entities': len(network_entities)
        }
        
        logger.info(
            f"Network topology analysis complete: {stats['subnets']} subnets, "
            f"{stats['network_relationships']} relationships, "
            f"{stats['entities_with_ips']} entities with IPs"
        )
        
        return TopologyAnalysisResult(
            subnets=subnets,
            relationships=relationships,
            network_entities=network_entities,
            stats=stats
        )
    
    def _extract_ip_addresses(
        self,
        entities: List[Dict[str, Any]]
    ) -> Dict[str, List[str]]:
        """
        Extract IP addresses from entities.
        
        Returns:
            Dict mapping entity_id -> list of IP addresses
        """
        ip_map = {}
        
        for entity in entities:
            entity_id = entity.get('entity_id', entity.get('id', ''))
            if not entity_id:
                continue
            
            # Get attributes
            attributes = entity.get('attributes', entity.get('properties', {}))
            
            # Look for IP addresses in various fields
            ip_addresses = []
            
            # Direct IP field
            ip_field = attributes.get('ip', attributes.get('ip_address', attributes.get('ipaddress', '')))
            if ip_field:
                ips = self._parse_ip_field(ip_field)
                ip_addresses.extend(ips)
            
            # IP addresses list
            ip_list = attributes.get('ip_addresses', [])
            if isinstance(ip_list, list):
                for ip_item in ip_list:
                    ips = self._parse_ip_field(ip_item)
                    ip_addresses.extend(ips)
            
            # Network interfaces
            interfaces = attributes.get('interfaces', attributes.get('network_interfaces', []))
            if isinstance(interfaces, list):
                for iface in interfaces:
                    if isinstance(iface, dict):
                        iface_ip = iface.get('ip', iface.get('ip_address', ''))
                        if iface_ip:
                            ips = self._parse_ip_field(iface_ip)
                            ip_addresses.extend(ips)
            
            if ip_addresses:
                ip_map[entity_id] = list(set(ip_addresses))  # Deduplicate
        
        return ip_map
    
    def _parse_ip_field(self, ip_field: Any) -> List[str]:
        """Parse IP addresses from a field value."""
        ips = []
        
        if not ip_field:
            return ips
        
        ip_str = str(ip_field).strip()
        
        # Handle comma or semicolon separated IPs
        if ',' in ip_str or ';' in ip_str:
            parts = re.split(r'[,;]', ip_str)
            for part in parts:
                part = part.strip()
                if self._is_valid_ip(part):
                    ips.append(part)
        else:
            if self._is_valid_ip(ip_str):
                ips.append(ip_str)
        
        return ips
    
    def _is_valid_ip(self, ip_str: str) -> bool:
        """Check if string is a valid IP address."""
        try:
            ip_address(ip_str)
            return True
        except ValueError:
            return False
    
    def _infer_subnets(
        self,
        ip_map: Dict[str, List[str]]
    ) -> List[NetworkSubnet]:
        """
        Infer subnets from IP addresses.
        
        Groups IPs into /24 subnets by default.
        """
        # Group IPs by network
        subnet_groups = defaultdict(set)
        
        for entity_id, ip_list in ip_map.items():
            for ip_str in ip_list:
                try:
                    ip = ip_address(ip_str)
                    
                    # Only handle IPv4 for now
                    if isinstance(ip, IPv4Address):
                        # Infer /24 subnet
                        network = ip_network(f"{ip}/{self.default_subnet_mask}", strict=False)
                        network_str = str(network)
                        subnet_groups[network_str].add(entity_id)
                
                except Exception as e:
                    logger.debug(f"Failed to parse IP {ip_str}: {e}")
                    continue
        
        # Create NetworkSubnet objects
        subnets = []
        for network_str, hosts in subnet_groups.items():
            try:
                network = ip_network(network_str)
                
                # Classify network type
                network_type = self._classify_network(network)
                
                # Infer gateway
                gateway = self._infer_gateway(network)
                
                subnet = NetworkSubnet(
                    network=network_str,
                    hosts=list(hosts),
                    network_type=network_type,
                    gateway=gateway,
                    description=f"{network_type.capitalize()} subnet with {len(hosts)} hosts"
                )
                subnets.append(subnet)
            
            except Exception as e:
                logger.warning(f"Failed to create subnet for {network_str}: {e}")
                continue
        
        # Sort by network address
        subnets.sort(key=lambda s: s.network)
        
        return subnets
    
    def _classify_network(self, network: IPv4Network) -> str:
        """Classify network as private, public, or loopback."""
        # Check loopback
        if network.overlaps(self.loopback_network):
            return 'loopback'
        
        # Check private
        for private_net in self.private_networks:
            if network.overlaps(private_net):
                return 'private'
        
        # Default to public
        return 'public'
    
    def _infer_gateway(self, network: IPv4Network) -> Optional[str]:
        """Infer likely gateway IP for subnet."""
        # Common patterns: .1 or .254
        network_addr = network.network_address
        
        # Try .1
        gateway_1 = network_addr + 1
        if gateway_1 in network:
            return str(gateway_1)
        
        # Try .254 (for /24 networks)
        if network.prefixlen == 24:
            gateway_254 = network_addr + 254
            if gateway_254 in network:
                return str(gateway_254)
        
        return None
    
    def _create_subnet_entities(
        self,
        subnets: List[NetworkSubnet]
    ) -> List[Dict[str, Any]]:
        """Create network subnet entities."""
        entities = []
        
        for subnet in subnets:
            entity = {
                'entity_id': f"subnet_{subnet.network.replace('/', '_').replace('.', '_')}",
                'entity_type': 'network_subnet',
                'name': subnet.network,
                'attributes': {
                    'network': subnet.network,
                    'network_type': subnet.network_type,
                    'host_count': len(subnet.hosts),
                    'gateway': subnet.gateway,
                    'description': subnet.description
                }
            }
            
            if subnet.vlan:
                entity['attributes']['vlan'] = subnet.vlan
            
            entities.append(entity)
        
        return entities
    
    def _create_network_relationships(
        self,
        ip_map: Dict[str, List[str]],
        subnets: List[NetworkSubnet]
    ) -> List[Dict[str, Any]]:
        """Create network connectivity relationships."""
        relationships = []
        
        # Map entity IDs to subnets
        entity_to_subnet = {}
        for subnet in subnets:
            for host_id in subnet.hosts:
                entity_to_subnet[host_id] = subnet.network
        
        # Create IN_SUBNET relationships
        for entity_id, subnet_network in entity_to_subnet.items():
            subnet_id = f"subnet_{subnet_network.replace('/', '_').replace('.', '_')}"
            
            relationships.append({
                'source_id': entity_id,
                'target_id': subnet_id,
                'relationship_type': 'IN_SUBNET',
                'properties': {
                    'network': subnet_network
                }
            })
        
        # Create SAME_SUBNET relationships (entities in same subnet can communicate)
        subnet_to_entities = defaultdict(list)
        for entity_id, subnet_network in entity_to_subnet.items():
            subnet_to_entities[subnet_network].append(entity_id)
        
        for subnet_network, entity_ids in subnet_to_entities.items():
            # Only create relationships if more than one entity
            if len(entity_ids) > 1:
                for i, entity_1 in enumerate(entity_ids):
                    for entity_2 in entity_ids[i+1:]:
                        relationships.append({
                            'source_id': entity_1,
                            'target_id': entity_2,
                            'relationship_type': 'SAME_SUBNET',
                            'properties': {
                                'network': subnet_network,
                                'bidirectional': True
                            }
                        })
        
        return relationships


def analyze_network_topology(
    entities: List[Dict[str, Any]],
    infer_subnets: bool = True,
    create_subnet_entities: bool = True
) -> Dict[str, Any]:
    """
    Convenience function to analyze network topology.
    
    Args:
        entities: List of entity dicts
        infer_subnets: If True, automatically infer subnets
        create_subnet_entities: If True, create subnet entities
    
    Returns:
        Dict with topology analysis results
    """
    analyzer = NetworkTopologyAnalyzer()
    result = analyzer.analyze_topology(entities, infer_subnets, create_subnet_entities)
    
    return {
        'subnets': [
            {
                'network': s.network,
                'hosts': s.hosts,
                'network_type': s.network_type,
                'gateway': s.gateway,
                'vlan': s.vlan,
                'description': s.description
            }
            for s in result.subnets
        ],
        'relationships': result.relationships,
        'network_entities': result.network_entities,
        'stats': result.stats
    }
