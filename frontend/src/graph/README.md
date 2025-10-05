# Unified Graph Architecture

## Overview
This new graph architecture replaces the fragmented multi-view graph system with a **unified backend schema** and **pluggable frontend strategies** for different visualization modes.

## Backend Architecture

### Unified Endpoint
- **URL**: `GET /projects/{project_id}/graph/unified`
- **Query Parameters**:
  - `view`: knowledge | infra | platform | environment | document
  - `environment`: Filter by environment name (optional)
  - `document_id`: Center graph on specific document (optional)
  - `include_clusters`: Group discovery facts into clusters (default: true)
  - `include_related`: Include related nodes for document view (default: true)
  - `fact_sample`: Number of sample facts per cluster (default: 3)
  - `node_limit`: Maximum nodes to return (default: 800)
  - `fact_cluster_min`: Minimum facts to form cluster (default: 2)

### Normalized Schema
All views return the same node/edge structure:

**Node**:
```json
{
  "id": "unique-id",
  "role": "Platform | Application | Server | Database | FactCluster | ...",
  "display": "Human-readable label",
  "metrics": {
    "degree": 10,
    "fact_count": 25
  },
  "cluster": {
    "size": 25,
    "sample": ["fact 1", "fact 2", "fact 3"]
  },
  "level": 0,  // For platform view hierarchy
  "ring": 1,   // For document view radial layout
  "environment": "production"
}
```

**Edge**:
```json
{
  "source": "node-id-1",
  "target": "node-id-2",
  "rel_type": "HOSTS",
  "kind": "infra | data | provenance | semantic",
  "directional": true
}
```

### View-Specific Transformations

#### Knowledge View
- Excludes raw `Discovery` nodes (facts)
- Includes virtual `FactCluster` nodes (grouped by entity + category)
- Shows core entities (Platform, Application, Server, Database, etc.)

#### Infrastructure View
- Whitelist filter: Platform, Application, Server, Database, Storage, IP, OS
- Layered structure using `level` annotations (0-3)

#### Platform View
- Radial layout with `level` hints (center = Platform, rings = App/Server/Resources)
- Concentric hierarchy

#### Environment View
- Partition by `environment` field
- Synthetic environment hubs
- Cross-environment edges highlighted

#### Document View
- Radial star with document at `ring` 0
- Related entities at `ring` 1
- Optional extended neighbors at `ring` 2

### Fact Clustering Logic
1. Pre-fetch all `Discovery` nodes linked to entities
2. Group by `(entity_id, category)` key
3. If group size ≥ `fact_cluster_min`, create virtual node:
   - `id`: `fc::<entity_id>::<category>`
   - `role`: `FactCluster`
   - `cluster.size`: total count
   - `cluster.sample`: first N facts
4. Emit `DESCRIBES` edge from cluster to entity

### Supporting Endpoints

#### Metadata Endpoint
- **URL**: `GET /projects/{project_id}/graph/metadata`
- Returns available filters: roles, categories, environments, documents

#### Neighbors Endpoint
- **URL**: `GET /projects/{project_id}/graph/node/{node_id}/neighbors`
- **Query**: `depth` (1-2), `limit` (1-200)
- Returns neighbors in unified format for incremental expansion

#### Fact Cluster Expansion
- **URL**: `GET /projects/{project_id}/graph/fact-cluster/{cluster_id}`
- **Query**: `offset`, `limit` (pagination)
- Returns full fact list for cluster
- Cluster ID format: `fc::<entity_id>::<category>`

## Frontend Architecture

### GraphContainer Component
Central orchestrator for all graph views:
- Fetches data from unified endpoint
- Applies view-specific layout strategy
- Manages interactions (hover, click, expand)
- Maintains state (selection, filters, expansion)

### Layout Strategies
**Pluggable strategy pattern** in `layout/strategies.ts`:

1. **Force Layout** (knowledge view):
   - Force-directed simulation
   - Charge scaling by degree
   - Collision detection
   - Pin high-degree nodes after stabilization

2. **Layered Layout** (infra view):
   - Horizontal swimlanes by `level`
   - Fixed y-coordinate per level
   - Evenly spaced x-coordinates

3. **Radial Layout** (platform view):
   - Concentric rings by `level`
   - Angular distribution per ring
   - Center pinned

