/**
 * API Service Layer for Nagarro AgentiMigrate Platform
 * Centralized API calls for all backend services with dynamic service discovery
 */

import { serviceDiscoveryClient } from './serviceDiscoveryClient';

export const API_BASE_URL = process.env.REACT_APP_API_URL || '';
// Keep environment variables as fallbacks for backward compatibility
const PROJECT_SERVICE_URL_FALLBACK = process.env.REACT_APP_PROJECT_SERVICE_URL || 'http://localhost:8002';
const STATS_SERVICE_URL_FALLBACK = process.env.REACT_APP_STATS_SERVICE_URL || 'http://localhost:8004';
const DOCUMENT_SERVICE_URL_FALLBACK = process.env.REACT_APP_DOCUMENT_SERVICE_URL || 'http://localhost:8003';

// Types
export interface Project {
  id: string;
  name: string;
  description: string;
  rfp?: string;
  timeline?: string;
  client_name: string;
  client_contact: string;
  status: string;
  report_url?: string;
  report_content?: string;
  report_artifact_url?: string;
  // LLM configuration
  llm_provider?: string;
  llm_model?: string;
  llm_api_key_id?: string;
  llm_temperature?: string;
  llm_max_tokens?: string;
  created_at: string;
  updated_at: string;
}

export interface ProjectFile {
  id?: string;
  filename: string;
  file_type?: string;
  file_size?: number;
  upload_timestamp?: string;
  uploaded_at?: string;
  project_id?: string;
  processing_status?: 'pending' | 'processing' | 'completed' | 'failed';
}

export interface PlatformSetting {
  key: string;
  value: string;
  description?: string;
}

export interface ProjectStats {
  total_projects: number;
  active_projects: number;
  completed_assessments: number;
  average_risk_score?: number;
}

// Real-time Stats Types
export interface PlatformStats {
  platform: {
    total_projects: number;
    active_projects: number;
    total_documents: number;
    total_embeddings: number;
    total_graph_nodes: number;
    total_agents: number;
    active_assessments: number;
    last_updated: string;
  };
  services_health: Record<string, string>;
  performance_metrics: {
    avg_processing_time: number;
    total_processing_time: number;
    success_rate: number;
  };
}

export interface ProjectStatsDetailed {
  project_id: string;
  name: string;
  documents: {
    total: number;
    processed: number;
    processing: number;
    failed: number;
    pending: number;
  };
  embeddings: {
    total: number;
    status: string;
  };
  graph: {
    nodes: number;
    relationships: number;
    last_updated: string;
  };
  assessment: {
    status: string;
    score?: number;
    recommendations?: number;
    completed_at?: string;
  };
  processing_stats: {
    total_time: number;
    avg_doc_time: number;
    success_rate: number;
  };
  last_updated: string;
}

// Crew Management Types
export interface AgentDefinition {
  id: string;
  role: string;
  goal: string;
  backstory: string;
  tools: string[];
  allow_delegation: boolean;
  verbose: boolean;
}

export interface TaskDefinition {
  id: string;
  description: string;
  expected_output: string;
  agent: string;
}

export interface CrewDefinition {
  id: string;
  name: string;
  description: string;
  agents: string[];
  tasks: string[];
  process: string;
  memory: boolean;
  verbose: number;
}

export interface AvailableTool {
  id: string;
  name: string;
  description: string;
}

export interface CrewStatistics {
  agents_count: number;
  tasks_count: number;
  crews_count: number;
  tools_count: number;
}

export interface ValidationResult {
  errors: string[];
  warnings: string[];
}

export interface CrewConfiguration {
  agents: AgentDefinition[];
  tasks: TaskDefinition[];
  crews: CrewDefinition[];
  available_tools: AvailableTool[];
  statistics?: CrewStatistics;
  validation?: ValidationResult;
}

export interface GraphNode {
  id: string;
  label: string;
  type: string;
  properties: Record<string, any>;
}

export interface GraphEdge {
  source: string;
  target: string;
  label: string;
  properties: Record<string, any>;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  links?: GraphEdge[]; // For ForceGraph2D compatibility
}

export interface PyvisNode { id: string; label: string; group?: string; title?: string; value?: number }
export interface PyvisEdge { from: string; to: string; label?: string; title?: string; dashes?: boolean; value?: number }
export interface PyvisGraphData { project_id: string; nodes: PyvisNode[]; edges: PyvisEdge[]; timestamp?: string }

// ============================
// MULTI-VIEWPOINT GRAPH TYPES
// ============================

// Platform-Centric View Types
export interface PlatformCentricNode extends GraphNode {
  layer_type: 'Platform' | 'Application' | 'Server' | 'Details';
  hierarchy_level: number; // 0-3, where 0 is center (Platform) and 3 is outer (Details)
}

export interface PlatformCentricGraphData {
  project_id: string;
  nodes: PlatformCentricNode[];
  edges: GraphEdge[];
  links?: GraphEdge[];
  layers: {
    platforms: PlatformCentricNode[];
    applications: PlatformCentricNode[];
    servers: PlatformCentricNode[];
    details: PlatformCentricNode[];
  };
}

// Document Source View Types
export interface DocumentInfo {
  document_id: string;
  filename: string;
  entity_count: number;
}

export interface DocumentSourceGraphData {
  project_id: string;
  document_id: string;
  document_filename: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  links?: GraphEdge[];
  stats: {
    entity_count: number;
    relationship_count: number;
  };
}

export interface ProjectDocumentsResponse {
  project_id: string;
  documents: DocumentInfo[];
  count: number;
}

// Environment View Types
export interface EnvironmentNode extends GraphNode {
  environment: string | null;
}

export interface EnvironmentGraphData {
  project_id: string;
  environment: string | null;
  nodes: EnvironmentNode[];
  edges: GraphEdge[];
  links?: GraphEdge[];
  grouped_by_environment: Record<string, EnvironmentNode[]>;
  cross_environment_connections: Array<{
    from_node: string;
    to_node: string;
    from_environment: string | null;
    to_environment: string | null;
    relationship_type: string;
  }>;
}

export interface ProjectEnvironmentsResponse {
  project_id: string;
  environments: string[];
  count: number;
}

export interface QueryResponse {
  answer: string;
  project_id: string;
}

export interface ReportResponse {
  project_id: string;
  report_content: string;
}

export interface UploadedFile {
  filename: string;
  object_key?: string;
  size?: number;
  content_type?: string;
  status: 'uploaded' | 'failed';
  error?: string;
}

export interface UploadResponse {
  status: string;
  project_id: string;
  uploaded_files: UploadedFile[];
  summary?: {
    total: number;
    successful: number;
    failed: number;
  };
}

// ============================
// USAGE TRACKING TYPES
// ============================
export interface LLMCall {
  id?: string;
  project_id?: string;
  provider?: string;
  model?: string;
  prompt_tokens?: number;
  completion_tokens?: number;
  total_tokens?: number;
  cost_usd_cents?: number;
  duration_ms?: number;
  status?: string;
  correlation_id?: string;
  created_at?: string;
  meta?: Record<string, any>;
  prompt_text?: string;
  response_text?: string;
}

export interface AgentRun {
  id?: string;
  run_id?: string;
  project_id?: string;
  agent_name?: string;
  status?: string;
  started_at?: string;
  completed_at?: string;
  duration_ms?: number;
  correlation_id?: string;
  meta?: Record<string, any>;
}

export interface AgentEvent {
  id?: string;
  run_id?: string;
  project_id?: string;
  event_type?: string;
  message?: string;
  ts?: string;
  correlation_id?: string;
  meta?: Record<string, any>;
}

// API Service Class
class ApiService {
  private serviceDiscoveryEnabled: boolean = true;

