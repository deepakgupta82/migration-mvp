/**
 * WebSocket hooks for real-time statistics updates
 * Provides project and platform statistics with automatic updates
 */

import { useState, useEffect, useRef, useCallback } from 'react';

// Types for statistics data
export interface ProjectStats {
  project_id: string;
  files_count: number;
  embeddings_count: number;
  graph_nodes: number;
  graph_relationships: number;
  last_updated: string;
}

export interface PlatformStats {
  total_projects: number;
  total_documents: number;
  total_embeddings: number;
  total_neo4j_nodes: number;
  total_neo4j_relationships: number;
  last_updated: string;
}

// WebSocket message types
interface StatsMessage {
  type: string;
  project_id?: string;
  event_type?: string;
  data: ProjectStats | PlatformStats;
  timestamp: string;
  additional_data?: any;
}

/**
 * Hook for real-time project statistics
 */
export const useProjectStats = (projectId: string) => {
  const [stats, setStats] = useState<ProjectStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastEvent, setLastEvent] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttempts = useRef(0);
  const maxReconnectAttempts = 5;

  const connectWebSocket = useCallback(() => {
    if (!projectId) return;

    try {
      const wsUrl = `ws://localhost:8000/ws/project-stats/${projectId}`;
      console.log(`Connecting to project stats WebSocket: ${wsUrl}`);
      
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log(`Project stats WebSocket connected for project ${projectId}`);
        reconnectAttempts.current = 0;
        setError(null);
        
        // Send ping to keep connection alive
        const pingInterval = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send('ping');
          } else {
            clearInterval(pingInterval);
          }
        }, 30000); // Ping every 30 seconds
      };

      ws.onmessage = (event) => {
        try {
          if (event.data === 'pong') return; // Ignore pong responses
          
          const message: StatsMessage = JSON.parse(event.data);
          console.log(`Project stats update received:`, message);

          if (message.type === 'initial_project_stats' || message.type === 'project_stats_update') {
            setStats(message.data as ProjectStats);
            setLoading(false);
            setLastEvent(message.event_type || 'initial_load');
            
            // Show user-friendly notification for certain events
            if (message.event_type && message.event_type !== 'initial_load') {
              console.log(`Project stats updated due to: ${message.event_type}`);
            }
          }
        } catch (error) {
          console.error('Error parsing project stats message:', error);
        }
      };

      ws.onclose = (event) => {
        console.log(`Project stats WebSocket closed for project ${projectId}:`, event.code, event.reason);
        wsRef.current = null;
        
        // Attempt to reconnect if not a normal closure
        if (event.code !== 1000 && reconnectAttempts.current < maxReconnectAttempts) {
          const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 30000);
          console.log(`Attempting to reconnect project stats WebSocket in ${delay}ms (attempt ${reconnectAttempts.current + 1})`);
          
          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectAttempts.current++;
            connectWebSocket();
          }, delay);
        } else if (reconnectAttempts.current >= maxReconnectAttempts) {
          setError('Failed to maintain WebSocket connection. Please refresh the page.');
        }
      };

      ws.onerror = (error) => {
        console.error(`Project stats WebSocket error for project ${projectId}:`, error);
        setError('WebSocket connection error');
      };

    } catch (error) {
      console.error('Error creating project stats WebSocket:', error);
      setError('Failed to create WebSocket connection');
    }
  }, [projectId]);

  // Initial stats load via HTTP as fallback
  const loadInitialStats = useCallback(async () => {
    if (!projectId) return;

    try {
      const response = await fetch(`http://localhost:8000/api/projects/${projectId}/stats`);
      if (response.ok) {
        const data = await response.json();
        setStats(data);
        setLoading(false);
        console.log('Initial project stats loaded via HTTP:', data);
      } else {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
    } catch (error) {
      console.error('Error loading initial project stats:', error);
      setError('Failed to load initial statistics');
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    if (!projectId) return;

    // Load initial stats
    loadInitialStats();
    
    // Connect WebSocket for real-time updates
    connectWebSocket();

    return () => {
      // Cleanup
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close(1000, 'Component unmounting');
      }
    };
  }, [projectId, loadInitialStats, connectWebSocket]);

  const refreshStats = useCallback(() => {
    loadInitialStats();
  }, [loadInitialStats]);

  return { 
    stats, 
    loading, 
    error, 
    lastEvent, 
    refreshStats,
    connected: wsRef.current?.readyState === WebSocket.OPEN 
  };
};

