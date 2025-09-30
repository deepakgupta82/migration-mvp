import { API_BASE_URL } from './api';

export type ExplorerOverview = {
  project_id: string;
  entity_count: number;
  relationship_count: number;
  top_entity_types: { type: string; count: number }[];
  top_relationship_types: { type: string; count: number }[];
};

export type FusedSearchItem = {
  id: string;
  name?: string;
  text?: string;
  fused_score: number;
  sources: { source: string; rank: number; score: number }[];
};

export type CanonicalCentrality = {
  project_id: string;
  count: number;
  items: Array<{
    id: string;
    name: string;
    out_degree: number;
    in_degree: number;
    total_degree: number;
    normalized_total_degree?: number;
  }>;
};

export class GraphService {
  private authHeaders() {
    return {
      'Authorization': 'Bearer service-backend-token',
      'Content-Type': 'application/json',
    } as Record<string, string>;
  }

  async getExplorerOverview(projectId: string): Promise<ExplorerOverview> {
    // Try API gateway first then fallback to direct graph-service
    try {
      const res = await fetch(`${API_BASE_URL}/api/graphs/projects/${projectId}/explorer/overview`, { headers: this.authHeaders() });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch {
      const res = await fetch(`http://localhost:8006/projects/${projectId}/explorer/overview`, { headers: this.authHeaders() });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    }
  }

  async fusedSearch(projectId: string, params: {
    q: string;
    kinds?: string[]; // entity_cards,raw_chunks,triple_cards
    k?: number;
    use_hybrid?: boolean;
    boost_centrality?: boolean;
    weights?: string; // CSV entity_cards:1.0,raw_chunks:0.8
    centrality_scale?: number; // 0..1
    normalized_centrality?: boolean;
  }): Promise<{ project_id: string; query: string; count: number; items: FusedSearchItem[] }> {
    const searchParams = new URLSearchParams({ q: params.q });
    if (params.kinds?.length) searchParams.set('kinds', params.kinds.join(','));
    if (typeof params.k === 'number') searchParams.set('k', String(params.k));
    if (typeof params.use_hybrid === 'boolean') searchParams.set('use_hybrid', String(params.use_hybrid));
    if (typeof params.boost_centrality === 'boolean') searchParams.set('boost_centrality', String(params.boost_centrality));
    if (params.weights) searchParams.set('weights', params.weights);
    if (typeof params.centrality_scale === 'number') searchParams.set('centrality_scale', String(params.centrality_scale));
    if (typeof params.normalized_centrality === 'boolean') searchParams.set('normalized_centrality', String(params.normalized_centrality));

    // Try gateway route first;
    try {
      const res = await fetch(`${API_BASE_URL}/api/graphs/projects/${projectId}/search/fuse?${searchParams.toString()}`, { headers: this.authHeaders() });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch {
      const res = await fetch(`http://localhost:8006/projects/${projectId}/search/fuse?${searchParams.toString()}`, { headers: this.authHeaders() });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    }
  }

  async runPhases(projectId: string, options?: {
    dry_run?: boolean;
    min_score?: number;
    max_candidates?: number;
    preferred_kind?: string;
    use_hybrid?: boolean;
    min_support?: number;
    max_pairs?: number;
    allow_types?: string[];
  }): Promise<{
    project_id: string;
    dry_run: boolean;
    refers_to: any;
    canonical_relationships: any;
  }> {
    const params = new URLSearchParams();
    if (typeof options?.dry_run === 'boolean') params.set('dry_run', String(options.dry_run));
    if (typeof options?.min_score === 'number') params.set('min_score', String(options.min_score));
    if (typeof options?.max_candidates === 'number') params.set('max_candidates', String(options.max_candidates));
    if (options?.preferred_kind) params.set('preferred_kind', options.preferred_kind);
    if (typeof options?.use_hybrid === 'boolean') params.set('use_hybrid', String(options.use_hybrid));
    if (typeof options?.min_support === 'number') params.set('min_support', String(options.min_support));
    if (typeof options?.max_pairs === 'number') params.set('max_pairs', String(options.max_pairs));
    if (options?.allow_types?.length) params.set('allow_types', options.allow_types.join(','));

    const headers = { ...this.authHeaders(), 'X-Project-Id': projectId };

    // Try API gateway path first, then fallback to service direct
    try {
      const res = await fetch(`${API_BASE_URL}/api/graphs/projects/${projectId}/maintenance/run-phases?${params.toString()}`, {
        method: 'POST',
        headers,
      });
      if (!res.ok) {
        const body = await safeReadBody(res);
        throw new Error(`HTTP ${res.status}${body ? `: ${body}` : ''}`);
      }
      return await res.json();
    } catch {
      const res = await fetch(`http://localhost:8006/projects/${projectId}/maintenance/run-phases?${params.toString()}`, {
        method: 'POST',
        headers,
      });
      if (!res.ok) {
        const body = await safeReadBody(res);
        throw new Error(`HTTP ${res.status}${body ? `: ${body}` : ''}`);
      }
      return await res.json();
    }
  }

  async getCanonicalCentrality(projectId: string, limit: number = 100): Promise<CanonicalCentrality> {
    try {
      const res = await fetch(`${API_BASE_URL}/api/graphs/projects/${projectId}/canonical/centrality?limit=${encodeURIComponent(String(limit))}`, { headers: this.authHeaders() });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch {
      const res = await fetch(`http://localhost:8006/projects/${projectId}/canonical/centrality?limit=${encodeURIComponent(String(limit))}`, { headers: this.authHeaders() });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    }
  }

  async nl2cypher(projectId: string, body: { nl: string; limit?: number }): Promise<{ cypher: string; params?: any; warnings?: string[] }> {
    const headers = this.authHeaders();
    try {
      const res = await fetch(`${API_BASE_URL}/api/graphs/projects/${projectId}/query/nl2cypher`, {
        method: 'POST',
        headers,
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const msg = await safeReadBody(res);
        throw new Error(`HTTP ${res.status}${msg ? `: ${msg}` : ''}`);
      }
      return await res.json();
    } catch {
      const res = await fetch(`http://localhost:8006/projects/${projectId}/query/nl2cypher`, {
        method: 'POST',
        headers,
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const msg = await safeReadBody(res);
        throw new Error(`HTTP ${res.status}${msg ? `: ${msg}` : ''}`);
      }
      return await res.json();
    }
  }

  async runCypher(projectId: string, body: { cypher: string; limit?: number }): Promise<{ columns: string[]; rows: any[]; stats?: any }> {
    const headers = this.authHeaders();
    try {
      const res = await fetch(`${API_BASE_URL}/api/graphs/projects/${projectId}/query/run`, {
        method: 'POST',
        headers,
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const msg = await safeReadBody(res);
        throw new Error(`HTTP ${res.status}${msg ? `: ${msg}` : ''}`);
      }
      return await res.json();
    } catch {
      const res = await fetch(`http://localhost:8006/projects/${projectId}/query/run`, {
        method: 'POST',
        headers,
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const msg = await safeReadBody(res);
        throw new Error(`HTTP ${res.status}${msg ? `: ${msg}` : ''}`);
      }
      return await res.json();
    }
  }
}

export const graphService = new GraphService();
export default graphService;

async function safeReadBody(res: Response): Promise<string | null> {
  try {
    const text = await res.text();
    return text?.slice(0, 500) || null;
  } catch {
    return null;
  }
}
