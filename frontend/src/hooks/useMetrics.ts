/**
 * React hooks for metrics tracking and analytics
 * Provides easy-to-use hooks for tracking processing operations, WebSocket connections, and performance metrics
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import { metricsService } from '../services/MetricsService';
import { webSocketManager, MessageType } from '../services/WebSocketManager';
import {
  ProcessingMetrics,
  WebSocketMetrics,
  PerformanceMetrics,
  AnalyticsDashboardData,
  UseProcessingMetricsReturn,
  UseWebSocketMetricsReturn,
  UsePerformanceMetricsReturn,
  UseMetricsReturn,
  TimeRange
} from '../types/metrics';

// Hook for tracking processing operations
export const useProcessingMetrics = (projectId: string): UseProcessingMetricsReturn => {
  const operationIdsRef = useRef<Set<string>>(new Set());

  const trackProcessingStart = useCallback((
    operationId: string,
    operationType: string,
    documentId?: string,
    fileSize?: number,
    fileType?: string
  ) => {
    metricsService.trackProcessingStart(operationId, operationType, documentId, fileSize, fileType);
    operationIdsRef.current.add(operationId);
  }, []);

  const trackProcessingEnd = useCallback((
    operationId: string,
    status: 'success' | 'failed' | 'cancelled',
    errorMessage?: string,
    retryCount?: number
  ) => {
    metricsService.trackProcessingEnd(operationId, status, errorMessage, retryCount);
    operationIdsRef.current.delete(operationId);
  }, []);

  const trackProcessingStage = useCallback((
    operationId: string,
    stageName: string,
    progress?: number
  ) => {
    metricsService.trackProcessingStage(operationId, stageName, progress);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      operationIdsRef.current.forEach(operationId => {
        metricsService.trackProcessingEnd(operationId, 'cancelled', 'Component unmounted');
      });
      operationIdsRef.current.clear();
    };
  }, []);

  return {
    trackProcessingStart,
    trackProcessingEnd,
    trackProcessingStage,
    currentMetrics: metricsService.getActiveOperations()
  };
};

// Hook for tracking WebSocket connection metrics
export const useWebSocketMetrics = (projectId: string): UseWebSocketMetricsReturn => {
  const connectionIdRef = useRef<string>(`ws_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`);
  const lastConnectionStateRef = useRef<string>('disconnected');
  const connectionStartTimeRef = useRef<number | null>(null);

  const trackConnectionEvent = useCallback((
    event: WebSocketMetrics['event'],
    details: Partial<WebSocketMetrics> = {}
  ) => {
    const now = Date.now();

    // Track connection duration
    let duration: number | undefined;
    if (event === 'connect') {
      connectionStartTimeRef.current = now;
      lastConnectionStateRef.current = 'connected';
    } else if (event === 'disconnect' && connectionStartTimeRef.current) {
      duration = now - connectionStartTimeRef.current;
      connectionStartTimeRef.current = null;
      lastConnectionStateRef.current = 'disconnected';
    }

    metricsService.trackWebSocketEvent(event, {
      connectionId: connectionIdRef.current,
      connectionState: lastConnectionStateRef.current as WebSocketMetrics['connectionState'],
      duration,
      ...details
    });
  }, []);

  const trackMessage = useCallback((direction: 'sent' | 'received', messageType?: string) => {
    // Track message events
    metricsService.trackWebSocketEvent(
      direction === 'sent' ? 'message_sent' : 'message_received',
      {
        connectionId: connectionIdRef.current,
        connectionState: lastConnectionStateRef.current as WebSocketMetrics['connectionState']
      }
    );
  }, []);

  // Set up WebSocket event listeners
  useEffect(() => {
    const handleConnectionStateChange = (state: string) => {
      const event = state === 'connected' ? 'connect' :
                   state === 'disconnected' ? 'disconnect' :
                   state === 'reconnecting' ? 'reconnect' : 'error';

      trackConnectionEvent(event, { connectionState: state as WebSocketMetrics['connectionState'] });
    };

    // Subscribe to WebSocket state changes
    // This would need to be integrated with the WebSocket manager's state change callbacks
    // For now, we'll track basic connection events

    return () => {
      if (connectionStartTimeRef.current) {
        trackConnectionEvent('disconnect');
      }
    };
  }, [projectId, trackConnectionEvent]);

  // Calculate connection stability (percentage of time connected)
  const connectionStability = useCallback(() => {
    const metrics = metricsService.getWebSocketMetrics();
    const recentMetrics = metrics.filter(m =>
      Date.now() - new Date(m.timestamp).getTime() < 3600000 // Last hour
    );

    if (recentMetrics.length === 0) return 100;

    const connectedTime = recentMetrics
      .filter(m => m.connectionState === 'connected')
      .reduce((sum, m) => sum + (m.duration || 0), 0);

    const totalTime = 3600000; // 1 hour in milliseconds
    return Math.min(100, (connectedTime / totalTime) * 100);
  }, []);

  return {
    trackConnectionEvent,
    trackMessage,
    connectionMetrics: metricsService.getWebSocketMetrics(),
    connectionStability: connectionStability()
  };
};

// Hook for tracking performance metrics
export const usePerformanceMetrics = (projectId: string): UsePerformanceMetricsReturn => {
  const [isTracking, setIsTracking] = useState(false);
  const trackingIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const trackPerformance = useCallback(() => {
    if (isTracking) return;

    setIsTracking(true);

    // Track initial performance metrics
    metricsService.trackPerformanceMetric({
      memoryUsage: metricsService.getCurrentMemoryUsage()
    });

    // Set up periodic tracking
    trackingIntervalRef.current = setInterval(() => {
      metricsService.trackPerformanceMetric({
        memoryUsage: metricsService.getCurrentMemoryUsage()
      });
    }, 30000); // Every 30 seconds
  }, [isTracking]);

  const stopTracking = useCallback(() => {
    if (trackingIntervalRef.current) {
      clearInterval(trackingIntervalRef.current);
      trackingIntervalRef.current = null;
    }
    setIsTracking(false);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopTracking();
    };
  }, [stopTracking]);

  // Get current memory usage
  const memoryUsage = metricsService.getCurrentMemoryUsage();

  return {
    trackPerformance,
    memoryUsage,
    performanceData: metricsService.getPerformanceMetrics(),
    isTracking
  };
};

// Main analytics dashboard hook
export const useMetrics = (projectId: string, timeRange: TimeRange = '24h'): UseMetricsReturn => {
  const [metrics, setMetrics] = useState<AnalyticsDashboardData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    try {
      setIsLoading(true);
      setError(null);
      const dashboardData = metricsService.getAnalyticsDashboard(timeRange);
      setMetrics(dashboardData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load metrics');
    } finally {
      setIsLoading(false);
    }
  }, [timeRange]);

  const exportData = useCallback(async (format: 'json' | 'csv') => {
    try {
      return await metricsService.exportData(format, timeRange);
    } catch (err) {
      throw new Error(`Failed to export data: ${err instanceof Error ? err.message : 'Unknown error'}`);
    }
  }, [timeRange]);

  const clearMetrics = useCallback(() => {
    metricsService.clearMetrics();
    refresh();
  }, [refresh]);

  // Auto-refresh every 30 seconds
  useEffect(() => {
    refresh();

    const interval = setInterval(refresh, 30000);
    return () => clearInterval(interval);
  }, [refresh]);

  return {
    metrics: metrics || metricsService.getAnalyticsDashboard(timeRange),
    isLoading,
    error,
    refresh,
    exportData,
    clearMetrics
  };
};

// Hook for tracking progress updates
export const useProgressTracking = (operationId: string, projectId: string) => {
  const lastProgressRef = useRef<number>(0);
  const updateCountRef = useRef<number>(0);
  const startTimeRef = useRef<number>(Date.now());

  const trackProgress = useCallback((
    progressPercentage: number,
    stage: string,
    message?: string,
    estimatedTimeRemaining?: number
  ) => {
    // Only track if progress has actually changed
    if (progressPercentage !== lastProgressRef.current) {
      updateCountRef.current += 1;
      lastProgressRef.current = progressPercentage;

      metricsService.trackProgressUpdate(
        operationId,
        progressPercentage,
        stage,
        message,
        estimatedTimeRemaining
      );
    }
  }, [operationId]);

  const getProgressStats = useCallback(() => {
    const elapsed = Date.now() - startTimeRef.current;
    const progressRate = lastProgressRef.current / (elapsed / 1000); // percentage per second

    return {
      currentProgress: lastProgressRef.current,
      updateCount: updateCountRef.current,
      elapsedTime: elapsed,
      progressRate,
      estimatedTotalTime: progressRate > 0 ? (100 / progressRate) * 1000 : 0 // milliseconds
    };
  }, []);

  return {
    trackProgress,
    getProgressStats,
    currentProgress: lastProgressRef.current
  };
};

// Hook for real-time metrics updates
export const useRealTimeMetrics = (projectId: string, updateInterval: number = 5000) => {
  const [realTimeData, setRealTimeData] = useState({
    activeOperations: 0,
    operationsPerMinute: 0,
    averageLatency: 0,
    memoryUsage: 0,
    errorRate: 0,
    throughput: 0
  });

  const calculateRealTimeMetrics = useCallback(() => {
    const now = Date.now();
    const oneMinuteAgo = now - 60000;

    const recentProcessing = metricsService.getProcessingMetrics().filter(
      m => new Date(m.startTime).getTime() > oneMinuteAgo
    );

    const recentWebSocket = metricsService.getWebSocketMetrics().filter(
      m => new Date(m.timestamp).getTime() > oneMinuteAgo
    );

    const recentPerformance = metricsService.getPerformanceMetrics().filter(
      m => new Date(m.timestamp).getTime() > oneMinuteAgo
    );

    const activeOperations = metricsService.getActiveOperations().length;
    const operationsPerMinute = recentProcessing.length;

    const latencies = recentWebSocket
      .filter(m => m.latency !== undefined)
      .map(m => m.latency!);
    const averageLatency = latencies.length > 0
      ? latencies.reduce((sum, lat) => sum + lat, 0) / latencies.length
      : 0;

    const memoryUsage = recentPerformance.length > 0
      ? recentPerformance.reduce((sum, m) => sum + m.memoryUsage.percentage, 0) / recentPerformance.length
      : 0;

    const errorRate = recentProcessing.length > 0
      ? (recentProcessing.filter(m => m.status === 'failed').length / recentProcessing.length) * 100
      : 0;

    const throughput = operationsPerMinute; // operations per minute

    setRealTimeData({
      activeOperations,
      operationsPerMinute,
      averageLatency,
      memoryUsage,
      errorRate,
      throughput
    });
  }, []);

  useEffect(() => {
    calculateRealTimeMetrics();

    const interval = setInterval(calculateRealTimeMetrics, updateInterval);
    return () => clearInterval(interval);
  }, [calculateRealTimeMetrics, updateInterval]);

  return realTimeData;
};

// Hook for metrics alerts and insights
export const useMetricsAlerts = (projectId: string) => {
  const [alerts, setAlerts] = useState<Array<{
    id: string;
    type: 'warning' | 'error' | 'info';
    title: string;
    message: string;
    timestamp: string;
    acknowledged: boolean;
  }>>([]);

  const checkForAlerts = useCallback(() => {
    const dashboard = metricsService.getAnalyticsDashboard('1h');
    const newAlerts: typeof alerts = [];

    // Check success rate
    if (dashboard.summary.successRate < 80) {
      newAlerts.push({
        id: 'low_success_rate',
        type: 'warning',
        title: 'Low Success Rate',
        message: `Success rate dropped to ${dashboard.summary.successRate.toFixed(1)}%`,
        timestamp: new Date().toISOString(),
        acknowledged: false
      });
    }

    // Check processing time
    if (dashboard.summary.averageProcessingTime > 300000) { // 5 minutes
      newAlerts.push({
        id: 'slow_processing',
        type: 'warning',
        title: 'Slow Processing',
        message: `Average processing time is ${(dashboard.summary.averageProcessingTime / 1000).toFixed(1)}s`,
        timestamp: new Date().toISOString(),
        acknowledged: false
      });
    }

    // Check memory usage trend
    if (dashboard.trends.memoryUsage.direction === 'up' &&
        dashboard.trends.memoryUsage.changePercentage > 20) {
      newAlerts.push({
        id: 'memory_trend',
        type: 'warning',
        title: 'Memory Usage Increasing',
        message: `Memory usage increased by ${dashboard.trends.memoryUsage.changePercentage.toFixed(1)}%`,
        timestamp: new Date().toISOString(),
        acknowledged: false
      });
    }

    setAlerts(prev => {
      // Merge with existing alerts, avoiding duplicates
      const existingIds = new Set(prev.map(a => a.id));
      const uniqueNewAlerts = newAlerts.filter(a => !existingIds.has(a.id));
      return [...prev, ...uniqueNewAlerts];
    });
  }, []);

  const acknowledgeAlert = useCallback((alertId: string) => {
    setAlerts(prev => prev.map(alert =>
      alert.id === alertId ? { ...alert, acknowledged: true } : alert
    ));
  }, []);

  const dismissAlert = useCallback((alertId: string) => {
    setAlerts(prev => prev.filter(alert => alert.id !== alertId));
  }, []);

  useEffect(() => {
    checkForAlerts();

    const interval = setInterval(checkForAlerts, 60000); // Check every minute
    return () => clearInterval(interval);
  }, [checkForAlerts]);

  return {
    alerts,
    acknowledgeAlert,
    dismissAlert,
    activeAlertsCount: alerts.filter(a => !a.acknowledged).length
  };
};