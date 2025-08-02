/**
 * API Service Layer for Nagarro AgentiMigrate Platform
 * Centralized API calls for all backend services
 */

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';
const PROJECT_SERVICE_URL = process.env.REACT_APP_PROJECT_SERVICE_URL || 'http://localhost:8002';

// Types
export interface Project {
  id: string;
  name: string;
  description: string;
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
  id: string;
  filename: string;
  file_type?: string;
  file_size?: number;
  upload_timestamp: string;
  project_id: string;
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

export interface CrewConfiguration {
  agents: AgentDefinition[];
  tasks: TaskDefinition[];
  crews: CrewDefinition[];
  available_tools: AvailableTool[];
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

  // Project Management APIs
  async getProjects(): Promise<Project[]> {
    return this.request<Project[]>(`${PROJECT_SERVICE_URL}/projects`);
  }

  async getProject(projectId: string): Promise<Project> {
    return this.request<Project>(`${PROJECT_SERVICE_URL}/projects/${projectId}`);
  }

  async createProject(project: Omit<Project, 'id' | 'created_at' | 'updated_at' | 'status'>): Promise<Project> {
    return this.request<Project>(`${PROJECT_SERVICE_URL}/projects`, {
      method: 'POST',
      body: JSON.stringify(project),
    });
  }

  async updateProject(projectId: string, updates: Partial<Project>): Promise<Project> {
    return this.request<Project>(`${PROJECT_SERVICE_URL}/projects/${projectId}`, {
      method: 'PUT',
      body: JSON.stringify(updates),
    });
  }

  async deleteProject(projectId: string): Promise<void> {
    await this.request(`${PROJECT_SERVICE_URL}/projects/${projectId}`, {
      method: 'DELETE',
    });
  }

  // Project Files APIs
  async getProjectFiles(projectId: string): Promise<ProjectFile[]> {
    return this.request<ProjectFile[]>(`${PROJECT_SERVICE_URL}/projects/${projectId}/files`);
  }

  async addProjectFile(projectId: string, filename: string, fileType?: string): Promise<ProjectFile> {
    return this.request<ProjectFile>(`${PROJECT_SERVICE_URL}/projects/${projectId}/files`, {
      method: 'POST',
      body: JSON.stringify({ filename, file_type: fileType }),
    });
  }

  // Dashboard APIs
  async getProjectStats(): Promise<ProjectStats> {
    return this.request<ProjectStats>(`${PROJECT_SERVICE_URL}/projects/stats`);
  }

  // Platform Settings APIs
  async getPlatformSettings(): Promise<PlatformSetting[]> {
    return this.request<PlatformSetting[]>(`${PROJECT_SERVICE_URL}/platform-settings`);
  }

  // Graph Visualization APIs
  async getProjectGraph(projectId: string): Promise<GraphData> {
    return this.request<GraphData>(`${API_BASE_URL}/api/projects/${projectId}/graph`);
  }

  // RAG Knowledge Query APIs
  async queryProjectKnowledge(projectId: string, question: string): Promise<QueryResponse> {
    return this.request<QueryResponse>(`${API_BASE_URL}/api/projects/${projectId}/query`, {
      method: 'POST',
      body: JSON.stringify({ question }),
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

    const response = await fetch(`${API_BASE_URL}/upload/${projectId}`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      throw new Error(`Upload failed: ${response.status} ${response.statusText}`);
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

  // Get current crew definitions
  async getCrewDefinitions(): Promise<CrewConfiguration> {
    const response = await fetch(`${API_BASE_URL}/api/crew-definitions`);
    if (!response.ok) {
      throw new Error(`Failed to fetch crew definitions: ${response.status} ${response.statusText}`);
    }
    const result = await response.json();
    return result.data;
  }

  // Update crew definitions
  async updateCrewDefinitions(config: CrewConfiguration): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/api/crew-definitions`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(config),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(`Failed to update crew definitions: ${errorData.detail || response.statusText}`);
    }
  }

  // Get available tools
  async getAvailableTools(): Promise<AvailableTool[]> {
    const response = await fetch(`${API_BASE_URL}/api/available-tools`);
    if (!response.ok) {
      throw new Error(`Failed to fetch available tools: ${response.status} ${response.statusText}`);
    }
    const result = await response.json();
    return result.data;
  }
}

// Export singleton instance
export const apiService = new ApiService();
export default apiService;
