import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { useProgressQueue, ProgressUpdate } from '../utils/ProgressUpdateQueue';

interface AssessmentEvent {
  id: string;
  timestamp: Date;
  message: string;
  type: 'info' | 'success' | 'warning' | 'error' | 'progress';
  phase?: string; // e.g., 'parsing', 'vector', 'graph', 'entity', 'facts'
  details?: Record<string, any>; // Statistics extracted from WebSocket events
}

interface AssessmentStatistics {
  documentsProcessed: number;
  totalElements: number;
  embeddingsCreated: number;
  entitiesExtracted: number;
  relationshipsExtracted: number;
  factsExtracted: number;
  graphNodesCreated: number;
  graphEdgesCreated: number;
  errors: number;
  warnings: number;
}

interface AssessmentState {
  isRunning: boolean;
  projectId: string | null;
  startTime: Date | null;
  events: AssessmentEvent[];
  status: 'idle' | 'running' | 'completed' | 'failed';
  progress: number;
  statistics: AssessmentStatistics;
  currentPhase: string | null;
}

interface AssessmentContextType {
  assessmentState: AssessmentState;
  startAssessment: (projectId: string) => void;
  stopAssessment: () => void;
  addEvent: (event: Omit<AssessmentEvent, 'id' | 'timestamp'>) => void;
  addLog: (log: string) => void; // Legacy support
  setStatus: (status: AssessmentState['status']) => void;
  setProgress: (progress: number) => void;
  clearEvents: () => void;
  updateStatistics: (updates: Partial<AssessmentStatistics>) => void;
}

const AssessmentContext = createContext<AssessmentContextType | undefined>(undefined);

const initialStatistics: AssessmentStatistics = {
  documentsProcessed: 0,
  totalElements: 0,
  embeddingsCreated: 0,
  entitiesExtracted: 0,
  relationshipsExtracted: 0,
  factsExtracted: 0,
  graphNodesCreated: 0,
  graphEdgesCreated: 0,
  errors: 0,
  warnings: 0,
};

