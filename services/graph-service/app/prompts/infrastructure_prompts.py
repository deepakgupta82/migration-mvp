"""
Infrastructure-aware prompt templates for entity extraction.
Supports ANY infrastructure data type with adaptive strategies.
"""
from typing import Dict, List, Any, Optional


# Document Analysis Prompt
DOCUMENT_ANALYSIS_PROMPT = """Analyze the following document content and determine its type and best extraction strategy.

Document Content (first 2000 characters):
{content_preview}

Analyze and determine:
1. Document type (server_inventory, network_diagram, database_schema, application_manifest, cloud_resources, storage_config, security_policy, monitoring_config, infrastructure_general, narrative_text, mixed_content, or unknown)
2. What entity types should be extracted (servers, databases, applications, networks, storage, cloud resources, containers, etc.)
3. Best extraction strategy (tabular_structured, hierarchical_nested, relationship_focused, attribute_heavy, timeline_based, location_based, mixed_strategy)
4. Key indicators that led to this analysis
5. Complexity level (low, medium, high, very_high)

Respond in JSON format:
{{
  "document_type": "...",
  "suggested_entities": ["entity_type1", "entity_type2", ...],
  "extraction_strategy": "...",
  "confidence": 0.0-1.0,
  "key_indicators": ["indicator1", "indicator2", ...],
  "complexity": "low|medium|high|very_high",
  "metadata": {{}}
}}"""


# Base Entity Extraction Prompt
BASE_ENTITY_EXTRACTION_PROMPT = """Extract infrastructure entities and relationships from the following content.

CRITICAL INSTRUCTIONS:
1. Extract ONE entity for EACH distinct infrastructure component mentioned
2. Do NOT combine or summarize multiple components into one entity
3. Process ALL data provided - extract EVERY entity you find
4. Preserve ALL attributes, properties, and details for each entity

Content Type: {document_type}
Extraction Strategy: {strategy}

Content:
{content}

Extract all relevant infrastructure entities with their attributes and relationships.
Focus on: {focus_entities}

For EACH infrastructure component, create ONE entity with:
- Unique ID based on the component name/identifier
- Specific type (server, database, network_device, application, etc.)
- Descriptive name
- All available attributes (IP, version, location, etc.)
- Relevant tags for categorization

Return JSON with this structure - ONE entity per component:
{{
  "entities": [
    {{
      "id": "unique_id_1",
      "type": "entity_type",
      "name": "component_name_1",
      "attributes": {{
        "key1": "value1",
        "key2": "value2"
      }},
      "tags": ["tag1", "tag2"]
    }},
    {{
      "id": "unique_id_2",
      "type": "entity_type",
      "name": "component_name_2",
      "attributes": {{}},
      "tags": []
    }}
    // ... ONE entity for EACH component found
  ],
  "relationships": [
    {{
      "source_id": "unique_id_1",
      "target_id": "unique_id_2",
      "type": "relationship_type",
      "properties": {{
        "description": "relationship details"
      }}
    }}
    // ... ONE relationship for EACH connection/dependency
  ]
}}

REMEMBER: Extract EVERY entity mentioned, not just a summary or sample."""


# Server Inventory Specific Prompt
SERVER_INVENTORY_PROMPT = """Extract server infrastructure entities from this inventory data.

CRITICAL INSTRUCTIONS:
1. Process EACH ROW/LINE/ENTRY in the content as a SEPARATE entity
2. Extract ONE entity for EACH server/system you find
3. Do NOT summarize or combine multiple servers into one entity
4. Do NOT skip any rows - process ALL data provided

Content:
{content}

For EACH server/system row, extract:
- Server name/hostname
- IP address(es)
- Operating system (OS)
- OS version
- Hardware specs (CPU, RAM, storage)
- Location/datacenter
- Environment (prod/dev/test)
- Applications/services running
- Owner/team
- Any dependencies or connections

Return comprehensive JSON with ONE entity PER ROW:
{{
  "entities": [
    {{
      "id": "server_<unique_name_or_ip>",
      "type": "server",
      "name": "server_name_or_hostname",
      "attributes": {{
        "hostname": "...",
        "ip_addresses": ["..."],
        "os": "...",
        "os_version": "...",
        "cpu": "...",
        "ram": "...",
        "storage": "...",
        "location": "...",
        "environment": "...",
        "applications": ["..."],
        "owner": "...",
        "notes": "...",
        "source_row": "original row data for reference"
      }},
      "tags": ["server", "physical|virtual", "os_family"]
    }},
    {{
      "id": "server_<another_unique_name>",
      "type": "server",
      "name": "another_server_name",
      "attributes": {{ ... }}
    }}
    // ... ONE entity for EACH ROW in the data
  ],
  "relationships": [
    {{
      "source_id": "server_id",
      "target_id": "application_id",
      "type": "hosts",
      "properties": {{}}
    }}
  ]
}}

EXAMPLE (if you receive 3 server rows, return 3 entities):
Input: 
Row 1: web01, 10.0.0.1, Ubuntu 20.04
Row 2: db01, 10.0.0.2, CentOS 7
Row 3: app01, 10.0.0.3, Windows Server 2019

Output:
{{
  "entities": [
    {{"id": "server_web01", "type": "server", "name": "web01", "attributes": {{"ip_addresses": ["10.0.0.1"], "os": "Ubuntu", "os_version": "20.04"}}}},
    {{"id": "server_db01", "type": "server", "name": "db01", "attributes": {{"ip_addresses": ["10.0.0.2"], "os": "CentOS", "os_version": "7"}}}},
    {{"id": "server_app01", "type": "server", "name": "app01", "attributes": {{"ip_addresses": ["10.0.0.3"], "os": "Windows Server", "os_version": "2019"}}}}
  ],
  "relationships": []
}}

Extract ALL servers from the data - one entity per row. Be thorough and process EVERY single row."""


