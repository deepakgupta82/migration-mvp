/**
 * API Service Layer for Nagarro AgentiMigrate Platform
 * Centralized API calls for all backend services
 */

export const API_BASE_URL = process.env.REACT_APP_API_URL || '';
const PROJECT_SERVICE_URL = process.env.REACT_APP_PROJECT_SERVICE_URL || 'http://localhost:8002';
const STATS_SERVICE_URL = process.env.REACT_APP_STATS_SERVICE_URL || 'http://localhost:8004';
const DOCUMENT_SERVICE_URL = process.env.REACT_APP_DOCUMENT_SERVICE_URL || 'http://localhost:8003';

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

// API Service Class
class ApiService {
  // Generate a correlation ID for tracking requests
  private generateCorrelationId(): string {
    return `ui-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
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
    return this.request<Project[]>(`${PROJECT_SERVICE_URL}/projects${param}`);
  }

  async getProject(projectId: string): Promise<Project> {
    return this.request<Project>(`${PROJECT_SERVICE_URL}/projects/${projectId}`);
  }

  async createProject(project: Omit<Project, 'id' | 'created_at' | 'updated_at' | 'status'>): Promise<Project> {
    // Ensure required fields for project-service
    const payload: any = {
      ...project,
      client_name: (project as any).client_name ?? (project as any).name,
    };
    return this.request<Project>(`${PROJECT_SERVICE_URL}/projects/`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async updateProject(projectId: string, updates: Partial<Project>): Promise<Project> {
    // Use project-service endpoint
    return this.request<Project>(`${PROJECT_SERVICE_URL}/projects/${projectId}`, {
      method: 'PUT',
      body: JSON.stringify(updates),
    });
  }

  async deleteProject(projectId: string): Promise<void> {
    // Use project-service endpoint
    await this.request(`${PROJECT_SERVICE_URL}/projects/${projectId}`, {
      method: 'DELETE',
    });
  }

  // Project Files APIs
  async getProjectFiles(projectId: string): Promise<ProjectFile[]> {
    // Use project-service files endpoint
    const files = await this.request<ProjectFile[]>(`${PROJECT_SERVICE_URL}/api/projects/${projectId}/files`);
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
    return this.request<ProjectFile>(`${PROJECT_SERVICE_URL}/projects/${projectId}/files`, {
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

  // Assessment WebSocket Connection
  createAssessmentWebSocket(projectId: string): WebSocket {
    const wsUrl = `ws://localhost:8000/ws/run_assessment/${projectId}`;
    return new WebSocket(wsUrl);
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
    return this.request(`${STATS_SERVICE_URL}/api/stats/platform`, options);
  }

  async getAllProjectStats(): Promise<{
    status: string;
    data: {
      projects: ProjectStatsDetailed[];
      total_count: number;
    };
    timestamp: string;
  }> {
    return this.request(`${STATS_SERVICE_URL}/api/stats/projects`);
  }

  async getProjectStats(projectId: string, options: RequestInit = {}): Promise<{
    status: string;
    data: ProjectStatsDetailed;
    timestamp: string;
  }> {
    return this.request(`${STATS_SERVICE_URL}/api/stats/projects/${projectId}`, options);
  }

  // WebSocket connection helpers
  createPlatformStatsWebSocket(): WebSocket {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = STATS_SERVICE_URL.replace(/^https?:\/\//, '');
    return new WebSocket(`${protocol}//${host}/ws/platform-stats`);
  }

  createProjectStatsWebSocket(projectId: string): WebSocket {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = STATS_SERVICE_URL.replace(/^https?:\/\//, '');
    return new WebSocket(`${protocol}//${host}/ws/project-stats/${projectId}`);
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
    return this.request(`${STATS_SERVICE_URL}/api/stats/projects/${projectId}/events/document-processed`, {
      method: 'POST',
      body: JSON.stringify(documentInfo)
    });
  }

  async triggerEmbeddingsUpdated(projectId: string, embeddingsInfo: any): Promise<any> {
    return this.request(`${STATS_SERVICE_URL}/api/stats/projects/${projectId}/events/embeddings-updated`, {
      method: 'POST',
      body: JSON.stringify(embeddingsInfo)
    });
  }

  async updateAssessmentStatus(projectId: string, status: string): Promise<any> {
    return this.request(`${STATS_SERVICE_URL}/api/stats/projects/${projectId}/events/assessment-status`, {
      method: 'POST',
      body: JSON.stringify({ status })
    });
  }

  async updateServiceHealth(serviceName: string, status: string): Promise<any> {
    return this.request(`${STATS_SERVICE_URL}/api/stats/services/${serviceName}/health`, {
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
    return this.request(`${DOCUMENT_SERVICE_URL}/api/documents/${projectId}/search`, {
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
    return this.request(`${DOCUMENT_SERVICE_URL}/api/documents/${projectId}/content/${encodeURIComponent(filename)}`);
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
    return this.request(`${DOCUMENT_SERVICE_URL}/api/documents/${projectId}/analyze/${encodeURIComponent(filename)}`, {
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
    return this.request(`${DOCUMENT_SERVICE_URL}/api/documents/${projectId}/insights`);
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
    return this.request(`${DOCUMENT_SERVICE_URL}/api/documents/${projectId}/llm-analyze/${encodeURIComponent(filename)}`, {
      method: 'POST',
      body: JSON.stringify({
        analysis_type: analysisType,
        force_reanalysis: false,
        include_raw_analysis: false
      })
    });
  }
}

// Export singleton instance
export const apiService = new ApiService();
export default apiService;
