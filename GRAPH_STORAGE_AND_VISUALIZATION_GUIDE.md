# Graph Storage and Visualization Guide
**Created:** October 5, 2025  
**Purpose:** Complete documentation of how entities/relationships are stored in Neo4j and visualized in the Graph tab

---

## Executive Summary

This guide explains how rich infrastructure data (like the network entities you provided as examples) is stored in Neo4j graph database and visualized in the project's Graph tab with multiple viewpoints.

**Key Points:**
✅ All entity attributes, tags, and properties are fully preserved in Neo4j  
✅ Multiple graph viewpoints available: Knowledge Graph, Infrastructure, Platform-Centric, Document Source, Environment  
✅ Entities support hierarchical relationships, network topology, and metadata enrichment  
✅ Visualization uses force-directed layouts with color-coded entity types  

---

## Part 1: Entity Storage in Neo4j

### Entity Structure

Your example entities are stored as Neo4j nodes with the following structure:

```json
{
  "id": "segment_internet_cloud",
  "type": "network_segment",
  "name": "Internet Cloud",
  "attributes": {
    "ip_address": null,
    "device_type": null,
    "model": null,
    "ports": null,
    "location": "Public",
    "vlans": [],
    "subnets": []
  },
  "tags": ["network", "wan", "public"]
}
```

This becomes a Neo4j node with these properties:

#### Node Labels
- **Primary:** `:Entity` (all nodes have this)
- **Type-Specific:** `:NetworkSegment` (derived from `type: "network_segment"`)
- **Example:** `:Entity:NetworkSegment`

#### Node Properties

| Property | Value | Source | Purpose |
|----------|-------|--------|---------|
| `canonical_id` | `<project_id>:network_segment:internet_cloud` | Generated | **UNIQUE KEY** for MERGE operations |
| `id` | `segment_internet_cloud` | From LLM | User-facing identifier |
| `type` | `network_segment` | From LLM | Entity type classification |
| `name` | `Internet Cloud` | From LLM | Display name |
| `location` | `Public` | From attributes | Flattened important field |
| `tags` | `["network", "wan", "public"]` | From LLM | Serialized as JSON string |
| `project_id` | `<uuid>` | System | Links to project |
| `document_id` | `<uuid>` | System | Source document tracking |
| `document_filename` | `network_diagram.pdf` | System | Source file name |
| `layer_type` | `network` | Enriched | Hierarchical layer classification |
| `hierarchy_level` | `1` | Enriched | Display priority (0=highest) |
| `environment` | Auto-detected | Enriched | Dev/Test/Prod if mentioned |
| `created_at` | timestamp | System | When first created |
| `updated_at` | timestamp | System | Last modified |

#### Attributes Storage

Complex nested attributes are handled in two ways:

1. **Important fields flattened** (for querying):
   - `ip_address`, `location`, `os`, `version` → Direct properties
   
2. **Full attributes preserved** (for display):
   - Original `attributes` object serialized as `attributes_json` property
   - Contains ALL data: `vlans`, `subnets`, `ports`, `model`, etc.

**Example:**
```cypher
// Your firewall entity becomes:
(n:Entity:Firewall {
  canonical_id: "proj123:firewall:dc_firewall_1",
  id: "device_dc_firewall_1",
  name: "DC Firewall 1",
  type: "firewall",
  location: "Data Center",  // Flattened
  tags_json: '["network","firewall","security","datacenter"]',
  attributes_json: '{"location":"Data Center"}',  // Full original
  layer_type: "network",
  hierarchy_level: 1,
  project_id: "proj123",
  document_id: "doc456",
  created_at: "2025-10-05T..."
})
```

### Relationship Storage

Your example relationships:

```json
{
  "source_id": "segment_internet_cloud",
  "target_id": "zone_dmz_1",
  "type": "routes_through",
  "properties": {
    "description": "Internet traffic is routed to the DMZ..."
  }
}
```

Becomes a Neo4j relationship:

