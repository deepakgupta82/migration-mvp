/**
 * Unified Graph Data Types
 * Normalized schema from backend unified graph endpoint
 */

export interface UnifiedNode {
  id: string;
  role: string; // Platform, Application, Server, Database, Discovery, Document, Environment, IP, OS, Storage, Entity, FactCluster
  display: string;
  metrics?: {
    degree?: number;
    fact_count?: number;
  };
  cluster?: {
    size: number;
    sample: string[]; // Sample fact texts
  };
  level?: number; // For platform view (0-3 hierarchy)
  ring?: number; // For document view (radial distance)
  environment?: string;
  // Layout coordinates (added client-side)
  x?: number;
  y?: number;
  fx?: number | null; // Fixed position
  fy?: number | null;
}

export interface UnifiedEdge {
  source: string;
  target: string;
  rel_type: string;
  kind: "infra" | "data" | "provenance" | "semantic";
  directional: boolean;
}

export interface UnifiedGraph {
  project_id: string;
  view: string;
  nodes: UnifiedNode[];
  edges: UnifiedEdge[];
  warnings?: string[];
  meta?: {
    counts: {
      nodes: number;
      edges: number;
      clusters?: number;
    };
    truncated?: boolean;
    node_limit?: number;
  };
}

export interface GraphMetadata {
  project_id: string;
  roles: string[];
  categories: string[];
  environments: string[];
  documents: { id: string; filename: string }[];
}

export interface NeighborsResponse {
  project_id: string;
  origin_node_id: string;
  depth: number;
  nodes: UnifiedNode[];
  edges: UnifiedEdge[];
  meta: {
    counts: {
      nodes: number;
      edges: number;
    };
  };
}

export interface FactClusterResponse {
  cluster_id: string;
  entity_id: string;
  category: string;
  facts: Array<{
    id: string;
    text: string;
    confidence?: number;
    source_document?: string;
  }>;
  pagination: {
    offset: number;
    limit: number;
    returned: number;
  };
}

export type GraphViewType = "knowledge" | "infra" | "platform" | "environment" | "document";

export interface GraphFilters {
  roles: Set<string>;
  categories: Set<string>;
  environments: Set<string>;
  searchQuery: string;
}

export interface GraphState {
  view: GraphViewType;
  nodes: Map<string, UnifiedNode>;
  edges: Map<string, UnifiedEdge>;
  expandedClusters: Set<string>;
  expandedNodes: Set<string>;
  filters: GraphFilters;
  selection: string | null;
  hover: string | null;
  focusMode: boolean;
  loading: boolean;
}