/**
 * Hook for real-time platform statistics
 */
export const usePlatformStats = () => {
  const [stats, setStats] = useState<PlatformStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastEvent, setLastEvent] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttempts = useRef(0);
  const maxReconnectAttempts = 5;

  const connectWebSocket = useCallback(() => {
    try {
      const wsUrl = `ws://localhost:8000/ws/platform-stats`;
      console.log(`Connecting to platform stats WebSocket: ${wsUrl}`);
      
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('Platform stats WebSocket connected');
        reconnectAttempts.current = 0;
        setError(null);
        
        // Send ping to keep connection alive
        const pingInterval = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send('ping');
          } else {
            clearInterval(pingInterval);
          }
        }, 30000); // Ping every 30 seconds
      };

      ws.onmessage = (event) => {
        try {
          if (event.data === 'pong') return; // Ignore pong responses
          
          const message: StatsMessage = JSON.parse(event.data);
          console.log('Platform stats update received:', message);

          if (message.type === 'initial_platform_stats' || message.type === 'platform_stats_update') {
            setStats(message.data as PlatformStats);
            setLoading(false);
            setLastEvent(message.event_type || 'initial_load');
            
            // Show user-friendly notification for certain events
            if (message.event_type && message.event_type !== 'initial_load') {
              console.log(`Platform stats updated due to: ${message.event_type}`);
            }
          }
        } catch (error) {
          console.error('Error parsing platform stats message:', error);
        }
      };

      ws.onclose = (event) => {
        console.log('Platform stats WebSocket closed:', event.code, event.reason);
        wsRef.current = null;
        
        // Attempt to reconnect if not a normal closure
        if (event.code !== 1000 && reconnectAttempts.current < maxReconnectAttempts) {
          const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 30000);
          console.log(`Attempting to reconnect platform stats WebSocket in ${delay}ms (attempt ${reconnectAttempts.current + 1})`);
          
          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectAttempts.current++;
            connectWebSocket();
          }, delay);
        } else if (reconnectAttempts.current >= maxReconnectAttempts) {
          setError('Failed to maintain WebSocket connection. Please refresh the page.');
        }
      };

      ws.onerror = (error) => {
        console.error('Platform stats WebSocket error:', error);
        setError('WebSocket connection error');
      };

    } catch (error) {
      console.error('Error creating platform stats WebSocket:', error);
      setError('Failed to create WebSocket connection');
    }
  }, []);

  // Initial stats load via HTTP as fallback
  const loadInitialStats = useCallback(async () => {
    try {
      const response = await fetch('http://localhost:8000/api/platform/stats');
      if (response.ok) {
        const data = await response.json();
        setStats(data);
        setLoading(false);
        console.log('Initial platform stats loaded via HTTP:', data);
      } else {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
    } catch (error) {
      console.error('Error loading initial platform stats:', error);
      setError('Failed to load initial statistics');
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // Load initial stats
    loadInitialStats();
    
    // Connect WebSocket for real-time updates
    connectWebSocket();

    return () => {
      // Cleanup
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close(1000, 'Component unmounting');
      }
    };
  }, [loadInitialStats, connectWebSocket]);

  const refreshStats = useCallback(() => {
    loadInitialStats();
  }, [loadInitialStats]);

  return { 
    stats, 
    loading, 
    error, 
    lastEvent, 
    refreshStats,
    connected: wsRef.current?.readyState === WebSocket.OPEN 
  };
};