export const AssessmentProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [assessmentState, setAssessmentState] = useState<AssessmentState>({
    isRunning: false,
    projectId: null,
    startTime: null,
    events: [],
    status: 'idle',
    progress: 0,
    statistics: initialStatistics,
    currentPhase: null,
  });

  // Progress update handler for the queue
  const handleProgressUpdate = useCallback((update: ProgressUpdate) => {
    setAssessmentState(prev => ({
      ...prev,
      progress: Math.max(0, Math.min(100, update.progress)),
    }));
  }, []);

  // Initialize progress queue
  const { enqueue: enqueueProgress } = useProgressQueue(handleProgressUpdate, {
    debounceMs: 50,
    maxQueueSize: 20,
    enableBatching: true,
  });

  const startAssessment = useCallback((projectId: string) => {
    // CRITICAL: Clear all events from previous run when starting new assessment
    setAssessmentState({
      isRunning: true,
      projectId,
      startTime: new Date(),
      events: [{
        id: `evt_${Date.now()}`,
        timestamp: new Date(),
        message: `🚀 Assessment started for project ${projectId}`,
        type: 'info',
        phase: 'initialization',
      }],
      status: 'running',
      progress: 0,
      statistics: { ...initialStatistics }, // Reset statistics
      currentPhase: 'initialization',
    });
  }, []);

  const stopAssessment = useCallback(() => {
    setAssessmentState(prev => ({
      ...prev,
      isRunning: false,
      status: prev.status === 'running' ? 'completed' : prev.status,
      currentPhase: null,
    }));
  }, []);

  const clearEvents = useCallback(() => {
    setAssessmentState(prev => ({
      ...prev,
      events: [],
      statistics: { ...initialStatistics },
    }));
  }, []);

  const addEvent = useCallback((event: Omit<AssessmentEvent, 'id' | 'timestamp'>) => {
    // DEBUG: Log every addEvent call
    console.log('[AssessmentContext DEBUG] addEvent called with:', event);
    
    const newEvent: AssessmentEvent = {
      ...event,
      id: `evt_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      timestamp: new Date(),
    };
    
    console.log('[AssessmentContext DEBUG] Created new event:', newEvent);

    setAssessmentState(prev => {
      console.log('[AssessmentContext DEBUG] Previous state events count:', prev.events.length);
      console.log('[AssessmentContext DEBUG] Previous statistics:', prev.statistics);
      // Update statistics based on event details
      const updatedStats = { ...prev.statistics };
      
      // Track errors and warnings
      if (event.type === 'error') {
        updatedStats.errors += 1;
      } else if (event.type === 'warning') {
        updatedStats.warnings += 1;
      }

      // Extract statistics from event details if available
      if (event.details) {
        if (event.details.elements_count) {
          updatedStats.totalElements += event.details.elements_count;
        }
        if (event.details.embeddings_created) {
          updatedStats.embeddingsCreated += event.details.embeddings_created;
        }
        if (event.details.entities_extracted || event.details.entities_count) {
          updatedStats.entitiesExtracted += event.details.entities_extracted || event.details.entities_count;
        }
        if (event.details.relationships_extracted || event.details.relationships_count) {
          updatedStats.relationshipsExtracted += event.details.relationships_extracted || event.details.relationships_count;
        }
        if (event.details.facts_extracted || event.details.facts_count) {
          updatedStats.factsExtracted += event.details.facts_extracted || event.details.facts_count;
        }
        if (event.details.graph_nodes || event.details.nodes_created) {
          updatedStats.graphNodesCreated += event.details.graph_nodes || event.details.nodes_created;
        }
        if (event.details.graph_edges || event.details.edges_created) {
          updatedStats.graphEdgesCreated += event.details.graph_edges || event.details.edges_created;
        }
        if (event.details.document_processed) {
          updatedStats.documentsProcessed += 1;
        }
      }

      const newState = {
        ...prev,
        events: [...prev.events, newEvent].slice(-100), // Keep last 100 events
        statistics: updatedStats,
        currentPhase: event.phase || prev.currentPhase,
      };
      
      console.log('[AssessmentContext DEBUG] New state events count:', newState.events.length);
      console.log('[AssessmentContext DEBUG] New statistics:', newState.statistics);
      console.log('[AssessmentContext DEBUG] Current phase:', newState.currentPhase);
      
      return newState;
    });
  }, []);

  // Legacy addLog support for backward compatibility
  const addLog = useCallback((log: string) => {
    const timestamp = new Date().toLocaleTimeString();
    const logWithTimestamp = `[${timestamp}] ${log}`;
    
    // Convert log to event format
    let type: AssessmentEvent['type'] = 'info';
    if (log.includes('❌') || log.toLowerCase().includes('error') || log.toLowerCase().includes('failed')) {
      type = 'error';
    } else if (log.includes('✅') || log.toLowerCase().includes('success') || log.toLowerCase().includes('completed')) {
      type = 'success';
    } else if (log.includes('⚠️') || log.toLowerCase().includes('warning')) {
      type = 'warning';
    }

    addEvent({
      message: logWithTimestamp,
      type,
    });
  }, [addEvent]);

  const setStatus = useCallback((status: AssessmentState['status']) => {
    setAssessmentState(prev => {
      const newIsRunning = status === 'running';
      if (prev.status === status && prev.isRunning === newIsRunning) {
        return prev;
      }
      return {
        ...prev,
        status,
        isRunning: newIsRunning,
      };
    });
  }, []);

  const setProgress = useCallback((progress: number) => {
    enqueueProgress({
      type: 'assessment',
      progress: Math.max(0, Math.min(100, progress)),
      priority: 'normal',
    });
  }, [enqueueProgress]);

  const updateStatistics = useCallback((updates: Partial<AssessmentStatistics>) => {
    setAssessmentState(prev => ({
      ...prev,
      statistics: {
        ...prev.statistics,
        ...updates,
      },
    }));
  }, []);

  // Auto-fail assessment after 30 minutes
  useEffect(() => {
    if (assessmentState.isRunning && assessmentState.startTime) {
      const timeout = setTimeout(() => {
        if (assessmentState.status === 'running') {
          setStatus('failed');
          addEvent({
            message: '❌ Assessment timed out after 30 minutes',
            type: 'error',
            phase: 'timeout',
          });
        }
      }, 30 * 60 * 1000);

      return () => clearTimeout(timeout);
    }
  }, [assessmentState.isRunning, assessmentState.startTime, assessmentState.status, setStatus, addEvent]);

  return (
    <AssessmentContext.Provider
      value={{
        assessmentState,
        startAssessment,
        stopAssessment,
        addEvent,
        addLog,
        setStatus,
        setProgress,
        clearEvents,
        updateStatistics,
      }}
    >
      {children}
    </AssessmentContext.Provider>
  );
};

export const useAssessment = () => {
  const context = useContext(AssessmentContext);
  if (context === undefined) {
    throw new Error('useAssessment must be used within an AssessmentProvider');
  }
  return context;
};
