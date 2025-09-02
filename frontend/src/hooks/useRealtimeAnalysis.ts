import { useState, useEffect, useRef, useCallback } from 'react';
import { notifications } from '@mantine/notifications';

interface AnalysisProgress {
  analysis_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress_percentage: number;
  current_step?: string;
  total_steps?: number;
  message?: string;
  estimated_completion?: string;
  error_message?: string;
}

interface BatchProgress {
  batch_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress_percentage: number;
  completed_files: number;
  total_files: number;
  current_file?: string;
  message?: string;
  estimated_completion?: string;
}

interface UseRealtimeAnalysisOptions {
  projectId: string;
  onAnalysisUpdate?: (progress: AnalysisProgress) => void;
  onBatchUpdate?: (progress: BatchProgress) => void;
  onAnalysisComplete?: (analysisId: string, result: any) => void;
  onBatchComplete?: (batchId: string, results: any[]) => void;
  autoConnect?: boolean;
}

export const useRealtimeAnalysis = ({
  projectId,
  onAnalysisUpdate,
  onBatchUpdate,
  onAnalysisComplete,
  onBatchComplete,
  autoConnect = true
}: UseRealtimeAnalysisOptions) => {
  const [isConnected, setIsConnected] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttempts = useRef(0);
  const maxReconnectAttempts = 5;

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return; // Already connected
    }

    try {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = window.location.host;
      const wsUrl = `${protocol}//${host}/ws/analysis/${projectId}?token=service-backend-token`;

      console.log('Connecting to WebSocket:', wsUrl);
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('WebSocket connected for analysis updates');
        setIsConnected(true);
        setConnectionError(null);
        reconnectAttempts.current = 0;
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log('Received analysis update:', data);

          // Handle different message types
          if (data.type === 'analysis_progress') {
            const progress: AnalysisProgress = data.data;
            onAnalysisUpdate?.(progress);

            if (progress.status === 'completed') {
              onAnalysisComplete?.(progress.analysis_id, data.result);
            }
          } else if (data.type === 'batch_progress') {
            const progress: BatchProgress = data.data;
            onBatchUpdate?.(progress);

            if (progress.status === 'completed') {
              onBatchComplete?.(progress.batch_id, data.results || []);
            }
          } else if (data.type === 'analysis_result') {
            // Direct analysis result
            onAnalysisComplete?.(data.analysis_id, data.result);
          } else if (data.type === 'batch_result') {
            // Direct batch result
            onBatchComplete?.(data.batch_id, data.results || []);
          }
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      };

      ws.onclose = (event) => {
        console.log('WebSocket closed:', event.code, event.reason);
        setIsConnected(false);
        wsRef.current = null;

        // Attempt to reconnect if not a normal closure
        if (event.code !== 1000 && reconnectAttempts.current < maxReconnectAttempts) {
          reconnectAttempts.current++;
          const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 30000);

          reconnectTimeoutRef.current = setTimeout(() => {
            console.log(`Attempting to reconnect (${reconnectAttempts.current}/${maxReconnectAttempts})...`);
            connect();
          }, delay);
        } else if (reconnectAttempts.current >= maxReconnectAttempts) {
          setConnectionError('Failed to reconnect after multiple attempts');
          notifications.show({
            title: 'Connection Lost',
            message: 'Unable to maintain real-time connection for analysis updates',
            color: 'orange',
          });
        }
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        setConnectionError('WebSocket connection error');
      };

    } catch (error) {
      console.error('Failed to create WebSocket connection:', error);
      setConnectionError('Failed to establish connection');
    }
  }, [projectId, onAnalysisUpdate, onBatchUpdate, onAnalysisComplete, onBatchComplete]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (wsRef.current) {
      wsRef.current.close(1000, 'Component unmounting');
      wsRef.current = null;
    }

    setIsConnected(false);
  }, []);

  const sendMessage = useCallback((message: any) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    } else {
      console.warn('WebSocket is not connected, cannot send message:', message);
    }
  }, []);

  // Auto-connect on mount if enabled
  useEffect(() => {
    if (autoConnect) {
      connect();
    }

    return () => {
      disconnect();
    };
  }, [autoConnect, connect, disconnect]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      disconnect();
    };
  }, [disconnect]);

  return {
    isConnected,
    connectionError,
    connect,
    disconnect,
    sendMessage,
    reconnect: () => {
      reconnectAttempts.current = 0;
      connect();
    }
  };
};

export default useRealtimeAnalysis;