# Network Infrastructure Prompt
NETWORK_INFRASTRUCTURE_PROMPT = """Extract network infrastructure entities and topology.

CRITICAL INSTRUCTIONS:
1. Extract ONE entity for EACH network device, segment, zone, or service mentioned
2. Do NOT combine multiple devices/segments into a single entity
3. Extract ALL entities - no matter how many there are
4. Preserve ALL attributes, tags, and relationship details

Content:
{content}

Extract:
- Network devices (routers, switches, firewalls, load balancers) - ONE entity EACH
- Network segments/subnets - ONE entity EACH
- Network zones (DMZ, internal, external) - ONE entity EACH
- External services - ONE entity EACH
- Connections and routing - ONE relationship EACH
- IP address schemes
- VLANs and network zones
- Security boundaries

Return comprehensive JSON with ONE entity per device/segment/zone:
{{
  "entities": [
    {{
      "id": "device_<unique_name>",
      "type": "router|switch|firewall|load_balancer|network_segment|network_zone|external_service",
      "name": "device_or_segment_name",
      "attributes": {{
        "ip_address": "..." OR null,
        "device_type": "..." OR null,
        "model": "..." OR null,
        "ports": "..." OR null,
        "location": "...",
        "vlans": ["..."],
        "subnets": ["..."]
      }},
      "tags": ["network", "device_type", "location_tag"]
    }},
    {{
      "id": "segment_<unique_name>",
      "type": "network_segment",
      "name": "segment_name",
      "attributes": {{
        "ip_address": null,
        "location": "...",
        "subnets": ["..."]
      }},
      "tags": ["network", "segment"]
    }}
    // ... ONE entity for EACH device, segment, zone, service
  ],
  "relationships": [
    {{
      "source_id": "device1_id",
      "target_id": "device2_id",
      "type": "connects_to|routes_through|protected_by",
      "properties": {{
        "port": "...",
        "protocol": "...",
        "description": "..."
      }}
    }}
    // ... ONE relationship for EACH connection
  ]
}}

EXAMPLE:
If content mentions:
- Internet Cloud
- DMZ Zone 1
- Firewall 1
- Firewall 2
- Router 1

Then extract 5 entities:
{{
  "entities": [
    {{"id": "segment_internet", "type": "network_segment", "name": "Internet Cloud", ...}},
    {{"id": "zone_dmz_1", "type": "network_zone", "name": "DMZ Zone 1", ...}},
    {{"id": "device_firewall_1", "type": "firewall", "name": "Firewall 1", ...}},
    {{"id": "device_firewall_2", "type": "firewall", "name": "Firewall 2", ...}},
    {{"id": "device_router_1", "type": "router", "name": "Router 1", ...}}
  ],
  "relationships": [...]
}}

Extract EVERY device, segment, zone, and service mentioned. Be comprehensive."""


# Database Infrastructure Prompt
DATABASE_INFRASTRUCTURE_PROMPT = """Extract database infrastructure entities.

Content:
{content}

Extract:
- Database servers/instances
- Database names and types (MySQL, PostgreSQL, Oracle, SQL Server, MongoDB, etc.)
- Versions and configurations
- Storage allocations
- Backup configurations
- Replication relationships
- Application dependencies

Return JSON:
{{
  "entities": [
    {{
      "id": "db_<name>",
      "type": "database",
      "name": "database_name",
      "attributes": {{
        "db_type": "mysql|postgres|oracle|mssql|mongodb|...",
        "version": "...",
        "host": "...",
        "port": "...",
        "storage_gb": "...",
        "backup_enabled": true|false,
        "replication": "...",
        "applications": ["..."]
      }},
      "tags": ["database", "db_type"]
    }}
  ],
  "relationships": [
    {{
      "source_id": "db_id",
      "target_id": "server_id",
      "type": "runs_on",
      "properties": {{}}
    }}
  ]
}}"""


