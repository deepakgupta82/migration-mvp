// Comprehensive Analytics and Metrics Types for Migration Platform

// Core metric data point
export interface MetricDataPoint {
  id: string;
  timestamp: string;
  projectId: string;
  operationId?: string;
  documentId?: string;
  value: number;
  unit: string;
  metadata?: Record<string, any>;
}

// Processing performance metrics
export interface ProcessingMetrics {
  operationId: string;
  documentId?: string;
  projectId: string;
  startTime: string;
  endTime?: string;
  duration: number; // in milliseconds
  status: 'success' | 'failed' | 'in_progress' | 'cancelled';
  operationType: string;
  fileSize?: number;
  fileType?: string;
  errorMessage?: string;
  retryCount?: number;
  processingStages: ProcessingStage[];
}

export interface ProcessingStage {
  stageName: string;
  startTime: string;
  endTime?: string;
  duration?: number;
  status: 'success' | 'failed' | 'in_progress';
  progress?: number; // 0-100
  metadata?: Record<string, any>;
}

// WebSocket connection metrics
export interface WebSocketMetrics {
  projectId: string;
  connectionId: string;
  timestamp: string;
  event: 'connect' | 'disconnect' | 'reconnect' | 'error' | 'message_received' | 'message_sent';
  connectionState: 'connected' | 'connecting' | 'reconnecting' | 'disconnected' | 'failed';
  duration?: number; // connection duration in milliseconds
  errorMessage?: string;
  messageCount?: number;
  reconnectAttempts?: number;
  latency?: number; // in milliseconds
}

// Memory and performance metrics
export interface PerformanceMetrics {
  timestamp: string;
  projectId: string;
  memoryUsage: {
    used: number; // in MB
    total: number; // in MB
    percentage: number;
  };
  cpuUsage?: number; // percentage
  networkLatency?: number; // in milliseconds
  domNodes?: number;
  renderTime?: number; // in milliseconds
  jsHeapSize?: number; // in MB
  jsHeapSizeLimit?: number; // in MB
}

// Progress update metrics
export interface ProgressMetrics {
  operationId: string;
  projectId: string;
  documentId?: string;
  timestamp: string;
  progressPercentage: number;
  stage: string;
  message?: string;
  estimatedTimeRemaining?: number; // in milliseconds
  updateFrequency: number; // updates per minute
  reliability: number; // percentage of successful updates
}

// Success/failure rate metrics
export interface SuccessRateMetrics {
  projectId: string;
  timeRange: {
    start: string;
    end: string;
  };
  totalOperations: number;
  successfulOperations: number;
  failedOperations: number;
  cancelledOperations: number;
  successRate: number; // percentage
  failureRate: number; // percentage
  averageProcessingTime: number; // in milliseconds
  operationsByType: Record<string, OperationStats>;
  operationsByStatus: Record<string, number>;
}

export interface OperationStats {
  total: number;
  successful: number;
  failed: number;
  averageDuration: number;
  successRate: number;
}

// Real-time metrics aggregation
export interface RealTimeMetrics {
  projectId: string;
  timestamp: string;
  activeConnections: number;
  activeOperations: number;
  operationsPerMinute: number;
  averageLatency: number;
  memoryUsageTrend: 'increasing' | 'decreasing' | 'stable';
  errorRate: number;
  throughput: number; // operations per second
}

// Analytics dashboard data
export interface AnalyticsDashboardData {
  projectId: string;
  timeRange: {
    start: string;
    end: string;
  };
  summary: {
    totalOperations: number;
    successRate: number;
    averageProcessingTime: number;
    totalDataProcessed: number; // in MB
    activeUsers: number;
  };
  trends: {
    processingTime: TrendData;
    successRate: TrendData;
    memoryUsage: TrendData;
    connectionStability: TrendData;
  };
  topOperations: ProcessingMetrics[];
  recentErrors: ErrorMetrics[];
  performanceInsights: PerformanceInsight[];
}

