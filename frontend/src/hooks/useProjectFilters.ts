import { useState, useMemo } from 'react';
import { Project } from '../services/api';

export interface UseProjectFiltersReturn {
  searchQuery: string;
  setSearchQuery: (query: string) => void;
  statusFilter: string | null;
  setStatusFilter: (status: string | null) => void;
  filteredProjects: Project[];
  totalCount: number;
  filteredCount: number;
}

export const useProjectFilters = (projects: Project[]): UseProjectFiltersReturn => {
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string | null>(null);

  const filteredProjects = useMemo(() => {
    if (!Array.isArray(projects)) return [];

    return projects.filter((project) => {
      // Search filter
      const matchesSearch = !searchQuery ||
        project.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        project.client_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        project.description?.toLowerCase().includes(searchQuery.toLowerCase());

      // Status filter
      const matchesStatus = !statusFilter || project.status === statusFilter;

      return matchesSearch && matchesStatus;
    });
  }, [projects, searchQuery, statusFilter]);

  return {
    searchQuery,
    setSearchQuery,
    statusFilter,
    setStatusFilter,
    filteredProjects,
    totalCount: projects.length,
    filteredCount: filteredProjects.length,
  };
};