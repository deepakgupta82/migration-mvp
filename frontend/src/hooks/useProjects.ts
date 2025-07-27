/**
 * Custom hooks for project data management
 */

import { useState, useEffect, useCallback } from 'react';
import { apiService, Project, ProjectStats } from '../services/api';

export const useProjects = () => {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchProjects = useCallback(async () => {
    try {
      console.log('Fetching projects...');
      setLoading(true);
      setError(null);
      const data = await apiService.getProjects();
      console.log('Projects fetched successfully:', data);
      setProjects(data);
    } catch (err) {
      console.error('Error fetching projects:', err);
      setError(err instanceof Error ? err.message : 'Failed to fetch projects');
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
      await apiService.deleteProject(projectId);
      setProjects(prev => prev.filter(p => p.id !== projectId));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete project');
      throw err;
    }
  }, []);

  useEffect(() => {
    fetchProjects();
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
      const data = await apiService.getProjectStats();
      setStats(data);
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