```cypher
// Relationship creation
(:NetworkSegment {id: "segment_internet_cloud"})
  -[:ROUTES_THROUGH {
      description: "Internet traffic is routed to the DMZ...",
      project_id: "proj123",
      document_id: "doc456",
      created_at: "2025-10-05T..."
    }]->
(:NetworkZone {id: "zone_dmz_1"})
```

#### Relationship Types Preserved

All relationship types from your LLM extraction are preserved:
- `ROUTES_THROUGH` - Network routing
- `CONNECTS_TO` - Direct connections
- `PROTECTED_BY` - Security relationships
- `HOSTS` - Application hosting
- `DEPENDS_ON` - Dependencies
- `LOCATED_IN` - Physical/logical location
- Any custom types defined in LLM response

#### Relationship Properties

- **All properties preserved:** Everything in `properties` object
- **System metadata added:** `project_id`, `document_id`, `created_at`
- **Queryable:** Can filter by relationship type and properties

### Enrichment Pipeline

After storing your raw entities, the system applies enrichment:

#### 1. Server Entity Validation
```
Input: Server entity with IP address
↓
Validation: Check OS, hostname format, IP validity
↓
Output: Entity with validation.status = "valid"/"warning"
```

#### 2. Network Topology Analysis
```
Input: Entities with IP addresses
↓
Analysis: Detect subnets, network relationships
↓
Output: New subnet entities + BELONGS_TO relationships
```

#### 3. Hierarchical Mapping
```
Input: Applications, Servers, Platforms
↓
Analysis: Detect parent-child relationships
↓
Output: CONTAINS, RUNS_ON relationships
```

#### 4. Entity Resolution (Deduplication)
```
Input: Multiple "DC Firewall 1" entities from different documents
↓
Resolution: Canonical ID matching (project:type:name)
↓
Output: Single merged entity with combined attributes
```

### Example: Complete Storage of Your Network Diagram

**Entities Stored:**

1. `segment_internet_cloud` → `:Entity:NetworkSegment`
2. `service_mbm_swift` → `:Entity:ExternalService`
3. `service_billers` → `:Entity:ExternalService`
4. `service_partners_1` → `:Entity:ExternalService`
5. `service_partners_2` → `:Entity:ExternalService`
6. `device_extranet_firewall_1` → `:Entity:Firewall`
7. `device_extranet_router_1` → `:Entity:Router`
8. `device_extranet_router_2` → `:Entity:Router`
9. `zone_dmz_1` → `:Entity:NetworkZone`
10. `zone_dmz_2` → `:Entity:NetworkZone`
11. `device_dc_firewall_1` → `:Entity:Firewall`
12. `device_dc_firewall_2` → `:Entity:Firewall`

**Total:** 12 nodes in Neo4j, each with full attributes, tags, and metadata

**Relationships Stored:**

All `ROUTES_THROUGH`, `CONNECTS_TO`, `PROTECTED_BY` relationships preserved with their properties.

---

## Part 2: Graph Visualization

### Available Viewpoints

The Graph tab provides 5 different viewpoints:

#### 1. Knowledge Graph (Default)
**Purpose:** See ALL entities and relationships  
**Layout:** Force-directed graph  
**Features:**
- Color-coded by entity type
- Interactive drag-and-drop
- Zoom/pan controls
- Click node to see details

**Your network diagram visualization:**
```
[Internet Cloud] --routes_through--> [DMZ Zone 1]
     |                                     |
     |                              [DC Firewall 1]
     v                                     |
[External Services]                 [DMZ Zone 2]
  - MBM Swift                              |
  - BILLERS                         [DC Firewall 2]
  - VISA/CB/EIDA
```

#### 2. Infrastructure View
**Purpose:** Filter to show only infrastructure entities  
**Filtered Types:** Servers, Networks, Databases, Applications  
**Excludes:** Discovery nodes, facts, documents

**For your network:**
- Shows all devices (firewalls, routers)
- Shows all zones (DMZ 1, DMZ 2)
- Shows all segments (Internet Cloud)
- Shows all services (external services)