export interface TrendData {
  current: number;
  previous: number;
  change: number;
  changePercentage: number;
  direction: 'up' | 'down' | 'stable';
  data: Array<{ timestamp: string; value: number }>;
}

export interface ErrorMetrics {
  operationId: string;
  timestamp: string;
  errorType: string;
  errorMessage: string;
  operationType: string;
  projectId: string;
  retryCount?: number;
  resolution?: string;
}

export interface PerformanceInsight {
  id: string;
  type: 'warning' | 'info' | 'success' | 'error';
  title: string;
  description: string;
  recommendation?: string;
  impact: 'low' | 'medium' | 'high';
  timestamp: string;
  resolved?: boolean;
}

// Metrics storage and persistence
export interface MetricsStorage {
  processingMetrics: ProcessingMetrics[];
  webSocketMetrics: WebSocketMetrics[];
  performanceMetrics: PerformanceMetrics[];
  progressMetrics: ProgressMetrics[];
  maxEntries: number;
  retentionPeriod: number; // in days
}

// Export formats
export interface MetricsExportData {
  format: 'json' | 'csv';
  timeRange: {
    start: string;
    end: string;
  };
  projectId?: string;
  metrics: {
    processing?: boolean;
    websocket?: boolean;
    performance?: boolean;
    progress?: boolean;
  };
  includeMetadata: boolean;
}

// Metrics service configuration
export interface MetricsConfig {
  enabled: boolean;
  projectId: string;
  storage: {
    type: 'localStorage' | 'sessionStorage' | 'memory';
    maxEntries: number;
    retentionPeriod: number;
  };
  tracking: {
    processing: boolean;
    websocket: boolean;
    performance: boolean;
    memory: boolean;
    progress: boolean;
  };
  export: {
    formats: ('json' | 'csv')[];
    autoExport: boolean;
    exportInterval: number; // in minutes
  };
  alerts: {
    enabled: boolean;
    thresholds: {
      errorRate: number;
      memoryUsage: number;
      processingTime: number;
      connectionFailures: number;
    };
  };
}

// Hook return types
export interface UseMetricsReturn {
  metrics: AnalyticsDashboardData;
  isLoading: boolean;
  error: string | null;
  refresh: () => void;
  exportData: (format: 'json' | 'csv') => Promise<string>;
  clearMetrics: () => void;
}

export interface UseProcessingMetricsReturn {
  trackProcessingStart: (operationId: string, operationType: string, documentId?: string) => void;
  trackProcessingEnd: (operationId: string, status: 'success' | 'failed', errorMessage?: string) => void;
  trackProcessingStage: (operationId: string, stageName: string, progress?: number) => void;
  currentMetrics: ProcessingMetrics[];
}

export interface UseWebSocketMetricsReturn {
  trackConnectionEvent: (event: WebSocketMetrics['event'], details?: Partial<WebSocketMetrics>) => void;
  trackMessage: (direction: 'sent' | 'received', messageType?: string) => void;
  connectionMetrics: WebSocketMetrics[];
  connectionStability: number; // percentage
}

export interface UsePerformanceMetricsReturn {
  trackPerformance: () => void;
  memoryUsage: PerformanceMetrics['memoryUsage'];
  performanceData: PerformanceMetrics[];
  isTracking: boolean;
}

// Utility types
export type MetricType = 'processing' | 'websocket' | 'performance' | 'progress' | 'success_rate';
export type TimeRange = '1h' | '24h' | '7d' | '30d' | 'custom';
export type AggregationType = 'avg' | 'sum' | 'min' | 'max' | 'count' | 'rate';

// Chart data types for visualization
export interface ChartDataPoint {
  timestamp: string;
  value: number;
  label?: string;
  metadata?: Record<string, any>;
}

export interface ChartSeries {
  name: string;
  data: ChartDataPoint[];
  color?: string;
  type?: 'line' | 'bar' | 'area';
}

export interface ChartConfig {
  title: string;
  xAxis: {
    type: 'time' | 'category';
    label?: string;
  };
  yAxis: {
    label?: string;
    unit?: string;
  };
  series: ChartSeries[];
  timeRange: TimeRange;
}