/**
 * API client for unified graph endpoints
 */
import {
  UnifiedGraph,
  GraphMetadata,
  NeighborsResponse,
  FactClusterResponse,
  GraphViewType
} from '../types';

const GRAPH_SERVICE_URL = process.env.REACT_APP_GRAPH_SERVICE_URL || 'http://localhost:8006/api/graphs';

export async function fetchUnifiedGraph(
  projectId: string,
  view: GraphViewType,
  options: {
    environment?: string;
    documentId?: string;
    includeClusters?: boolean;
    includeRelated?: boolean;
    factSample?: number;
    nodeLimit?: number;
    factClusterMin?: number;
  } = {}
): Promise<UnifiedGraph> {
  const params = new URLSearchParams({
    view,
    include_clusters: String(options.includeClusters ?? true),
    include_related: String(options.includeRelated ?? true),
    fact_sample: String(options.factSample ?? 3),
    node_limit: String(options.nodeLimit ?? 800),
    fact_cluster_min: String(options.factClusterMin ?? 2),
  });

  if (options.environment) params.set('environment', options.environment);
  if (options.documentId) params.set('document_id', options.documentId);

  const response = await fetch(
    `${GRAPH_SERVICE_URL}/projects/${projectId}/graph/unified?${params}`,
    {
      headers: {
        Authorization: `Bearer ${localStorage.getItem('token') || 'service-backend-token'}`,
      },
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to fetch unified graph: ${response.statusText}`);
  }

  return response.json();
}

export async function fetchGraphMetadata(projectId: string): Promise<GraphMetadata> {
  const response = await fetch(
    `${GRAPH_SERVICE_URL}/projects/${projectId}/graph/metadata`,
    {
      headers: {
        Authorization: `Bearer ${localStorage.getItem('token') || 'service-backend-token'}`,
      },
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to fetch graph metadata: ${response.statusText}`);
  }

  return response.json();
}

export async function fetchNeighbors(
  projectId: string,
  nodeId: string,
  depth: number = 1,
  limit: number = 50
): Promise<NeighborsResponse> {
  const params = new URLSearchParams({
    depth: String(depth),
    limit: String(limit),
  });

  const response = await fetch(
    `${GRAPH_SERVICE_URL}/projects/${projectId}/graph/node/${encodeURIComponent(nodeId)}/neighbors?${params}`,
    {
      headers: {
        Authorization: `Bearer ${localStorage.getItem('token') || 'service-backend-token'}`,
      },
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to fetch neighbors: ${response.statusText}`);
  }

  return response.json();
}

export async function fetchFactCluster(
  projectId: string,
  clusterId: string,
  offset: number = 0,
  limit: number = 100
): Promise<FactClusterResponse> {
  const params = new URLSearchParams({
    offset: String(offset),
    limit: String(limit),
  });

  const response = await fetch(
    `${GRAPH_SERVICE_URL}/projects/${projectId}/graph/fact-cluster/${encodeURIComponent(clusterId)}?${params}`,
    {
      headers: {
        Authorization: `Bearer ${localStorage.getItem('token') || 'service-backend-token'}`,
      },
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to fetch fact cluster: ${response.statusText}`);
  }

  return response.json();
}