# Cloud Resources Prompt
CLOUD_RESOURCES_PROMPT = """Extract cloud infrastructure resources.

Content:
{content}

Extract:
- Cloud instances (EC2, VMs, compute instances)
- Storage (S3, blob storage, volumes)
- Databases (RDS, Cloud SQL, Cosmos, etc.)
- Networking (VPCs, subnets, security groups)
- Services (Lambda, Cloud Functions, App Services)
- Containers (ECS, AKS, GKE)
- Load balancers, CDNs

Return JSON:
{{
  "entities": [
    {{
      "id": "cloud_<resource>",
      "type": "cloud_resource",
      "name": "resource_name",
      "attributes": {{
        "cloud_provider": "aws|azure|gcp|...",
        "resource_type": "...",
        "region": "...",
        "tier": "...",
        "pricing": "...",
        "tags": {{}}
      }},
      "tags": ["cloud", "provider", "resource_type"]
    }}
  ],
  "relationships": [
    {{
      "source_id": "resource1",
      "target_id": "resource2",
      "type": "depends_on|connects_to",
      "properties": {{}}
    }}
  ]
}}"""


# Application Manifest Prompt
APPLICATION_MANIFEST_PROMPT = """Extract application infrastructure entities.

Content:
{content}

Extract:
- Applications and services
- Application components/microservices
- Dependencies (databases, APIs, services)
- Deployment configurations
- Versions and technologies
- Resource requirements

Return JSON:
{{
  "entities": [
    {{
      "id": "app_<name>",
      "type": "application|service|middleware",
      "name": "application_name",
      "attributes": {{
        "version": "...",
        "technology": "...",
        "language": "...",
        "framework": "...",
        "deployment_type": "...",
        "dependencies": ["..."],
        "resource_requirements": {{}}
      }},
      "tags": ["application", "technology"]
    }}
  ],
  "relationships": [
    {{
      "source_id": "app_id",
      "target_id": "dependency_id",
      "type": "depends_on|communicates_with",
      "properties": {{"protocol": "...", "port": "..."}}
    }}
  ]
}}"""


# Storage Infrastructure Prompt
STORAGE_INFRASTRUCTURE_PROMPT = """Extract storage infrastructure entities.

Content:
{content}

Extract:
- Storage systems (SAN, NAS, DAS)
- Storage volumes and filesystems
- Backup systems
- Storage capacity and usage
- Replication and redundancy
- Connected servers

Return JSON:
{{
  "entities": [
    {{
      "id": "storage_<name>",
      "type": "storage_system|backup_system",
      "name": "storage_name",
      "attributes": {{
        "storage_type": "san|nas|das|cloud|...",
        "capacity_tb": "...",
        "used_tb": "...",
        "raid_level": "...",
        "replication": "...",
        "backup_schedule": "..."
      }},
      "tags": ["storage", "storage_type"]
    }}
  ],
  "relationships": [
    {{
      "source_id": "server_id",
      "target_id": "storage_id",
      "type": "uses|backed_up_by",
      "properties": {{}}
    }}
  ]
}}"""


# Security Infrastructure Prompt
SECURITY_INFRASTRUCTURE_PROMPT = """Extract security infrastructure entities.

Content:
{content}

Extract:
- Security appliances (firewalls, IDS/IPS, WAF)
- Security policies and rules
- Access controls
- Encryption configurations
- Compliance requirements
- Monitoring/SIEM systems

Return JSON:
{{
  "entities": [
    {{
      "id": "security_<name>",
      "type": "security_appliance|firewall",
      "name": "security_device",
      "attributes": {{
        "device_type": "firewall|ids|ips|waf|...",
        "vendor": "...",
        "policies": ["..."],
        "protected_zones": ["..."]
      }},
      "tags": ["security", "device_type"]
    }}
  ],
  "relationships": [
    {{
      "source_id": "resource_id",
      "target_id": "security_id",
      "type": "protected_by",
      "properties": {{}}
    }}
  ]
}}"""


