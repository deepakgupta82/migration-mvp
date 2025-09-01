/**
 * Custom hooks for project data management
 */

import { useState, useEffect, useCallback } from 'react';
import { apiService, Project, ProjectStats, API_BASE_URL } from '../services/api';

export const useProjects = () => {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchProjects = useCallback(async () => {
    try {
      console.log('Fetching projects (include stats)...');
      setLoading(true);
      setError(null);
      const data = await apiService.getProjects(true);
      // Ensure data is always an array
      const safeData = Array.isArray(data) ? data : [];
      setProjects(safeData as any); // enriched objects contain files_count, embeddings_count, stats_stale
    } catch (err) {
      console.error('Error fetching projects:', err);
      setError(err instanceof Error ? err.message : JSON.stringify(err));
      // Ensure projects remains an array even on error
      setProjects([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const createProject = useCallback(async (projectData: Omit<Project, 'id' | 'created_at' | 'updated_at' | 'status'>) => {
    try {
      console.log('Creating project:', projectData);
      const newProject = await apiService.createProject(projectData);
      console.log('Project created successfully:', newProject);
      setProjects(prev => [newProject, ...prev]);
      // Clear any previous errors on successful creation
      setError(null);
      return newProject;
    } catch (err) {
      console.error('Error creating project:', err);
      setError(err instanceof Error ? err.message : 'Failed to create project');
      throw err;
    }
  }, []);

  const updateProject = useCallback(async (projectId: string, updates: Partial<Project>) => {
    try {
      const updatedProject = await apiService.updateProject(projectId, updates);
      setProjects(prev => prev.map(p => p.id === projectId ? updatedProject : p));
      return updatedProject;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update project');
      throw err;
    }
  }, []);

  const deleteProject = useCallback(async (projectId: string) => {
    try {
      // First make the API call
      await apiService.deleteProject(projectId);
      // Only remove from local state if API call succeeds
      setProjects(prev => prev.filter(p => p.id !== projectId));
      // Clear any previous errors on successful deletion
      setError(null);
    } catch (err) {
      // Don't remove from local state if deletion failed
      // Don't set the global error state for deletion failures
      // Let the component handle the error display
      console.error('Failed to delete project:', err);
      throw err;
    }
  }, []);

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  // Configurable background refresh: default every 15 minutes, configurable via config.local.json
  useEffect(() => {
    let intervalId: number | undefined;
    let cancelled = false;

    const loadAndStart = async () => {
      // Default: 15 minutes
      let minutes = 15;
      try {
        const res = await fetch(`${API_BASE_URL}/config/config.local.json`);
        if (res.ok) {
          const cfg = await res.json();
          const val = cfg?.frontend?.project_list_poll_interval_minutes;
          if (typeof val === 'number' && isFinite(val) && val > 0) {
            minutes = val;
          } else if (typeof val === 'string' && val.trim() !== '' && !isNaN(Number(val))) {
            const parsed = Number(val);
            if (parsed > 0) minutes = parsed;
          }
        }
      } catch {
        // ignore and use default
      }

      if (cancelled) return;

      const intervalMs = minutes * 60 * 1000;
      // Kick off a delayed refresh loop; only fetch when tab is visible
      intervalId = window.setInterval(() => {
        try {
          if (document.visibilityState === 'visible') {
            fetchProjects();
          }
        } catch {
          // ignore errors in background loop
        }
      }, intervalMs);
    };

    loadAndStart();

    return () => {
      cancelled = true;
      if (intervalId) window.clearInterval(intervalId);
    };
  }, [fetchProjects]);

  return {
    projects,
    loading,
    error,
    fetchProjects,
    createProject,
    updateProject,
    deleteProject,
  };
};

export const useProjectStats = () => {
  const [stats, setStats] = useState<ProjectStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const fetchStats = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      // Derive lightweight stats from projects list to avoid extra network (Phase 4)
      const projects = await apiService.getProjects();
      const total_projects = projects.length;
      const active_projects = projects.filter(p => (p as any).status === 'running').length;
      setStats({ total_projects, active_projects, completed_assessments: 0 });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch project stats');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  return {
    stats,
    loading,
    error,
    fetchStats,
  };
};

export const useProject = (projectId: string | null) => {
  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchProject = useCallback(async (id: string) => {
    try {
      setLoading(true);
      setError(null);
      const data = await apiService.getProject(id);
      setProject(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch project');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (projectId) {
      fetchProject(projectId);
    } else {
      setProject(null);
    }
  }, [projectId, fetchProject]);

  return {
    project,
    loading,
    error,
    fetchProject,
  };
};
