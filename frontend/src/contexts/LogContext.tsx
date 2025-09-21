import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { webSocketManager, MessageType, AssessmentCallback, ProcessingCallback, LogCallback } from '../services/WebSocketManager';
import { StandardizedAssessmentMessage, StandardizedProcessingMessage, StandardizedLogMessage } from '../types/messages';
import { metricsService } from '../services/MetricsService';

// Log entry types
export type LogType = 'assessment' | 'processing' | 'agent_activity' | 'general' | 'upload' | 'system';

export type LogLevel = 'INFO' | 'WARNING' | 'ERROR' | 'DEBUG' | 'SUCCESS';

export interface UnifiedLogEntry {
  id: string;
  type: LogType;
  level: LogLevel;
  timestamp: string;
  message: string;
  source: string;
  projectId?: string;
  metadata?: Record<string, any>;
  // Agent-specific fields
  agentName?: string;
  tool?: string;
  toolInput?: string;
  output?: string;
  error?: string;
  status?: string;
  goal?: string;
  actionDescription?: string;
  log?: string;
  // Processing-specific fields
  operationName?: string;
  currentStep?: number;
  totalSteps?: number;
  progressPercentage?: number;
  // Log-specific fields
  component?: string;
  user_id?: string;
  session_id?: string;
  correlation_id?: string;
  // Deduplication
  deduplicationKey?: string;
  duplicateCount?: number;
}

interface LogSession {
  id: string;
  projectId: string;
  startTime: string;
  endTime?: string;
  logCount: number;
  type: 'assessment' | 'processing' | 'upload' | 'general';
}

interface LogContextState {
  logs: UnifiedLogEntry[];
  sessions: LogSession[];
  currentSession: LogSession | null;
  isWebSocketConnected: boolean;
  maxLogs: number;
  filters: {
    types: LogType[];
    levels: LogLevel[];
    sources: string[];
    projectId?: string;
  };
}

interface LogContextType {
  state: LogContextState;
  // Core log management
  addLog: (entry: Omit<UnifiedLogEntry, 'id' | 'timestamp'>) => void;
  addLogMessage: (type: LogType, level: LogLevel, message: string, source: string, metadata?: Record<string, any>) => void;
  clearLogs: (type?: LogType, projectId?: string) => void;
  clearSession: (sessionId: string) => void;

  // Session management
  startSession: (projectId: string, type: LogSession['type']) => string;
  endSession: (sessionId: string) => void;
  getSessionLogs: (sessionId: string) => UnifiedLogEntry[];

  // Filtering and querying
  setFilters: (filters: Partial<LogContextState['filters']>) => void;
  getFilteredLogs: () => UnifiedLogEntry[];
  getLogsByType: (type: LogType) => UnifiedLogEntry[];
  getLogsByProject: (projectId: string) => UnifiedLogEntry[];

  // WebSocket integration
  subscribeToWebSocket: (projectId: string, enabled: boolean) => void;

  // Utility functions
  deduplicateLogs: () => void;
  exportLogs: (format: 'json' | 'csv') => string;
}

const LogContext = createContext<LogContextType | undefined>(undefined);