# Monitoring Infrastructure Prompt
MONITORING_INFRASTRUCTURE_PROMPT = """Extract monitoring infrastructure entities.

Content:
{content}

Extract:
- Monitoring systems (Nagios, Zabbix, Prometheus, Datadog, etc.)
- Monitored resources
- Alerts and thresholds
- Dashboards
- Metrics collected

Return JSON:
{{
  "entities": [
    {{
      "id": "monitor_<name>",
      "type": "monitoring_system",
      "name": "monitoring_tool",
      "attributes": {{
        "tool": "nagios|zabbix|prometheus|datadog|...",
        "monitored_resources": ["..."],
        "metrics": ["..."],
        "alert_rules": ["..."]
      }},
      "tags": ["monitoring", "tool"]
    }}
  ],
  "relationships": [
    {{
      "source_id": "monitor_id",
      "target_id": "resource_id",
      "type": "monitors",
      "properties": {{"metrics": ["..."]}}
    }}
  ]
}}"""


# Enhanced Prompt with Examples (for retry attempts)
ENHANCED_PROMPT_WITH_EXAMPLES = """Extract infrastructure entities from the content below.

Previous attempt found 0 entities. Please be more thorough.

{base_prompt}

EXAMPLES of what to extract:

Example 1 - Server:
{{
  "id": "server_web01",
  "type": "server",
  "name": "web01.example.com",
  "attributes": {{
    "ip_addresses": ["192.168.1.10"],
    "os": "Ubuntu",
    "os_version": "20.04 LTS"
  }}
}}

Example 2 - Database:
{{
  "id": "db_mysql_prod",
  "type": "database",
  "name": "prod_mysql",
  "attributes": {{
    "db_type": "mysql",
    "version": "8.0"
  }}
}}

Example 3 - Relationship:
{{
  "source_id": "server_web01",
  "target_id": "db_mysql_prod",
  "type": "connects_to"
}}

Now extract ALL entities from the content, no matter how simple or complex."""


# Simplified Prompt (for retry attempts)
SIMPLIFIED_EXTRACTION_PROMPT = """Look at this infrastructure data and extract ANY entities you can find.

Content:
{content}

Extract anything that looks like:
- Computer systems, servers, devices
- Software, applications, services
- Networks, connections
- Databases, storage
- Cloud resources

Return even partial information in JSON format:
{{
  "entities": [
    {{
      "id": "unique_id",
      "type": "best_guess_type",
      "name": "entity_name",
      "attributes": {{"any_key": "any_value"}}
    }}
  ],
  "relationships": []
}}

Extract at least SOMETHING from the content."""


# Prompt Templates Registry
PROMPT_TEMPLATES: Dict[str, str] = {
    "server_inventory": SERVER_INVENTORY_PROMPT,
    "network_diagram": NETWORK_INFRASTRUCTURE_PROMPT,
    "database_schema": DATABASE_INFRASTRUCTURE_PROMPT,
    "cloud_resources": CLOUD_RESOURCES_PROMPT,
    "application_manifest": APPLICATION_MANIFEST_PROMPT,
    "storage_config": STORAGE_INFRASTRUCTURE_PROMPT,
    "security_policy": SECURITY_INFRASTRUCTURE_PROMPT,
    "monitoring_config": MONITORING_INFRASTRUCTURE_PROMPT,
    "infrastructure_general": BASE_ENTITY_EXTRACTION_PROMPT,
    "mixed_content": BASE_ENTITY_EXTRACTION_PROMPT,
    "unknown": BASE_ENTITY_EXTRACTION_PROMPT,
}


def get_prompt_template(document_type: str) -> str:
    """Get prompt template for document type."""
    return PROMPT_TEMPLATES.get(document_type, BASE_ENTITY_EXTRACTION_PROMPT)


def build_extraction_prompt(
    document_type: str,
    content: str,
    focus_entities: Optional[List[str]] = None,
    strategy: Optional[str] = None,
    attempt: int = 1,
    max_chars: int = 20000
) -> str:
    """Build extraction prompt based on document type and attempt number."""
    
    # Truncate content if needed
    if len(content) > max_chars:
        content = content[:max_chars] + f"\n\n[Content truncated at {max_chars} chars]"
    
    # Get base template
    template = get_prompt_template(document_type)
    
    # For retry attempts, enhance the prompt
    if attempt == 2:
        # Add examples
        template = ENHANCED_PROMPT_WITH_EXAMPLES.format(base_prompt=template)
    elif attempt >= 3:
        # Simplify and be more explicit
        template = SIMPLIFIED_EXTRACTION_PROMPT
    
    # Format the template
    prompt = template.format(
        content=content,
        document_type=document_type,
        strategy=strategy or "adaptive",
        focus_entities=", ".join(focus_entities) if focus_entities else "all infrastructure entities"
    )
    
    return prompt


def build_analysis_prompt(content: str, max_preview_chars: int = 2000) -> str:
    """Build document analysis prompt."""
    preview = content[:max_preview_chars]
    if len(content) > max_preview_chars:
        preview += f"\n\n[Preview truncated at {max_preview_chars} chars]"
    
    return DOCUMENT_ANALYSIS_PROMPT.format(content_preview=preview)
