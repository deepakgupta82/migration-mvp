/**
 * API Service Layer for Nagarro AgentiMigrate Platform
 * Centralized API calls for all backend services
 */

const API_BASE_URL = process.env.REACT_APP_API_URL || (typeof window !== 'undefined' ? `${window.location.protocol}//${window.location.hostname}:8000` : 'http://localhost:8000');
const PROJECT_SERVICE_URL = process.env.REACT_APP_PROJECT_SERVICE_URL || 'http://localhost:8002';

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
  private getAuthHeaders(): Record<string, string> {
    // For now, use the service token for backend-to-frontend communication
    // In production, this should use proper user authentication
    const serviceToken = 'service-backend-token';
    return {
      'Authorization': `Bearer ${serviceToken}`,
      'Content-Type': 'application/json',
    };
  }

  private async request<T>(url: string, options: RequestInit = {}): Promise<T> {
    try {
      console.log(`Making API request to: ${url}`);
      const response = await fetch(url, {
        headers: {
          ...this.getAuthHeaders(),
          ...options.headers,
        },
        ...options,
      });

      console.log(`API response status: ${response.status}`);

      if (!response.ok) {
        const errorText = await response.text();
        console.error(`API Error: ${response.status} ${response.statusText}`, errorText);
        throw new Error(`API Error: ${response.status} ${response.statusText}`);
      }

      const data = await response.json();
      console.log('API response data:', data);
      return data;
    } catch (error) {
      console.error('API request failed:', error);
      throw error;
    }
  }

  // Project Management APIs - use backend consistently for LLM config consistency
  async getProjects(includeStats: boolean = false): Promise<Project[]> {
    const param = includeStats ? '?include_stats=true' : '';
    return this.request<Project[]>(`${API_BASE_URL}/api/projects${param}`);
  }

  async getProject(projectId: string): Promise<Project> {
    return this.request<Project>(`${API_BASE_URL}/api/projects/${projectId}`);
  }

  async createProject(project: Omit<Project, 'id' | 'created_at' | 'updated_at' | 'status'>): Promise<Project> {
    // Ensure required fields for gateway/project-service
    const payload: any = {
      ...project,
      client_name: (project as any).client_name ?? (project as any).name,
    };
    return this.request<Project>(`${API_BASE_URL}/api/projects/`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async updateProject(projectId: string, updates: Partial<Project>): Promise<Project> {
    // Use backend endpoint for consistency with getProject and createProject
    return this.request<Project>(`${API_BASE_URL}/api/projects/${projectId}`, {
      method: 'PUT',
      body: JSON.stringify(updates),
    });
  }

  async deleteProject(projectId: string): Promise<void> {
    // Use backend wrapper for consistent auth / future logic
    await this.request(`${API_BASE_URL}/api/projects/${projectId}`, {
      method: 'DELETE',
    });
  }

  // Project Files APIs
  async getProjectFiles(projectId: string): Promise<ProjectFile[]> {
    // Route via gateway to comply with architecture
    const res = await this.request<{ project_id: string; files: string[]; count: number }>(
      `${API_BASE_URL}/api/projects/${projectId}/uploaded-files`
    );
    const nowIso = new Date().toISOString();
    return (res.files || []).map((filename) => ({
      id: filename,
      filename,
      project_id: res.project_id,
      upload_timestamp: nowIso,
    } as ProjectFile));
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

  async deleteProjectFile(projectId: string, fileId: string): Promise<void> {
    await this.request(`${PROJECT_SERVICE_URL}/projects/${projectId}/files/${fileId}`, {
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

  // Dashboard APIs (legacy full stats retained for fallback)
  async getProjectStats(): Promise<ProjectStats> {
    return this.request<ProjectStats>(`${API_BASE_URL}/api/projects/stats`);
  }
  async getPlatformStatsFast(): Promise<any> {
    return this.request(`${API_BASE_URL}/api/platform/stats-fast`);
  }
  async getProjectStatsSnapshot(projectId: string): Promise<any> {
    return this.request(`${API_BASE_URL}/api/projects/${projectId}/stats-snapshot`);
  }

  // Platform Settings APIs
  async getPlatformSettings(): Promise<PlatformSetting[]> {
    return this.request<PlatformSetting[]>(`${API_BASE_URL}/api/platform-settings`);
  }

  // Graph Visualization APIs
  async getProjectGraph(projectId: string): Promise<GraphData> {
    return this.request<GraphData>(`${API_BASE_URL}/api/projects/${projectId}/graph`);
  }

  // RAG Knowledge Query APIs
  async queryProjectKnowledge(projectId: string, question: string): Promise<QueryResponse> {
    // Gateway expects { query }
    return this.request<QueryResponse>(`${API_BASE_URL}/api/projects/${projectId}/query`, {
      method: 'POST',
      body: JSON.stringify({ query: question }),
    });
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
  async queryKnowledgeBase(projectId: string, question: string): Promise<QueryResponse> {
    return this.queryProjectKnowledge(projectId, question);
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
}

// Export singleton instance
export const apiService = new ApiService();
export default apiService;