// Generate unique ID for log entries
const generateLogId = (): string => {
  return `${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
};

// Generate deduplication key
const generateDeduplicationKey = (entry: Omit<UnifiedLogEntry, 'id' | 'timestamp' | 'deduplicationKey'>): string => {
  const keyParts = [
    entry.type,
    entry.level,
    entry.message.substring(0, 100), // First 100 chars of message
    entry.source,
    entry.agentName || '',
    entry.tool || '',
  ];
  return keyParts.join('|').toLowerCase();
};

export const LogProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [state, setState] = useState<LogContextState>({
    logs: [],
    sessions: [],
    currentSession: null,
    isWebSocketConnected: false,
    maxLogs: 1000, // Keep last 1000 logs
    filters: {
      types: [],
      levels: [],
      sources: [],
    },
  });

  const subscriptionIdsRef = useRef<Map<string, string>>(new Map());

  // WebSocket message handlers
  const handleAssessmentMessage = useCallback((message: StandardizedAssessmentMessage) => {
    const logEntry: Omit<UnifiedLogEntry, 'id' | 'timestamp'> = {
      type: 'agent_activity',
      level: message.type === 'tool_error' ? 'ERROR' : 'INFO',
      message: message.action_description || `${message.agent_name || 'Agent'} ${message.type.replace('_', ' ')}`,
      source: 'agent',
      projectId: message.project_id,
      agentName: message.agent_name,
      tool: message.tool,
      toolInput: message.tool_input,
      output: message.output,
      error: message.error,
      status: message.status,
      goal: message.goal,
      actionDescription: message.action_description,
      log: message.log,
      progressPercentage: message.progress_percentage,
      currentStep: message.current_step,
      totalSteps: message.total_steps,
    };
    addLog(logEntry);
  }, []);

  const handleProcessingMessage = useCallback((message: StandardizedProcessingMessage) => {
    const logEntry: Omit<UnifiedLogEntry, 'id' | 'timestamp'> = {
      type: 'processing',
      level: message.type === 'operation_failed' || message.type === 'document_processing_failed' ? 'ERROR' : 'INFO',
      message: message.message || `Processing ${message.type.replace('_', ' ')}`,
      source: 'processing',
      projectId: message.project_id,
      operationName: message.operation_name,
      currentStep: message.current_step,
      totalSteps: message.total_steps,
      progressPercentage: message.progress_percentage,
    };
    addLog(logEntry);

    // Track processing metrics
    if (message.type === 'document_processing_start') {
      metricsService.trackProcessingStart(
        message.document_id || `doc_${Date.now()}`,
        'document_processing',
        message.document_id,
        message.file_size,
        message.file_name
      );
    } else if (message.type === 'document_processing_complete') {
      metricsService.trackProcessingEnd(
        message.document_id || `doc_${Date.now()}`,
        'success'
      );
    } else if (message.type === 'document_processing_failed') {
      metricsService.trackProcessingEnd(
        message.document_id || `doc_${Date.now()}`,
        'failed',
        message.message
      );
    } else if (message.type === 'operation_progress' && message.progress_percentage) {
      metricsService.trackProgressUpdate(
        message.document_id || `op_${Date.now()}`,
        message.progress_percentage,
        message.operation_name || 'operation',
        message.message
      );
    }
  }, []);

  const handleLogMessage = useCallback((message: StandardizedLogMessage) => {
    const logEntry: Omit<UnifiedLogEntry, 'id' | 'timestamp'> = {
      type: 'general',
      level: message.level,
      message: message.message,
      source: message.service,
      projectId: message.project_id,
      metadata: message.metadata,
      component: message.component,
      user_id: message.user_id,
      session_id: message.session_id,
      correlation_id: message.correlation_id,
    };
    addLog(logEntry);
  }, []);

  // Core log management functions
  const addLog = useCallback((entry: Omit<UnifiedLogEntry, 'id' | 'timestamp'>) => {
    const newEntry: UnifiedLogEntry = {
      ...entry,
      id: generateLogId(),
      timestamp: new Date().toISOString(),
      deduplicationKey: generateDeduplicationKey(entry),
    };

    setState(prevState => {
      // Check for duplicates
      const existingIndex = prevState.logs.findIndex(log =>
        log.deduplicationKey === newEntry.deduplicationKey &&
        Date.now() - new Date(log.timestamp).getTime() < 5000 // Within 5 seconds
      );

      let updatedLogs: UnifiedLogEntry[];

      if (existingIndex >= 0) {
        // Update duplicate count
        updatedLogs = [...prevState.logs];
        updatedLogs[existingIndex] = {
          ...updatedLogs[existingIndex],
          duplicateCount: (updatedLogs[existingIndex].duplicateCount || 1) + 1,
          timestamp: newEntry.timestamp, // Update timestamp to latest
        };
      } else {
        // Add new log
        updatedLogs = [...prevState.logs, newEntry];
      }

      // Keep only the most recent logs
      if (updatedLogs.length > prevState.maxLogs) {
        updatedLogs = updatedLogs.slice(-prevState.maxLogs);
      }

      // Update session count if there's an active session
      const updatedSessions = prevState.currentSession ?
        prevState.sessions.map(session =>
          session.id === prevState.currentSession!.id
            ? { ...session, logCount: session.logCount + (existingIndex >= 0 ? 0 : 1) }
            : session
        ) : prevState.sessions;

      return {
        ...prevState,
        logs: updatedLogs,
        sessions: updatedSessions,
      };
    });
  }, []);

  const addLogMessage = useCallback((
    type: LogType,
    level: LogLevel,
    message: string,
    source: string,
    metadata?: Record<string, any>
  ) => {
    addLog({ type, level, message, source, metadata });
  }, [addLog]);

  const clearLogs = useCallback((type?: LogType, projectId?: string) => {
    setState(prevState => ({
      ...prevState,
      logs: prevState.logs.filter(log => {
        if (type && log.type !== type) return true;
        if (projectId && log.projectId !== projectId) return true;
        return false;
      }),
    }));
  }, []);

  const clearSession = useCallback((sessionId: string) => {
    setState(prevState => ({
      ...prevState,
      logs: prevState.logs.filter(log => {
        // Find session and filter logs that belong to it
        const session = prevState.sessions.find(s => s.id === sessionId);
        if (!session) return true;
        return !(log.projectId === session.projectId &&
                 new Date(log.timestamp) >= new Date(session.startTime) &&
                 (!session.endTime || new Date(log.timestamp) <= new Date(session.endTime)));
      }),
      sessions: prevState.sessions.filter(s => s.id !== sessionId),
    }));
  }, []);

  // Session management
  const startSession = useCallback((projectId: string, type: LogSession['type']): string => {
    const sessionId = generateLogId();
    const newSession: LogSession = {
      id: sessionId,
      projectId,
      startTime: new Date().toISOString(),
      logCount: 0,
      type,
    };

    setState(prevState => ({
      ...prevState,
      currentSession: newSession,
      sessions: [...prevState.sessions, newSession],
    }));

    return sessionId;
  }, []);

  const endSession = useCallback((sessionId: string) => {
    setState(prevState => ({
      ...prevState,
      currentSession: prevState.currentSession?.id === sessionId ? null : prevState.currentSession,
      sessions: prevState.sessions.map(session =>
        session.id === sessionId
          ? { ...session, endTime: new Date().toISOString() }
          : session
      ),
    }));
  }, []);

  const getSessionLogs = useCallback((sessionId: string): UnifiedLogEntry[] => {
    const session = state.sessions.find(s => s.id === sessionId);
    if (!session) return [];

    return state.logs.filter(log =>
      log.projectId === session.projectId &&
      new Date(log.timestamp) >= new Date(session.startTime) &&
      (!session.endTime || new Date(log.timestamp) <= new Date(session.endTime))
    );
  }, [state.sessions, state.logs]);

  // Filtering and querying
  const setFilters = useCallback((filters: Partial<LogContextState['filters']>) => {
    setState(prevState => ({
      ...prevState,
      filters: { ...prevState.filters, ...filters },
    }));
  }, []);

  const getFilteredLogs = useCallback((): UnifiedLogEntry[] => {
    return state.logs.filter(log => {
      if (state.filters.types.length > 0 && !state.filters.types.includes(log.type)) return false;
      if (state.filters.levels.length > 0 && !state.filters.levels.includes(log.level)) return false;
      if (state.filters.sources.length > 0 && !state.filters.sources.includes(log.source)) return false;
      if (state.filters.projectId && log.projectId !== state.filters.projectId) return false;
      return true;
    });
  }, [state.logs, state.filters]);

  const getLogsByType = useCallback((type: LogType): UnifiedLogEntry[] => {
    return state.logs.filter(log => log.type === type);
  }, [state.logs]);

  const getLogsByProject = useCallback((projectId: string): UnifiedLogEntry[] => {
    return state.logs.filter(log => log.projectId === projectId);
  }, [state.logs]);

  // WebSocket integration
  const subscribeToWebSocket = useCallback((projectId: string, enabled: boolean) => {
    if (!enabled || !projectId) {
      // Unsubscribe from all
      subscriptionIdsRef.current.forEach((subId, key) => {
        const [projId, msgType] = key.split('_');
        webSocketManager.unsubscribe(projId, msgType as MessageType, subId);
      });
      subscriptionIdsRef.current.clear();
      setState(prev => ({ ...prev, isWebSocketConnected: false }));
      return;
    }

    // Subscribe to different message types
    const messageTypes = [MessageType.ASSESSMENT, MessageType.PROCESSING, MessageType.LOGS];

    messageTypes.forEach(messageType => {
      const subscriptionKey = `${projectId}_${messageType}`;
      if (!subscriptionIdsRef.current.has(subscriptionKey)) {
        let callback: (message: any) => void;

        switch (messageType) {
          case MessageType.ASSESSMENT:
            callback = handleAssessmentMessage;
            break;
          case MessageType.PROCESSING:
            callback = handleProcessingMessage;
            break;
          case MessageType.LOGS:
            callback = handleLogMessage;
            break;
          default:
            return;
        }

        const subscriptionId = webSocketManager.subscribe(projectId, messageType, callback);
        subscriptionIdsRef.current.set(subscriptionKey, subscriptionId);
      }
    });

    // Update connection status
    const connectionState = webSocketManager.getConnectionState(projectId, messageTypes);
    setState(prev => ({
      ...prev,
      isWebSocketConnected: connectionState === 'connected'
    }));
  }, [handleAssessmentMessage, handleProcessingMessage, handleLogMessage]);

  // Utility functions
  const deduplicateLogs = useCallback(() => {
    setState(prevState => {
      const seen = new Map<string, UnifiedLogEntry>();
      const deduplicated: UnifiedLogEntry[] = [];

      prevState.logs.forEach(log => {
        const key = log.deduplicationKey || log.id;
        if (seen.has(key)) {
          const existing = seen.get(key)!;
          seen.set(key, {
            ...existing,
            duplicateCount: (existing.duplicateCount || 1) + (log.duplicateCount || 1),
            timestamp: log.timestamp > existing.timestamp ? log.timestamp : existing.timestamp,
          });
        } else {
          seen.set(key, log);
        }
      });

      seen.forEach(log => deduplicated.push(log));
      return { ...prevState, logs: deduplicated };
    });
  }, []);

  const exportLogs = useCallback((format: 'json' | 'csv'): string => {
    const logs = getFilteredLogs();

    if (format === 'json') {
      return JSON.stringify(logs, null, 2);
    } else {
      // CSV format
      const headers = ['timestamp', 'type', 'level', 'source', 'message', 'projectId', 'agentName', 'tool'];
      const csvRows = [
        headers.join(','),
        ...logs.map(log => [
          log.timestamp,
          log.type,
          log.level,
          log.source,
          `"${log.message.replace(/"/g, '""')}"`,
          log.projectId || '',
          log.agentName || '',
          log.tool || '',
        ].join(','))
      ];
      return csvRows.join('\n');
    }
  }, [getFilteredLogs]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      subscriptionIdsRef.current.forEach((subId, key) => {
        const [projId, msgType] = key.split('_');
        webSocketManager.unsubscribe(projId, msgType as MessageType, subId);
      });
    };
  }, []);

  const contextValue: LogContextType = {
    state,
    addLog,
    addLogMessage,
    clearLogs,
    clearSession,
    startSession,
    endSession,
    getSessionLogs,
    setFilters,
    getFilteredLogs,
    getLogsByType,
    getLogsByProject,
    subscribeToWebSocket,
    deduplicateLogs,
    exportLogs,
  };

  return (
    <LogContext.Provider value={contextValue}>
      {children}
    </LogContext.Provider>
  );
};

export const useLogContext = () => {
  const context = useContext(LogContext);
  if (context === undefined) {
    throw new Error('useLogContext must be used within a LogProvider');
  }
  return context;
};