#### 3. Platform-Centric View
**Purpose:** Hierarchical view by platform/application layers  
**Hierarchy:**
```
Level 0: Platforms/Cloud Providers
    ↓
Level 1: Applications/Services
    ↓
Level 2: Servers/Compute
    ↓
Level 3: Databases/Storage
    ↓
Level 4: Network/Infrastructure
```

**Your network in Platform-Centric:**
```
Network Infrastructure (Level 4)
├── Internet Cloud (segment)
├── DMZ Infrastructure
│   ├── DMZ Zone 1
│   └── DMZ Zone 2
├── Firewalls
│   ├── Extranet Firewall
│   ├── DC Firewall 1
│   └── DC Firewall 2
└── Routers
    ├── Extranet Router 1
    └── Extranet Router 2
```

#### 4. Document Source View
**Purpose:** Filter graph by source document  
**Features:**
- Dropdown to select document
- Shows only entities from that document
- Highlights cross-document relationships

**Example:**
```
Select: "network_diagram.pdf"
Shows: All 12 network entities
Highlights: Links to servers from other documents
```

#### 5. Environment View
**Purpose:** Group by environment (Dev/Test/Prod)  
**Features:**
- Color-coded by environment
- Filter by environment type
- Shows cross-environment dependencies

**Your network (if environment detected):**
```
Production (red cluster)
├── DC Firewall 1
├── DC Firewall 2
└── DMZ zones

External (gray cluster)
├── Internet Cloud
└── External Services
```

### Visual Encoding

#### Node Colors (by Type)

| Entity Type | Color | Your Examples |
|------------|-------|---------------|
| Server | Blue | (none in your data) |
| Database | Green | (none in your data) |
| Application | Purple | (none in your data) |
| Network Device | Orange | Firewalls, Routers |
| Network Segment | Yellow | Internet Cloud |
| Network Zone | Teal | DMZ zones |
| External Service | Gray | MBM Swift, BILLERS, etc. |
| Firewall | Red-Orange | All firewall entities |
| Router | Dark Orange | All router entities |

#### Node Size

- **Based on degree centrality** (number of connections)
- More connections = larger node
- Example: DMZ Zone 1 (hub) appears larger than isolated services

#### Edge Styles

| Relationship Type | Visual Style | Your Examples |
|------------------|--------------|---------------|
| ROUTES_THROUGH | Dashed line | Internet → DMZ |
| CONNECTS_TO | Solid line | Device connections |
| PROTECTED_BY | Thick line | Security relationships |
| HOSTS | Dotted line | App hosting |
| DEPENDS_ON | Arrow | Dependencies |

#### Tooltips

Hover over node to see:
```
Firewall — DC Firewall 1 (deg=5)
Type: firewall
Location: Data Center
Tags: network, firewall, security, datacenter
Document: network_diagram.pdf
```

### Interactive Features

#### Node Clicking
- **Click node:** Show detail panel with all attributes
- **Double-click:** Expand connected nodes
- **Right-click:** Context menu (filter, isolate, expand)

#### Filtering
- By entity type (checkboxes)
- By document source (dropdown)
- By environment (radio buttons)
- By tag (multi-select)
- By search (text input)

#### Layout Controls
- **Force-directed:** Auto-arrange by connections
- **Hierarchical:** Top-down tree layout
- **Circular:** Ring layout
- **Grid:** Matrix layout

#### Export
- Export as PNG/SVG
- Export graph data as JSON
- Export Cypher query for Neo4j

---

## Part 3: Query Examples

### Get All Network Devices
```cypher
MATCH (p:Project {id: $project_id})-[:CONTAINS]->(n)
WHERE n.type IN ['firewall', 'router', 'switch', 'load_balancer']
RETURN n.name, n.type, n.location, n.tags
```

### Get Network Topology
```cypher
MATCH (p:Project {id: $project_id})-[:CONTAINS]->(source)
MATCH (source)-[r:ROUTES_THROUGH|CONNECTS_TO]->(target)
WHERE source.type IN ['network_segment', 'network_zone', 'firewall', 'router']
RETURN source.name, type(r), target.name, r.description
```