  // Generate a correlation ID for tracking requests
  private generateCorrelationId(): string {
    return `ui-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * Initialize service discovery
   */
  public async initializeServiceDiscovery(): Promise<void> {
    try {
      await serviceDiscoveryClient.initialize();
      console.log('Service discovery initialized successfully');
    } catch (error) {
      console.warn('Service discovery initialization failed, falling back to environment variables:', error);
      this.serviceDiscoveryEnabled = false;
    }
  }

  /**
   * Get service URL dynamically with fallback
   */
  private async getServiceUrl(serviceName: string, fallbackUrl: string): Promise<string> {
    if (!this.serviceDiscoveryEnabled) {
      return fallbackUrl;
    }

    try {
      const service = await serviceDiscoveryClient.getService(serviceName);
      if (service && service.status === 'healthy') {
        return `http://${service.host}:${service.port}`;
      }
    } catch (error) {
      console.warn(`Failed to get ${serviceName} from service discovery, using fallback:`, error);
    }

    return fallbackUrl;
  }

  /**
   * Get project service URL
   */
  private async getProjectServiceUrl(): Promise<string> {
    return this.getServiceUrl('project-service', PROJECT_SERVICE_URL_FALLBACK);
  }

  /**
   * Get stats service URL
   */
  private async getStatsServiceUrl(): Promise<string> {
    return this.getServiceUrl('stats-service', STATS_SERVICE_URL_FALLBACK);
  }

  /**
   * Get document service URL
   */
  private async getDocumentServiceUrl(): Promise<string> {
    return this.getServiceUrl('document-service', DOCUMENT_SERVICE_URL_FALLBACK);
  }

  private getAuthHeaders(): Record<string, string> {
    // For now, use the service token for backend-to-frontend communication
    // In production, this should use proper user authentication
    const serviceToken = 'service-backend-token';
    const correlationId = this.generateCorrelationId();
    
    return {
      'Authorization': `Bearer ${serviceToken}`,
      'Content-Type': 'application/json',
      'X-Correlation-ID': correlationId,
    };
  }

  private async request<T>(url: string, options: RequestInit = {}): Promise<T> {
    const corrId = this.generateCorrelationId();
    
    try {
      console.log(`Making API request to: ${url} [${corrId}]`);
      const response = await fetch(url, {
        headers: {
          ...this.getAuthHeaders(),
          'X-Correlation-ID': corrId, // Override with request-specific correlation ID
          ...options.headers,
        },
        ...options,
      });

      console.log(`API response status: ${response.status} [${corrId}]`);

      if (!response.ok) {
        const errorText = await response.text();
        console.error(`API Error: ${response.status} ${response.statusText} [${corrId}]`, errorText);
        throw new Error(`API Error: ${response.status} ${response.statusText} [${corrId}]`);
      }

      const data = await response.json();
      console.log('API response data:', data, `[${corrId}]`);
      return data;
    } catch (error) {
      console.error(`API request failed [${corrId}]:`, error);
      throw error;
    }
  }

  // Project Management APIs - use project-service directly
  async getProjects(includeStats: boolean = false): Promise<Project[]> {
    const param = includeStats ? '?include_stats=true' : '';
    const baseUrl = await this.getProjectServiceUrl();
    return this.request<Project[]>(`${baseUrl}/projects${param}`);
  }

  async getProject(projectId: string): Promise<Project> {
    const baseUrl = await this.getProjectServiceUrl();
    return this.request<Project>(`${baseUrl}/projects/${projectId}`);
  }

  async createProject(project: Omit<Project, 'id' | 'created_at' | 'updated_at' | 'status'> & { configId?: string }): Promise<Project> {
    console.log('Starting project creation with data:', {
      name: project.name,
      client_name: (project as any).client_name,
      configId: (project as any).configId
    });

    // Ensure required fields for project-service
    const payload: any = {
      ...project,
      client_name: (project as any).client_name ?? (project as any).name,
    };

    // If configId is provided, fetch the LLM configuration and populate project fields
    if ((project as any).configId) {
      console.log('Fetching LLM configuration for configId:', (project as any).configId);
      try {
        const projectServiceUrl = await this.getProjectServiceUrl();
        console.log('Project service URL:', projectServiceUrl);

        const configUrl = `${projectServiceUrl}/llm-configurations/${(project as any).configId}`;
        console.log('Fetching config from URL:', configUrl);

        const configResponse = await this.request<{
          id: string;
          provider: string;
          model: string;
          temperature: string;
          max_tokens: string;
        }>(configUrl);

        console.log('Received LLM config response:', configResponse);

        // Populate project with LLM config values
        payload.llm_provider = configResponse.provider;
        payload.llm_model = configResponse.model;
        payload.llm_api_key_id = configResponse.id;
        payload.llm_temperature = configResponse.temperature;
        payload.llm_max_tokens = configResponse.max_tokens;

        console.log('Populated project with LLM config:', {
          provider: payload.llm_provider,
          model: payload.llm_model,
          api_key_id: payload.llm_api_key_id,
          temperature: payload.llm_temperature,
          max_tokens: payload.llm_max_tokens
        });
      } catch (error) {
        console.error('Failed to fetch LLM configuration for project creation:', error);
        // Don't throw here - let project creation proceed without LLM config
        console.warn('Proceeding with project creation without LLM configuration');
      }
    } else {
      console.log('No configId provided, proceeding without LLM configuration');
    }

    console.log('Final payload for project creation:', payload);

    try {
      const projectServiceUrl = await this.getProjectServiceUrl();
      const createUrl = `${projectServiceUrl}/projects/`;
      console.log('Creating project at URL:', createUrl);

      const result = await this.request<Project>(createUrl, {
        method: 'POST',
        body: JSON.stringify(payload),
      });

      console.log('Project created successfully:', result);
      return result;
    } catch (error) {
      console.error('Failed to create project:', error);
      throw error;
    }
  }

  async updateProject(projectId: string, updates: Partial<Project>): Promise<Project> {
    // Use project-service endpoint
    const baseUrl = await this.getProjectServiceUrl();
    return this.request<Project>(`${baseUrl}/projects/${projectId}`, {
      method: 'PUT',
      body: JSON.stringify(updates),
    });
  }

  async deleteProject(projectId: string): Promise<void> {
    // Use project-service endpoint
    const baseUrl = await this.getProjectServiceUrl();
    await this.request(`${baseUrl}/projects/${projectId}`, {
      method: 'DELETE',
    });
  }

  // Project Files APIs
  async getProjectFiles(projectId: string): Promise<ProjectFile[]> {
    // Use project-service files endpoint
    const baseUrl = await this.getProjectServiceUrl();
    const files = await this.request<ProjectFile[]>(`${baseUrl}/api/projects/${projectId}/files`);
    return files || [];
  }

  // New: Use backend object storage listing for uploaded files
  async getProjectUploads(projectId: string): Promise<ProjectFile[]> {
    const res = await this.request<{ project_id: string; files: any[]; count: number }>(
      `${API_BASE_URL}/api/projects/${projectId}/uploaded-files`
    );
    const nowIso = new Date().toISOString();
    return (res.files || []).map((item: any) => {
      if (typeof item === 'string') {
        return {
          id: item,
          filename: item,
          project_id: res.project_id,
          upload_timestamp: nowIso,
        } as ProjectFile;
      }
      const filename = (item.filename || item.key || item.name || item.object_key || '').toString();
      const file_type = item.file_type || item.content_type;
      const file_size = item.file_size ?? item.size;
      const uploaded_at = item.uploaded_at || item.timestamp || nowIso;
      return {
        id: filename || `${Math.random().toString(36).slice(2)}`,
        filename: filename?.split('/').pop() || filename,
        file_type,
        file_size,
        uploaded_at,
        project_id: res.project_id,
      } as ProjectFile;
    });
  }

  async addProjectFile(projectId: string, filename: string, fileType?: string, fileSize?: number): Promise<ProjectFile> {
    const baseUrl = await this.getProjectServiceUrl();
    return this.request<ProjectFile>(`${baseUrl}/projects/${projectId}/files`, {
      method: 'POST',
      body: JSON.stringify({ filename, file_type: fileType, file_size: fileSize }),
    });
  }

  async deleteProjectFile(projectId: string, fileId: string): Promise<any> {
    // Use the new complete deletion endpoint that handles storage, embeddings, and graph data
    return await this.request(`${API_BASE_URL}/api/projects/${projectId}/files/${fileId}`, {
      method: 'DELETE',
    });
  }

  async downloadFile(projectId: string, filename: string): Promise<ArrayBuffer> {
    // Adjust to existing backend download endpoint
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/download/${filename}`);
    if (!response.ok) {
      throw new Error(`Failed to download file: ${response.statusText}`);
    }
    return response.arrayBuffer();
  }

  // MinIO Directory Browser API
  async listProjectFiles(projectId: string, path: string = ''): Promise<{
    files: Array<{
      name: string;
      type: 'file' | 'directory';
      size?: number;
      last_modified?: string;
      path: string;
    }>;
    current_path: string;
  }> {
    const encodedPath = path ? `?path=${encodeURIComponent(path)}` : '';
    return this.request(`${API_BASE_URL}/api/projects/${projectId}/files/browse${encodedPath}`);
  }

  // Dashboard APIs (legacy - replaced by stats service)
  async getLegacyProjectStats(): Promise<ProjectStats> {
    return this.request<ProjectStats>(`${API_BASE_URL}/api/projects/stats`);
  }
  async getPlatformStatsFast(): Promise<any> {
    return this.request(`${API_BASE_URL}/api/platform/stats-fast`);
  }
  // Gateway-first platform stats (preferred). If /api/platform/stats isn't available,
  // we can use the fast snapshot endpoint as a proxy for now.
  async getPlatformStatsBackend(options: RequestInit = {}): Promise<any> {
    // Prefer a richer endpoint if present; fallback to fast snapshot
    try {
      return await this.request(`${API_BASE_URL}/api/platform/stats`, options);
    } catch (e) {
      return await this.request(`${API_BASE_URL}/api/platform/stats-fast`, options);
    }
  }
  async getProjectStatsSnapshot(projectId: string): Promise<any> {
    return this.request(`${API_BASE_URL}/api/projects/${projectId}/stats-snapshot`);
  }

  // Platform Settings APIs
  async getPlatformSettings(): Promise<PlatformSetting[]> {
    return this.request<PlatformSetting[]>(`${API_BASE_URL}/api/platform-settings`);
  }

  // Graph Visualization APIs
  async getProjectGraph(projectId: string, type?: string): Promise<GraphData> {
    const q = type ? `?type=${encodeURIComponent(type)}` : '';
    return this.request<GraphData>(`${API_BASE_URL}/api/projects/${projectId}/graph${q}`);
  }

  async getPyvisGraph(projectId: string): Promise<PyvisGraphData> {
    // Try gateway route first, then fallback directly to graph-service
    try {
      return await this.request<PyvisGraphData>(`${API_BASE_URL}/api/projects/${projectId}/pyvis`);
    } catch (e) {
      // Fallback to graph-service direct URL
      return await this.request<PyvisGraphData>(`http://localhost:8006/api/graphs/projects/${projectId}/pyvis`);
    }
  }

  async getUiMinimalGraph(projectId: string, options?: { includeTypes?: string[]; excludeTypes?: string[]; hideSystem?: boolean }): Promise<GraphData & { stats?: any; timestamp?: string }> {
    const params = new URLSearchParams();
    if (options?.includeTypes && options.includeTypes.length) params.set('include_types', options.includeTypes.join(','));
    if (options?.excludeTypes && options.excludeTypes.length) params.set('exclude_types', options.excludeTypes.join(','));
    if (options?.hideSystem === false) params.set('hide_system', 'false');
    const suffix = params.toString() ? `?${params.toString()}` : '';
    // Try gateway route first
    try {
      return await this.request<GraphData & { stats?: any; timestamp?: string }>(`${API_BASE_URL}/api/projects/${projectId}/graph/ui-minimal${suffix}`);
    } catch (e) {
      // Fallback to graph-service direct URL
      return await this.request<GraphData & { stats?: any; timestamp?: string }>(`http://localhost:8006/api/graphs/projects/${projectId}/graph/ui-minimal${suffix}`);
    }
  }

  // ============================
  // MULTI-VIEWPOINT GRAPH APIs
  // ============================

  /**
   * Get platform-centric hierarchical view of the graph
   * Returns a structured view with 4 layers: Platform (center) → Applications → Servers → Details (outer)
   */
  async getPlatformCentricGraph(projectId: string): Promise<PlatformCentricGraphData> {
    try {
      // Try gateway route first
      return await this.request<PlatformCentricGraphData>(`${API_BASE_URL}/api/projects/${projectId}/graph/platform-centric`);
    } catch (e) {
      // Fallback to graph-service direct URL
      return await this.request<PlatformCentricGraphData>(`http://localhost:8006/api/graphs/projects/${projectId}/graph/platform-centric`);
    }
  }

  /**
   * List all documents that have been processed for a project
   * Returns document metadata including filename and entity count
   */
  async getProjectDocuments(projectId: string): Promise<ProjectDocumentsResponse> {
    try {
      // Try gateway route first
      return await this.request<ProjectDocumentsResponse>(`${API_BASE_URL}/api/projects/${projectId}/documents`);
    } catch (e) {
      // Fallback to graph-service direct URL
      return await this.request<ProjectDocumentsResponse>(`http://localhost:8006/api/graphs/projects/${projectId}/documents`);
    }
  }

  /**
   * Get graph filtered by source document
   * Shows all entities and relationships extracted from a specific document
   */
  async getDocumentSourceGraph(projectId: string, documentId: string): Promise<DocumentSourceGraphData> {
    try {
      // Try gateway route first
      return await this.request<DocumentSourceGraphData>(`${API_BASE_URL}/api/projects/${projectId}/graph/by-document/${documentId}`);
    } catch (e) {
      // Fallback to graph-service direct URL
      return await this.request<DocumentSourceGraphData>(`http://localhost:8006/api/graphs/projects/${projectId}/graph/by-document/${documentId}`);
    }
  }

  /**
   * List all environments discovered in a project
   * Returns environment names (e.g., Development, Test, Production)
   */
  async getProjectEnvironments(projectId: string): Promise<ProjectEnvironmentsResponse> {
    try {
      // Try gateway route first
      return await this.request<ProjectEnvironmentsResponse>(`${API_BASE_URL}/api/projects/${projectId}/environments`);
    } catch (e) {
      // Fallback to graph-service direct URL
      return await this.request<ProjectEnvironmentsResponse>(`http://localhost:8006/api/graphs/projects/${projectId}/environments`);
    }
  }

  /**
   * Get graph grouped by environment
   * If environment parameter is provided, filters to that environment only
   * Also identifies cross-environment connections
   */
  async getEnvironmentGraph(projectId: string, environment?: string): Promise<EnvironmentGraphData> {
    const params = environment ? `?environment=${encodeURIComponent(environment)}` : '';
    try {
      // Try gateway route first
      return await this.request<EnvironmentGraphData>(`${API_BASE_URL}/api/projects/${projectId}/graph/by-environment${params}`);
    } catch (e) {
      // Fallback to graph-service direct URL
      return await this.request<EnvironmentGraphData>(`http://localhost:8006/api/graphs/projects/${projectId}/graph/by-environment${params}`);
    }
  }

  // RAG Knowledge Query APIs
  async queryProjectKnowledge(projectId: string, question: string, useLLM: boolean = false): Promise<QueryResponse> {
    // Prefer new chat endpoint that proxies to knowledge-service
    try {
      return await this.request<QueryResponse>(`${API_BASE_URL}/api/projects/${projectId}/chat`, {
        method: 'POST',
        body: JSON.stringify({ question, use_llm: useLLM }),
      });
    } catch (e) {
      // Fallback to legacy query endpoint
      return await this.request<QueryResponse>(`${API_BASE_URL}/api/projects/${projectId}/query`, {
        method: 'POST',
        body: JSON.stringify({ query: question, use_llm: useLLM }),
      });
    }
  }

  // Test LLM Connectivity
  async testProjectLLM(projectId: string): Promise<{
    status: string;
    provider: string;
    model: string;
    response?: string;
    error?: string;
    message: string;
  }> {
    return this.request(`${API_BASE_URL}/api/projects/${projectId}/test-llm`, {
      method: 'POST',
    });
  }

  // Alias for knowledge base queries
  async queryKnowledgeBase(projectId: string, question: string, useLLM: boolean = false): Promise<QueryResponse> {
    return this.queryProjectKnowledge(projectId, question, useLLM);
  }

  // Report APIs
  async getProjectReport(projectId: string): Promise<ReportResponse> {
    return this.request<ReportResponse>(`${API_BASE_URL}/api/projects/${projectId}/report`);
  }

  // Test LLM API
  async testLLM(provider: string, model: string, apiKeyId?: string): Promise<any> {
    return this.request(`${API_BASE_URL}/api/test-llm`, {
      method: 'POST',
      body: JSON.stringify({
        provider,
        model,
        apiKeyId
      })
    });
  }

  // File Upload API with proper response type
  async uploadFiles(projectId: string, files: File[]): Promise<UploadResponse> {
    const formData = new FormData();
    files.forEach((file) => {
      formData.append('files', file);
    });

    // For multipart uploads, only include Authorization header (let browser set Content-Type)
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/upload`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer service-backend-token`,
        // Do NOT include Content-Type - browser will set multipart/form-data automatically
      },
      body: formData,
    });

    if (!response.ok) {
      const errText = await response.text();
      throw new Error(`Upload failed: ${response.status} ${response.statusText} - ${errText}`);
    }

    return response.json();
  }

  // Process Selected Documents API (enhanced pipeline only)
  async processSelectedDocuments(projectId: string, filenames: string[]): Promise<any> {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/process-selected`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer service-backend-token`,
      },
      body: JSON.stringify({ file_names: filenames, reprocess: false }),
    });

    if (!response.ok) {
      const errText = await response.text();
      throw new Error(`Process selected failed: ${response.status} ${response.statusText} - ${errText}`);
    }

    return response.json();
  }

  // Assessment WebSocket Connection
  createAssessmentWebSocket(projectId: string): WebSocket {
    const wsUrl = `ws://localhost:8000/ws/run_assessment/${projectId}`;
    return new WebSocket(wsUrl);
  }

  // =====================================================================================
  // PROJECT CLEANUP / DERIVED DATA MANAGEMENT
  // =====================================================================================

  // Clear all embeddings for a project (vector-service)
  async clearProjectEmbeddings(projectId: string): Promise<any> {
    const baseUrl = await this.getServiceUrl('vector-service', 'http://localhost:8005');
    return this.request(`${baseUrl}/api/vectors/projects/${projectId}/collection`, {
      method: 'DELETE',
    });
  }

  // Clear the entire knowledge graph for a project (graph-service)
  async clearProjectGraph(projectId: string): Promise<any> {
    const baseUrl = await this.getServiceUrl('graph-service', 'http://localhost:8006');
    return this.request(`${baseUrl}/api/graphs/projects/${projectId}/graph`, {
      method: 'DELETE',
    });
  }

  // Cleanup a storage category for a project (storage-service)
  async cleanupStorageCategory(projectId: string, category: string): Promise<any> {
    const baseUrl = await this.getServiceUrl('storage-service', 'http://localhost:8010');
    return this.request(`${baseUrl}/api/storage/projects/${projectId}/cleanup/${encodeURIComponent(category)}`, {
      method: 'POST',
    });
  }

  // Clear all derived artifacts: embeddings, graph, structured and processed categories
  async clearAllDerived(projectId: string): Promise<{
    embeddings?: any;
    graph?: any;
    structured?: any;
    uploads_parsed?: any;
    uploads_canonical?: any;
    errors?: string[];
  }> {
    const result: any = { errors: [] as string[] };
    try {
      result.embeddings = await this.clearProjectEmbeddings(projectId);
    } catch (e: any) {
      result.errors.push(`embeddings: ${e?.message || e}`);
    }
    try {
      result.graph = await this.clearProjectGraph(projectId);
    } catch (e: any) {
      result.errors.push(`graph: ${e?.message || e}`);
    }
    try {
      result.structured = await this.cleanupStorageCategory(projectId, 'structured');
    } catch (e: any) {
      result.errors.push(`structured: ${e?.message || e}`);
    }
    try {
      result.uploads_parsed = await this.cleanupStorageCategory(projectId, 'uploads_parsed');
    } catch (e: any) {
      result.errors.push(`uploads_parsed: ${e?.message || e}`);
    }
    try {
      result.uploads_canonical = await this.cleanupStorageCategory(projectId, 'uploads_canonical');
    } catch (e: any) {
      result.errors.push(`uploads_canonical: ${e?.message || e}`);
    }
    return result;
  }

  // =====================================================================================
  // CREW MANAGEMENT API METHODS
  // =====================================================================================

  // Deprecated crew definition endpoints (backend not implemented). Keeping placeholders commented.
  // async getCrewDefinitions(): Promise<CrewConfiguration> {
  //   const result = await this.request<{ data: CrewConfiguration }>(`${API_BASE_URL}/api/crew-definitions`);
  //   return result.data;
  // }

  // async updateCrewDefinitions(config: CrewConfiguration): Promise<void> {
  //   await this.request(`${API_BASE_URL}/api/crew-definitions`, {
  //     method: 'PUT',
  //     body: JSON.stringify(config),
  //   });
  // }

  // async getAvailableTools(): Promise<AvailableTool[]> {
  //   const result = await this.request<{ data: AvailableTool[] }>(`${API_BASE_URL}/api/available-tools`);
  //   return result.data;
  // }

  // Crew configuration (new REST endpoints)
  async getCrewDefinitions(): Promise<CrewConfiguration & {timestamp?: string}> {
    const result = await this.request<any>(`${API_BASE_URL}/api/crew-config`);
    return {
      agents: result.config.agents || [],
      tasks: result.config.tasks || [],
      crews: result.config.crews || [],
      available_tools: result.config.available_tools || [],
      statistics: result.statistics,
      validation: result.validation,
      timestamp: result.timestamp
    };
  }
  async reloadCrewDefinitions(): Promise<any> {
    return this.request(`${API_BASE_URL}/api/crew-config/reload`, { method: 'POST' });
  }
  async updateCrewDefinitions(config: CrewConfiguration): Promise<any> {
    return this.request(`${API_BASE_URL}/api/crew-config`, { method: 'PUT', body: JSON.stringify({
      agents: config.agents,
      tasks: config.tasks,
      crews: config.crews,
      available_tools: config.available_tools
    })});
  }

  // Global template usage via backend proxy
  async getGlobalTemplateUsage(): Promise<any> {
    return this.request(`${API_BASE_URL}/api/template-usage/global`);
  }

  // Backend logs listing / tail
  async listLogServices(): Promise<{services: string[]}> {
    return this.request(`${API_BASE_URL}/api/logs`);
  }

  async tailLogs(service: string, tail: number = 200): Promise<{service: string; lines: string[]}> {
    return this.request(`${API_BASE_URL}/api/logs?service=${encodeURIComponent(service)}&tail=${tail}`);
  }

  // LLM config test & models (align with new backend endpoints)
  async testLLMConfig(configId?: string): Promise<any> {
    const q = configId ? `?config_id=${encodeURIComponent(configId)}` : '';
    return this.request(`${API_BASE_URL}/api/llm/test-llm-config${q}`);
  }
  async listProviderModels(provider: string, apiKey?: string): Promise<{provider: string; models: string[]}> {
    const q = apiKey ? `?api_key=${encodeURIComponent(apiKey)}` : '';
    return this.request(`${API_BASE_URL}/api/llm/models/${provider}${q}`);
  }

  // Provide available tools (extracted from crew config for now)
  async getAvailableTools(): Promise<AvailableTool[]> {
    const cfg = await this.getCrewDefinitions();
    return cfg.available_tools || [];
  }

  // Notification Service Methods
  async createNotification(userId: string, workspaceId: string, data: {
    notification_type: string;
    title: string;
    message: string;
    correlation_id?: string;
    metadata?: Record<string, any>;
  }): Promise<{ notification_id: string; message: string }> {
    return this.request(`http://localhost:8016/workspaces/${workspaceId}/notifications`, {
      method: 'POST',
      body: JSON.stringify({
        user_id: userId,
        ...data
      })
    });
  }

  async getUserNotifications(userId: string): Promise<{
    user_id: string;
    notifications: any[];
    total_notifications: number;
    unread_count: number;
  }> {
    return this.request(`http://localhost:8016/users/${userId}/notifications`);
  }

  async markNotificationAsRead(userId: string, notificationId: string): Promise<{ message: string }> {
    return this.request(`http://localhost:8016/users/${userId}/notifications/${notificationId}/read`, {
      method: 'POST'
    });
  }

  // ============================
  // STATS SERVICE METHODS
  // ============================

  async getPlatformStats(options: RequestInit = {}): Promise<PlatformStats> {
    const baseUrl = await this.getStatsServiceUrl();
    return this.request(`${baseUrl}/api/stats/platform`, options);
  }

  async getAllProjectStats(): Promise<{
    status: string;
    data: {
      projects: ProjectStatsDetailed[];
      total_count: number;
    };
    timestamp: string;
  }> {
    const baseUrl = await this.getStatsServiceUrl();
    return this.request(`${baseUrl}/api/stats/projects`);
  }

  async getProjectStats(projectId: string, options: RequestInit = {}): Promise<{
    status: string;
    data: ProjectStatsDetailed;
    timestamp: string;
  }> {
    const baseUrl = await this.getStatsServiceUrl();
    return this.request(`${baseUrl}/api/stats/projects/${projectId}`, options);
  }

  // WebSocket connection helpers
  createPlatformStatsWebSocket(): WebSocket {
    // Try to get service URL synchronously, fallback to environment variable
    const baseUrl = this.serviceDiscoveryEnabled ?
      this.getStatsServiceUrlSync() :
      STATS_SERVICE_URL_FALLBACK;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = baseUrl.replace(/^https?:\/\//, '');
    return new WebSocket(`${protocol}//${host}/ws/platform-stats`);
  }

  createProjectStatsWebSocket(projectId: string): WebSocket {
    // Try to get service URL synchronously, fallback to environment variable
    const baseUrl = this.serviceDiscoveryEnabled ?
      this.getStatsServiceUrlSync() :
      STATS_SERVICE_URL_FALLBACK;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = baseUrl.replace(/^https?:\/\//, '');
    return new WebSocket(`${protocol}//${host}/ws/project-stats/${projectId}`);
  }

  /**
   * Synchronous version of getStatsServiceUrl for WebSocket creation
   */
  private getStatsServiceUrlSync(): string {
    try {
      // Try to get from cache first
      const cached = serviceDiscoveryClient['cache'].get('stats-service');
      if (cached && serviceDiscoveryClient['isCacheValid'](cached)) {
        const service = cached.info;
        if (service && service.status === 'healthy') {
          return `http://${service.host}:${service.port}`;
        }
      }
    } catch (error) {
      console.warn('Failed to get cached stats service URL:', error);
    }

    // Fallback to environment variable
    return STATS_SERVICE_URL_FALLBACK;
  }

  // Backend WS fallbacks (via API gateway on :8000)
  createBackendPlatformStatsWebSocket(): WebSocket {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = API_BASE_URL.replace(/^https?:\/\//, '');
    return new WebSocket(`${protocol}//${host}/ws/platform-stats?token=service-backend-token`);
  }

  createBackendProjectStatsWebSocket(projectId: string): WebSocket {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = API_BASE_URL.replace(/^https?:\/\//, '');
    return new WebSocket(`${protocol}//${host}/ws/project-stats/${projectId}?token=service-backend-token`);
  }

  // Manual event triggers (for testing)
  async triggerDocumentProcessed(projectId: string, documentInfo: any): Promise<any> {
    const baseUrl = await this.getStatsServiceUrl();
    return this.request(`${baseUrl}/api/stats/projects/${projectId}/events/document-processed`, {
      method: 'POST',
      body: JSON.stringify(documentInfo)
    });
  }

  async triggerEmbeddingsUpdated(projectId: string, embeddingsInfo: any): Promise<any> {
    const baseUrl = await this.getStatsServiceUrl();
    return this.request(`${baseUrl}/api/stats/projects/${projectId}/events/embeddings-updated`, {
      method: 'POST',
      body: JSON.stringify(embeddingsInfo)
    });
  }

  async updateAssessmentStatus(projectId: string, status: string): Promise<any> {
    const baseUrl = await this.getStatsServiceUrl();
    return this.request(`${baseUrl}/api/stats/projects/${projectId}/events/assessment-status`, {
      method: 'POST',
      body: JSON.stringify({ status })
    });
  }

  async updateServiceHealth(serviceName: string, status: string): Promise<any> {
    const baseUrl = await this.getStatsServiceUrl();
    return this.request(`${baseUrl}/api/stats/services/${serviceName}/health`, {
      method: 'POST',
      body: JSON.stringify({ status })
    });
  }

  // =====================================================================================
  // KNOWLEDGE BASE API METHODS
  // =====================================================================================

  // Knowledge discoveries (facts extracted from documents)
  async getProjectDiscoveries(projectId: string, category?: string): Promise<{
    project_id: string;
    discoveries: Array<{
      id: string;
      text: string;
      category: string;
      confidence: number;
      source_document: string;
      extracted_at: string;
      project_id: string;
    }>;
    total_count: number;
    categories: Record<string, number>;
    timestamp: string;
  }> {
    const query = category ? `?category=${encodeURIComponent(category)}` : '';
    return this.request(`${API_BASE_URL}/api/projects/${projectId}/discoveries${query}`);
  }

  // Search discoveries
  async searchProjectDiscoveries(projectId: string, query: string): Promise<{
    results: Array<{
      id: string;
      text: string;
      category: string;
      confidence: number;
      source_document: string;
      extracted_at: string;
      project_id: string;
    }>;
    total_count: number;
    search_query: string;
    timestamp: string;
  }> {
    return this.request(`${API_BASE_URL}/api/projects/${projectId}/discoveries/search?q=${encodeURIComponent(query)}`);
  }

  // =====================================================================================
  // DOCUMENT CONTENT SEARCH API METHODS (PHASE 4)
  // =====================================================================================

  // Search within document content
  async searchDocumentContent(
    projectId: string,
    query: string,
    searchType: string = 'comprehensive',
    limit: number = 20,
    includeContent: boolean = false,
    filters?: Record<string, any>
  ): Promise<{
    project_id: string;
    query: string;
    search_type: string;
    total_results: number;
    results: Array<{
      filename: string;
      relevance_score: number;
      search_type: string;
      matched_content?: string;
      summary?: string;
      categories: string[];
      document_type?: string;
      content_length: number;
      last_updated?: string;
      metadata?: Record<string, any>;
    }>;
    search_timestamp: string;
    processing_time: number;
    filters_applied?: Record<string, any>;
  }> {
    const baseUrl = await this.getDocumentServiceUrl();
    return this.request(`${baseUrl}/api/documents/${projectId}/search`, {
      method: 'POST',
      body: JSON.stringify({
        query,
        search_type: searchType,
        limit,
        include_content: includeContent,
        filters
      })
    });
  }

  // =====================================================================================
  // DOCUMENT CONTENT ANALYSIS API METHODS (PHASE 3)
  // =====================================================================================

  // Get document content details
  async getDocumentContentDetails(projectId: string, filename: string): Promise<{
    project_id: string;
    filename: string;
    content?: string;
    summary?: string;
    categories: string[];
    structure_metadata?: Record<string, any>;
    processing_status: string;
    last_updated?: string;
    content_length: number;
    has_structured_data: boolean;
  }> {
    const baseUrl = await this.getDocumentServiceUrl();
    return this.request(`${baseUrl}/api/documents/${projectId}/content/${encodeURIComponent(filename)}`);
  }

  // Analyze document content
  async analyzeDocument(projectId: string, filename: string, analysisType: string = 'comprehensive', includeContent: boolean = false): Promise<{
    project_id: string;
    filename: string;
    analysis_id: string;
    analysis_type: string;
    summary?: string;
    categories: string[];
    key_insights: string[];
    structure_analysis?: Record<string, any>;
    content_preview?: string;
    processing_time: number;
    analysis_timestamp: string;
  }> {
    const baseUrl = await this.getDocumentServiceUrl();
    return this.request(`${baseUrl}/api/documents/${projectId}/analyze/${encodeURIComponent(filename)}`, {
      method: 'POST',
      body: JSON.stringify({
        analysis_type: analysisType,
        include_content: includeContent,
        force_reanalysis: false
      })
    });
  }

  // Get project content insights
  async getProjectContentInsights(projectId: string): Promise<{
    project_id: string;
    total_documents: number;
    analyzed_documents: number;
    top_categories: Array<{
      category: string;
      count: number;
    }>;
    content_summary?: string;
    document_types: Record<string, number>;
    insights: string[];
    last_updated?: string;
  }> {
    const baseUrl = await this.getDocumentServiceUrl();
    return this.request(`${baseUrl}/api/documents/${projectId}/insights`);
  }

  // LLM-enhanced document analysis
  async analyzeDocumentWithLLM(projectId: string, filename: string, analysisType: string = 'comprehensive'): Promise<{
    project_id: string;
    filename: string;
    analysis_type: string;
    final_summary: string;
    final_categories: string[];
    quality_score: number;
    processing_methods: string[];
    processing_time: number;
    cached: boolean;
    timestamp: string;
  }> {
    const baseUrl = await this.getDocumentServiceUrl();
    return this.request(`${baseUrl}/api/documents/${projectId}/llm-analyze/${encodeURIComponent(filename)}`, {
      method: 'POST',
      body: JSON.stringify({
        analysis_type: analysisType,
        force_reanalysis: false,
        include_raw_analysis: false
      })
    });
  }

  // =====================================================================================
  // JSONL ANALYSIS ENDPOINTS (PHASE 3 - Migration to JSONL-only)
  // =====================================================================================

  // Create new analysis result in JSONL format
  async createAnalysisResult(projectId: string, analysisData: {
    filename: string;
    analysis_type: string;
    summary?: string;
    categories: string[];
    key_insights: string[];
    structure_analysis?: Record<string, any>;
    content_preview?: string;
    quality_score?: number;
    processing_time: number;
    metadata?: Record<string, any>;
  }): Promise<{
    analysis_id: string;
    project_id: string;
    filename: string;
    analysis_type: string;
    created_at: string;
    status: string;
  }> {
    const baseUrl = await this.getDocumentServiceUrl();
    return this.request(`${baseUrl}/api/documents/${projectId}/analysis`, {
      method: 'POST',
      body: JSON.stringify(analysisData)
    });
  }


  // Retrieve specific analysis result
  async getAnalysisResult(projectId: string, analysisId: string): Promise<{
    analysis_id: string;
    project_id: string;
    filename: string;
    analysis_type: string;
    summary?: string;
    categories: string[];
    key_insights: string[];
    structure_analysis?: Record<string, any>;
    content_preview?: string;
    quality_score?: number;
    processing_time: number;
    analysis_timestamp: string;
    metadata?: Record<string, any>;
    versions?: Array<{
      version_number: number;
      created_at: string;
      changes: string[];
    }>;
  }> {
    const baseUrl = await this.getDocumentServiceUrl();
    return this.request(`${baseUrl}/api/documents/${projectId}/analysis/${analysisId}`);
  }

  // List analysis results for project with filtering
  async listAnalysisResults(projectId: string, filters?: {
    filename?: string;
    analysis_type?: string;
    category?: string;
    quality_score_min?: number;
    quality_score_max?: number;
    date_from?: string;
    date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<{
    results: Array<{
      analysis_id: string;
      project_id: string;
      filename: string;
      analysis_type: string;
      summary?: string;
      categories: string[];
      quality_score?: number;
      processing_time: number;
      analysis_timestamp: string;
      metadata?: Record<string, any>;
    }>;
    total_count: number;
    filters_applied: Record<string, any>;
    timestamp: string;
  }> {
    const baseUrl = await this.getDocumentServiceUrl();
    const queryParams = filters ? new URLSearchParams(filters as any).toString() : '';
    const url = queryParams ? `${baseUrl}/api/documents/${projectId}/analysis?${queryParams}` : `${baseUrl}/api/documents/${projectId}/analysis`;
    return this.request(url);
  }

  // Update existing analysis result
  async updateAnalysisResult(projectId: string, analysisId: string, updates: {
    summary?: string;
    categories?: string[];
    key_insights?: string[];
    structure_analysis?: Record<string, any>;
    content_preview?: string;
    quality_score?: number;
    metadata?: Record<string, any>;
  }): Promise<{
    analysis_id: string;
    project_id: string;
    filename: string;
    updated_at: string;
    changes: string[];
  }> {
    const baseUrl = await this.getDocumentServiceUrl();
    return this.request(`${baseUrl}/api/documents/${projectId}/analysis/${analysisId}`, {
      method: 'PUT',
      body: JSON.stringify(updates)
    });
  }

  // Delete analysis result
  async deleteAnalysisResult(projectId: string, analysisId: string): Promise<{
    analysis_id: string;
    project_id: string;
    deleted_at: string;
    message: string;
  }> {
    const baseUrl = await this.getDocumentServiceUrl();
    return this.request(`${baseUrl}/api/documents/${projectId}/analysis/${analysisId}`, {
      method: 'DELETE'
    });
  }

  // Create and start batch analysis operation
  async createBatchAnalysis(projectId: string, batchData: {
    filenames: string[];
    analysis_type: string;
    priority?: 'low' | 'normal' | 'high';
    metadata?: Record<string, any>;
  }): Promise<{
    batch_id: string;
    project_id: string;
    analysis_type: string;
    total_files: number;
    status: string;
    created_at: string;
    estimated_completion?: string;
  }> {
    const baseUrl = await this.getDocumentServiceUrl();
    return this.request(`${baseUrl}/api/documents/${projectId}/analysis/batch`, {
      method: 'POST',
      body: JSON.stringify(batchData)
    });
  }

  // Get batch analysis status and results
  async getBatchAnalysisStatus(projectId: string, batchId: string): Promise<{
    batch_id: string;
    project_id: string;
    analysis_type: string;
    status: string;
    progress_percentage: number;
    total_files: number;
    completed_files: number;
    failed_files: number;
    results: Array<{
      analysis_id: string;
      filename: string;
      status: string;
      error_message?: string;
      processing_time?: number;
    }>;
    created_at: string;
    started_at?: string;
    completed_at?: string;
    estimated_completion?: string;
  }> {
    const baseUrl = await this.getDocumentServiceUrl();
    return this.request(`${baseUrl}/api/documents/${projectId}/analysis/batch/${batchId}`);
  }

  // List analysis batches for project
  async listAnalysisBatches(projectId: string, filters?: {
    status?: string;
    analysis_type?: string;
    date_from?: string;
    date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<{
    batches: Array<{
      batch_id: string;
      project_id: string;
      analysis_type: string;
      status: string;
      total_files: number;
      completed_files: number;
      failed_files: number;
      created_at: string;
      completed_at?: string;
    }>;
    total_count: number;
    filters_applied: Record<string, any>;
    timestamp: string;
  }> {
    const baseUrl = await this.getDocumentServiceUrl();
    const queryParams = filters ? new URLSearchParams(filters as any).toString() : '';
    const url = queryParams ? `${baseUrl}/api/documents/${projectId}/analysis/batches?${queryParams}` : `${baseUrl}/api/documents/${projectId}/analysis/batches`;
    return this.request(url);
  }

  // Create new version of analysis result
  async createAnalysisVersion(projectId: string, analysisId: string, versionData: {
    changes_description: string;
    updated_data: {
      summary?: string;
      categories?: string[];
      key_insights?: string[];
      structure_analysis?: Record<string, any>;
      content_preview?: string;
      quality_score?: number;
      metadata?: Record<string, any>;
    };
  }): Promise<{
    analysis_id: string;
    version_number: number;
    created_at: string;
    changes: string[];
  }> {
    const baseUrl = await this.getDocumentServiceUrl();
    return this.request(`${baseUrl}/api/documents/${projectId}/analysis/${analysisId}/version`, {
      method: 'POST',
      body: JSON.stringify(versionData)
    });
  }

  // List all versions of analysis result
  async listAnalysisVersions(projectId: string, analysisId: string): Promise<{
    analysis_id: string;
    versions: Array<{
      version_number: number;
      created_at: string;
      changes: string[];
      created_by?: string;
    }>;
    current_version: number;
    total_versions: number;
  }> {
    const baseUrl = await this.getDocumentServiceUrl();
    return this.request(`${baseUrl}/api/documents/${projectId}/analysis/${analysisId}/versions`);
  }

  // Get specific version of analysis result
  async getAnalysisVersion(projectId: string, analysisId: string, versionNumber: number): Promise<{
    analysis_id: string;
    version_number: number;
    project_id: string;
    filename: string;
    analysis_type: string;
    summary?: string;
    categories: string[];
    key_insights: string[];
    structure_analysis?: Record<string, any>;
    content_preview?: string;
    quality_score?: number;
    processing_time: number;
    analysis_timestamp: string;
    metadata?: Record<string, any>;
    created_at: string;
    changes: string[];
  }> {
    const baseUrl = await this.getDocumentServiceUrl();
    return this.request(`${baseUrl}/api/documents/${projectId}/analysis/${analysisId}/version/${versionNumber}`);
  }

  // =====================================================================================
  // ASYNC LLM ANALYSIS METHODS (NEW)
  // =====================================================================================

  // Get analysis status for a specific analysis batch
  async getAnalysisStatus(projectId: string, analysisId: string): Promise<{
    project_id: string;
    analysis_id: string;
    total_files: number;
    status: 'started' | 'completed' | 'failed';
    started_at: string;
    completed_at?: string;
    results: Array<{
      filename: string;
      status: string;
      analysis_id?: string;
      processing_time?: number;
      error?: string;
    }>;
    summary_stats: {
      successful_analyses: number;
      failed_analyses: number;
      average_quality_score: number;
      total_processing_time: number;
    };
  }> {
    const baseUrl = await this.getDocumentServiceUrl();
    return this.request(`${baseUrl}/api/documents/${projectId}/analysis-status/${analysisId}`);
  }

  // Get analysis status for all documents in a project
  async getDocumentsAnalysisStatus(projectId: string): Promise<{
    project_id: string;
    documents: Array<{
      filename: string;
      analysis_status: 'not_analyzed' | 'analysis_pending' | 'analyzing' | 'analysis_complete' | 'analysis_failed';
      analysis_id?: string;
      last_updated?: string;
    }>;
    total_documents: number;
    analysis_pending: number;
    analyzing: number;
    analysis_complete: number;
    analysis_failed: number;
    not_analyzed: number;
  }> {
    const baseUrl = await this.getDocumentServiceUrl();
    return this.request(`${baseUrl}/api/documents/${projectId}/documents/analysis-status`);
  }

  // =====================================================================================
  // AUTOGEN CONVERSATION API METHODS
  // =====================================================================================

  // Get available AutoGen agents
  async getAutoGenAgents(): Promise<{
    available_agents: Record<string, string>;
    total_count: number;
  }> {
    // Use service discovery to find ai-agent-service
    try {
      const service = await serviceDiscoveryClient.getService('ai-agent-service');
      if (service && service.status === 'healthy') {
        const baseUrl = `http://${service.host}:${service.port}`;
        return this.request(`${baseUrl}/api/autogen/agents`);
      }
    } catch (error) {
      console.warn('AutoGen service discovery failed, using fallback:', error);
    }

    // Fallback to direct URL
    return this.request('http://localhost:8008/api/autogen/agents');
  }

  // Start a new AutoGen discussion
  async startAutoGenDiscussion(data: {
    message: string;
    selected_agents?: string[];
    project_id: string;
    session_id?: string;
  }): Promise<{
    status: string;
    session_id: string;
    analysis: any;
    participating_agents: string[];
    result: any;
    gathered_context?: any;
    timestamp: string;
    error?: string;
  }> {
    try {
      const service = await serviceDiscoveryClient.getService('ai-agent-service');
      if (service && service.status === 'healthy') {
        const baseUrl = `http://${service.host}:${service.port}`;
        return this.request(`${baseUrl}/api/autogen/discussions/start`, {
          method: 'POST',
          body: JSON.stringify(data)
        });
      }
    } catch (error) {
      console.warn('AutoGen service discovery failed, using fallback:', error);
    }

    // Fallback to direct URL
    return this.request('http://localhost:8008/api/autogen/discussions/start', {
      method: 'POST',
      body: JSON.stringify(data)
    });
  }

  // Send follow-up message in AutoGen discussion
  async sendAutoGenFollowUp(sessionId: string, data: {
    message: string;
    session_id: string;
    override_agents?: string[];
    fetch_context?: boolean;
    project_id: string;
  }): Promise<{
    status: string;
    session_id: string;
    analysis: any;
    participating_agents: string[];
    result: any;
    gathered_context?: any;
    timestamp: string;
    error?: string;
  }> {
    try {
      const service = await serviceDiscoveryClient.getService('ai-agent-service');
      if (service && service.status === 'healthy') {
        const baseUrl = `http://${service.host}:${service.port}`;
        return this.request(`${baseUrl}/api/autogen/discussions/${sessionId}/query`, {
          method: 'POST',
          body: JSON.stringify(data)
        });
      }
    } catch (error) {
      console.warn('AutoGen service discovery failed, using fallback:', error);
    }

    // Fallback to direct URL
    return this.request(`http://localhost:8008/api/autogen/discussions/${sessionId}/query`, {
      method: 'POST',
      body: JSON.stringify(data)
    });
  }

  // Get AutoGen conversation history
  async getAutoGenConversationHistory(limit?: number): Promise<{
    status: string;
    total_conversations: number;
    limit: number;
    offset: number;
    sessions: Array<{
      session_id: string;
      created_at?: string;
      last_updated?: string;
      message_count?: number;
      participating_agents?: string[];
      status?: string;
    }>;
  }> {
    const query = limit ? `?limit=${limit}` : '';
    try {
      const service = await serviceDiscoveryClient.getService('ai-agent-service');
      if (service && service.status === 'healthy') {
        const baseUrl = `http://${service.host}:${service.port}`;
        return this.request(`${baseUrl}/api/autogen/conversations/history${query}`);
      }
    } catch (error) {
      console.warn('AutoGen service discovery failed, using fallback:', error);
    }

    // Fallback to direct URL
    return this.request(`http://localhost:8008/api/autogen/conversations/history${query}`);
  }

  // Get specific AutoGen conversation session history
  async getAutoGenSessionHistory(sessionId: string): Promise<{
    status: string;
    session_id: string;
    conversation_count: number;
    session?: any;
    messages: Array<{
      id: string;
      session_id: string;
      ts: string;
      source: string;
      content: string;
      message_type?: string;
      agent_name?: string;
    }>;
    conversations?: any[];
  }> {
    try {
      const service = await serviceDiscoveryClient.getService('ai-agent-service');
      if (service && service.status === 'healthy') {
        const baseUrl = `http://${service.host}:${service.port}`;
        return this.request(`${baseUrl}/api/autogen/conversations/${sessionId}/history`);
      }
    } catch (error) {
      console.warn('AutoGen service discovery failed, using fallback:', error);
    }

    // Fallback to direct URL
    return this.request(`http://localhost:8008/api/autogen/conversations/${sessionId}/history`);
  }

  // Create AutoGen WebSocket connection with enhanced error handling and reconnection
  createAutoGenWebSocket(sessionId: string): WebSocket {
    // Try to get service URL dynamically
    const createWebSocket = (baseUrl: string) => {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = baseUrl.replace(/^https?:\/\//, '');
      // Add authentication token and additional parameters for WebSocket
      const serviceToken = 'service-backend-token';
      const correlationId = this.generateCorrelationId();
      const wsUrl = `${protocol}//${host}/ws/autogen/${sessionId}?token=${encodeURIComponent(serviceToken)}&correlation_id=${correlationId}`;

      console.log('Creating AutoGen WebSocket connection to:', wsUrl);

      // Create WebSocket connection with enhanced configuration
      const ws = new WebSocket(wsUrl);

      // Enhanced event listeners with better error handling
      ws.onopen = (event) => {
        console.log('AutoGen WebSocket opened successfully for session:', sessionId, event);
        // Send initial ping to verify connection
        try {
          ws.send(JSON.stringify({ type: 'ping', timestamp: new Date().toISOString() }));
        } catch (error) {
          console.warn('Failed to send initial ping:', error);
        }
      };

      ws.onclose = (event) => {
        console.log('AutoGen WebSocket closed for session:', sessionId, 'Code:', event.code, 'Reason:', event.reason);
        // Log different close codes for debugging
        if (event.code === 1000) {
          console.log('WebSocket closed normally');
        } else if (event.code === 1006) {
          console.warn('WebSocket closed abnormally - possible network issue');
        } else if (event.code === 1011) {
          console.error('WebSocket closed due to server error');
        }
      };

      ws.onerror = (error) => {
        console.error('AutoGen WebSocket error for session:', sessionId, error);
        // Try to get more details about the error
        if (ws.readyState === WebSocket.CLOSED) {
          console.error('WebSocket is in CLOSED state');
        } else if (ws.readyState === WebSocket.CLOSING) {
          console.warn('WebSocket is in CLOSING state');
        }
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log('AutoGen WebSocket message received for session:', sessionId, data.type);
        } catch (error) {
          console.warn('Failed to parse WebSocket message:', event.data, error);
        }
      };

      return ws;
    };

    // Try service discovery first with better error handling
    try {
      const service = serviceDiscoveryClient['cache']?.get('ai-agent-service');
      if (service && serviceDiscoveryClient['isCacheValid']?.(service)) {
        const serviceInfo = service.info;
        if (serviceInfo && serviceInfo.status === 'healthy') {
          console.log('Using service discovery for AutoGen WebSocket:', serviceInfo.host, serviceInfo.port);
          return createWebSocket(`http://${serviceInfo.host}:${serviceInfo.port}`);
        } else {
          console.warn('AutoGen service found but not healthy:', serviceInfo?.status);
        }
      } else {
        console.warn('AutoGen service not found in cache or cache invalid');
      }
    } catch (error) {
      console.warn('AutoGen WebSocket service discovery failed:', error);
    }

    // Fallback to direct connection with better logging
    console.log('Falling back to direct AutoGen WebSocket connection');
    return createWebSocket('http://localhost:8008');
  }

  // ============================
  // USAGE TRACKING METHODS (via backend proxy with RBAC)
  // ============================
  async listLLMCalls(filters?: {
    project_id?: string;
    provider?: string;
    model?: string;
    correlation_id?: string;
    limit?: number;
    offset?: number;
  }): Promise<{ items: LLMCall[]; total?: number } | LLMCall[]> {
    const params = new URLSearchParams();
    if (filters?.project_id) params.set('project_id', filters.project_id);
    if (filters?.provider) params.set('provider', filters.provider);
    if (filters?.model) params.set('model', filters.model);
    if (filters?.correlation_id) params.set('correlation_id', filters.correlation_id);
    if (typeof filters?.limit === 'number') params.set('limit', String(filters.limit));
    if (typeof filters?.offset === 'number') params.set('offset', String(filters.offset));
    const q = params.toString() ? `?${params.toString()}` : '';
    return this.request(`${API_BASE_URL}/api/usage/llm-calls${q}`);
  }

  async listAgentRuns(filters?: {
    project_id?: string;
    correlation_id?: string;
    limit?: number;
    offset?: number;
  }): Promise<{ items: AgentRun[]; total?: number } | AgentRun[]> {
    const params = new URLSearchParams();
    if (filters?.project_id) params.set('project_id', filters.project_id);
    if (filters?.correlation_id) params.set('correlation_id', filters.correlation_id);
    if (typeof filters?.limit === 'number') params.set('limit', String(filters.limit));
    if (typeof filters?.offset === 'number') params.set('offset', String(filters.offset));
    const q = params.toString() ? `?${params.toString()}` : '';
    return this.request(`${API_BASE_URL}/api/usage/agent-runs${q}`);
  }

  async listAgentEvents(filters?: {
    run_id?: string;
    project_id?: string;
    correlation_id?: string;
    limit?: number;
    offset?: number;
  }): Promise<{ items: AgentEvent[]; total?: number } | AgentEvent[]> {
    const params = new URLSearchParams();
    if (filters?.run_id) params.set('run_id', filters.run_id);
    if (filters?.project_id) params.set('project_id', filters.project_id);
    if (filters?.correlation_id) params.set('correlation_id', filters.correlation_id);
    if (typeof filters?.limit === 'number') params.set('limit', String(filters.limit));
    if (typeof filters?.offset === 'number') params.set('offset', String(filters.offset));
    const q = params.toString() ? `?${params.toString()}` : '';
    return this.request(`${API_BASE_URL}/api/usage/agent-events${q}`);
  }
}

// Export singleton instance
export const apiService = new ApiService();
export default apiService;