4. **Partition Layout** (environment view):
   - Vertical columns per environment
   - Stacked nodes within column

5. **Radial Document Layout** (document view):
   - Center = document (ring 0, pinned)
   - Entities = ring 1
   - Related = ring 2

### Interactions

#### Hover
- Highlight node + connected edges
- Show tooltip with role, degree, fact count
- Tooltip follows cursor

#### Click
- Focus mode: dim unrelated nodes
- Open side panel with tabs:
  - **Overview**: node details
  - **Facts**: list of discoveries (if entity)
  - **Relationships**: incoming/outgoing edges

#### Double-Click / Expand Button
- **FactCluster**: fetch full fact list, display in side panel
- **Entity**: fetch neighbors, merge into graph with fade-in animation

#### Filters
- Role checkboxes (toggle visibility by role)
- Category checkboxes (for fact clusters)
- Environment selector
- Search input (fuzzy match on `display` field, highlight matches)

#### Keyboard Shortcuts
- `F`: Fit view (auto-zoom to show all nodes)
- `L`: Reset layout (clear cached positions, re-apply strategy)
- `ESC`: Clear focus mode
- `+/-`: Zoom in/out

### State Management
Managed in `GraphContainer` component:
- `nodes`: Map<string, UnifiedNode>
- `edges`: Map<string, UnifiedEdge>
- `expandedClusters`: Set<string> (cluster IDs)
- `expandedNodes`: Set<string> (node IDs with loaded neighbors)
- `filters`: { roles, categories, environments, searchQuery }
- `selection`: string | null (selected node ID)
- `hover`: string | null (hovered node ID)
- `focusMode`: boolean

### Position Caching
- Cache key: `graph-positions-${projectId}-${view}`
- Stores `{ [nodeId]: { x, y } }` in `localStorage`
- Applied on load before layout strategy
- Saved on unmount or simulation end

## Performance Optimizations

### Backend
- **Node limit**: Default 800, truncate with warning if exceeded
- **Fact clustering**: Minimum 2 facts to form cluster (avoid noise)
- **Sample size**: Return only 3 sample facts per cluster
- **Edge filtering**: Only emit edges between retained nodes

### Frontend
- **Debounced search**: 300ms delay on search input
- **Position reuse**: Cache and restore positions between sessions
- **Progressive loading**: Fetch backbone first, expand on demand
- **Simulation throttling**: Pin high-degree nodes after 300 ticks

## Migration Path

### Phase 1 (Completed)
- Backend unified endpoint with view parameter
- Fact clustering logic
- Structural annotations (level, ring)
- Normalized schema

### Phase 2 (Completed)
- Frontend GraphContainer + strategies
- All 5 view implementations
- Interactions (hover, click, expand, filter, search)
- Side panel + legend + toolbar

### Phase 3 (Integration)
- Replace old GraphVisualizer in ProjectDetailView
- Update routing to use view parameter
- Remove legacy graph components
- Update documentation

## Extension Points

### Adding New Views
1. Add view type to `UnifiedGraphView` enum (backend)
2. Implement filter logic in `unified_graph_endpoint`
3. Add layout strategy function in `frontend/src/graph/layout/strategies.ts`
4. Update `GraphContainer` view selector

### Adding New Node Types
1. Update `infer_role` helper in `graphs.py`
2. Add color mapping in `getNodeColor` (GraphContainer)
3. Update legend dynamically (already automatic)

### Adding New Interactions
1. Add event handler in `GraphContainer` (e.g., `onNodeRightClick`)
2. Update D3 binding (`.on('contextmenu', handleRightClick)`)
3. Add state/UI as needed (e.g., context menu)

## Troubleshooting

### Empty Graph
- Check backend response: `meta.counts.nodes` should be > 0
- Verify view parameter is valid
- Check filters (roles, categories) aren't too restrictive

### Performance Issues
- Reduce `node_limit` (default 800)
- Increase `fact_cluster_min` to reduce cluster count
- Disable search when not needed
- Clear position cache if layout is slow

### Label Overlap
- Increase collision force radius in force layout
- Adjust label `dy` offset in `renderGraph`
- Use smaller font size for dense graphs

### Missing Relationships
- Check edge filtering logic (both source and target must be in node set)
- Verify relationship types exist in Neo4j
- Check `include_related` parameter for document view