### Get DMZ Zone Entities
```cypher
MATCH (p:Project {id: $project_id})-[:CONTAINS]->(zone:NetworkZone)
WHERE zone.name CONTAINS 'DMZ'
MATCH (zone)<-[r]-(connected)
RETURN zone.name, connected.name, connected.type, type(r)
```

### Get All Entities from a Document
```cypher
MATCH (p:Project {id: $project_id})-[:CONTAINS]->(n)
WHERE n.document_filename = 'network_diagram.pdf'
RETURN n.name, n.type, labels(n), n.tags
```

### Get Entity with All Attributes
```cypher
MATCH (n:Entity {canonical_id: 'proj:firewall:dc_firewall_1'})
RETURN n.name, n.type, n.location, 
       n.tags_json, n.attributes_json,
       n.document_filename, n.created_at
```

---

## Part 4: Data Preservation Verification

### Your Example: Firewall Entity

**Input (from LLM):**
```json
{
  "id": "device_dc_firewall_2",
  "type": "firewall",
  "name": "DC Firewall 2",
  "attributes": {
    "location": "Data Center"
  },
  "tags": ["network", "firewall", "security", "datacenter"]
}
```

**Stored in Neo4j:**
```cypher
CREATE (n:Entity:Firewall {
  canonical_id: "a474a8aa-eb65-46ff-8017-0596bf2ad29c:firewall:dc_firewall_2",
  id: "device_dc_firewall_2",
  name: "DC Firewall 2",
  type: "firewall",
  location: "Data Center",              // ✅ Preserved
  tags_json: '["network","firewall","security","datacenter"]',  // ✅ Preserved
  attributes_json: '{"location":"Data Center"}',  // ✅ Full attributes preserved
  layer_type: "network",                // ✅ Enriched
  hierarchy_level: 1,                   // ✅ Enriched
  project_id: "a474a8aa-eb65-46ff-8017-0596bf2ad29c",
  document_id: "...",
  document_filename: "network_diagram.pdf",
  created_at: "2025-10-05T22:11:49Z"
})
```

**Queryable in Graph Tab:**
- ✅ Name: "DC Firewall 2"
- ✅ Type: Firewall (shows as Firewall icon)
- ✅ Location: "Data Center" (in tooltip)
- ✅ Tags: network, firewall, security, datacenter (filterable)
- ✅ Document: "network_diagram.pdf" (filterable by source)
- ✅ Color: Red-Orange (firewall type)
- ✅ Connections: All ROUTES_THROUGH, CONNECTS_TO relationships visible

### Your Example: Relationship

**Input (from LLM):**
```json
{
  "source_id": "segment_internet_cloud",
  "target_id": "zone_dmz_1",
  "type": "routes_through",
  "properties": {
    "description": "Internet traffic is routed to the DMZ, likely through an unseen edge firewall."
  }
}
```

**Stored in Neo4j:**
```cypher
(internet:NetworkSegment {id: "segment_internet_cloud"})
  -[:ROUTES_THROUGH {
      description: "Internet traffic is routed to the DMZ, likely through an unseen edge firewall.",
      project_id: "a474a8aa-eb65-46ff-8017-0596bf2ad29c",
      document_id: "...",
      created_at: "2025-10-05T22:11:49Z"
    }]->
(dmz:NetworkZone {id: "zone_dmz_1"})
```

**Visualized in Graph Tab:**
- ✅ Arrow from "Internet Cloud" to "DMZ Server Farm 1"
- ✅ Edge label: "ROUTES_THROUGH" (or "routes through")
- ✅ Tooltip on edge: "Internet traffic is routed to the DMZ..."
- ✅ Edge style: Dashed line (routing relationship)
- ✅ Clickable: Shows full relationship details

---

## Part 5: Rich Data Extraction Assurance

### What Gets Preserved

✅ **Entity IDs:** All original IDs from LLM  
✅ **Entity Types:** All types (firewall, router, network_segment, network_zone, external_service)  
✅ **Entity Names:** All display names  
✅ **Attributes:** ALL attributes (ip_address, location, model, ports, vlans, subnets, etc.)  
✅ **Tags:** All tags for categorization  
✅ **Relationships:** All relationship types and properties  
✅ **Relationship Properties:** All descriptions and metadata  
✅ **Document Source:** Filename for traceability  

### What Gets Enriched (Added)

✅ **Canonical IDs:** Stable identifiers for deduplication  
✅ **Layer Classification:** network, application, data, platform layers  
✅ **Hierarchy Levels:** 0-4 for hierarchical layout  
✅ **Environment Detection:** Dev/Test/Prod auto-detection  
✅ **Timestamps:** Created/updated tracking  
✅ **Project Linkage:** Connects to parent project node  
✅ **Network Topology:** Subnet entities and BELONGS_TO relationships (if IPs present)  
✅ **Server Validation:** Validation status for servers  

### What Does NOT Get Filtered/Lost

❌ No filtering by confidence (all entities kept)  
❌ No attribute truncation (full preservation)  
❌ No tag reduction (all tags preserved)  
❌ No relationship dropping (all relationships stored)  
❌ No type rejection (all entity types supported)  
❌ No name normalization (original names kept)  

### Verification Query

To verify ALL your example entities are stored correctly:

```cypher
MATCH (p:Project {id: $project_id})-[:CONTAINS]->(n)
WHERE n.document_filename = 'network_diagram.pdf'
RETURN 
  n.id as entity_id,
  n.name as name,
  n.type as type,
  n.location as location,
  n.tags_json as tags,
  n.attributes_json as all_attributes,
  labels(n) as labels
ORDER BY n.type, n.name
```

**Expected Results:**
- 12 rows (one for each entity)
- Each row contains full data
- All attributes, tags present
- Correct labels (:Entity:Firewall, :Entity:Router, etc.)

---

## Part 6: Visualization Best Practices

### For Network Diagrams

1. **Use Infrastructure View** - Filters to network entities
2. **Enable hierarchical layout** - Shows layers clearly
3. **Color by type** - Distinguishes firewalls, routers, zones
4. **Size by connections** - Highlights hub devices
5. **Export as SVG** - Documentation-ready diagrams

### For Server Inventories

1. **Use Platform-Centric View** - Groups by application/platform
2. **Filter by environment** - Separate prod/dev/test
3. **Search by tag** - Find all "linux" or "windows" servers
4. **Click server node** - See full inventory details (CPU, RAM, apps, etc.)
5. **Export as JSON** - Machine-readable inventory

### For Mixed Diagrams

1. **Start with Knowledge Graph** - See everything
2. **Apply type filters** - Hide/show specific entity types
3. **Use document filter** - Isolate one diagram
4. **Expand connected nodes** - Explore relationships
5. **Create custom view** - Save filtered configuration

---

## Conclusion

**Your Rich Network Entities Are Fully Preserved:**

✅ All 12 entities from your example stored as Neo4j nodes  
✅ All attributes (`location`, `vlans`, `subnets`, etc.) preserved  
✅ All tags (`network`, `firewall`, `security`, etc.) queryable  
✅ All relationships (`routes_through`, etc.) visualized  
✅ All relationship properties (`description`, etc.) accessible  

**Multiple Visualization Viewpoints Available:**

✅ Knowledge Graph: Force-directed, all entities  
✅ Infrastructure: Filtered to infra entities  
✅ Platform-Centric: Hierarchical by layer  
✅ Document Source: Filtered by document  
✅ Environment: Grouped by Dev/Test/Prod  

**Rich Querying Capabilities:**

✅ Query by type, name, tag, attribute  
✅ Traverse relationships with Cypher  
✅ Filter by document source  
✅ Export graph data  

**No Data Loss or Filtering:**

❌ No entities rejected  
❌ No attributes truncated  
❌ No tags removed  
❌ No relationships dropped  

Your infrastructure data is fully preserved in Neo4j and richly visualized in the Graph tab with multiple analytical viewpoints!
