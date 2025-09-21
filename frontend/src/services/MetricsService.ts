/**
 * Comprehensive Metrics Tracking Service for Migration Platform
 * Handles all analytics, performance monitoring, and data persistence
 */

import {
  ProcessingMetrics,
  WebSocketMetrics,
  PerformanceMetrics,
  ProgressMetrics,
  SuccessRateMetrics,
  RealTimeMetrics,
  AnalyticsDashboardData,
  MetricsStorage,
  MetricsConfig,
  MetricDataPoint,
  ProcessingStage,
  ErrorMetrics,
  PerformanceInsight,
  TrendData,
  OperationStats,
  MetricsExportData,
  ChartDataPoint,
  ChartSeries,
  ChartConfig,
  TimeRange,
  AggregationType
} from '../types/metrics';

class MetricsService {
  private config: MetricsConfig;
  private storage: MetricsStorage;
  private activeOperations = new Map<string, ProcessingMetrics>();
  private performanceObserver: PerformanceObserver | null = null;
  private memoryInterval: NodeJS.Timeout | null = null;

  constructor(config: Partial<MetricsConfig> = {}) {
    this.config = {
      enabled: true,
      projectId: 'default',
      storage: {
        type: 'localStorage',
        maxEntries: 10000,
        retentionPeriod: 30, // 30 days
        ...config.storage
      },
      tracking: {
        processing: true,
        websocket: true,
        performance: true,
        memory: true,
        progress: true,
        ...config.tracking
      },
      export: {
        formats: ['json', 'csv'],
        autoExport: false,
        exportInterval: 60, // 1 hour
        ...config.export
      },
      alerts: {
        enabled: true,
        thresholds: {
          errorRate: 10, // 10%
          memoryUsage: 80, // 80%
          processingTime: 300000, // 5 minutes
          connectionFailures: 5,
          ...config.alerts?.thresholds
        },
        ...config.alerts
      },
      ...config
    };

    this.storage = {
      processingMetrics: [],
      webSocketMetrics: [],
      performanceMetrics: [],
      progressMetrics: [],
      maxEntries: this.config.storage.maxEntries,
      retentionPeriod: this.config.storage.retentionPeriod
    };

    this.loadFromStorage();
    this.initializePerformanceTracking();
  }

  // Initialize performance tracking
  private initializePerformanceTracking(): void {
    if (!this.config.tracking.performance) return;

    // Performance Observer for navigation and resource timing
    if ('PerformanceObserver' in window) {
      try {
        this.performanceObserver = new PerformanceObserver((list) => {
          list.getEntries().forEach((entry) => {
            this.trackPerformanceMetric({
              memoryUsage: this.getMemoryUsage(),
              renderTime: entry.duration,
              networkLatency: entry.duration
            });
          });
        });

        this.performanceObserver.observe({ entryTypes: ['navigation', 'resource'] });
      } catch (error) {
        console.warn('Performance Observer not supported:', error);
      }
    }

    // Memory usage tracking
    if (this.config.tracking.memory) {
      this.memoryInterval = setInterval(() => {
        this.trackPerformanceMetric({
          memoryUsage: this.getMemoryUsage()
        });
      }, 30000); // Every 30 seconds
    }
  }

  // Get current memory usage
  private getMemoryUsage() {
    if ('memory' in performance) {
      const memory = (performance as any).memory;
      return {
        used: Math.round(memory.usedJSHeapSize / 1024 / 1024), // MB
        total: Math.round(memory.totalJSHeapSize / 1024 / 1024), // MB
        percentage: Math.round((memory.usedJSHeapSize / memory.jsHeapSizeLimit) * 100)
      };
    }

    return {
      used: 0,
      total: 0,
      percentage: 0
    };
  }

  // Public method to get current memory usage
  getCurrentMemoryUsage() {
    return this.getMemoryUsage();
  }

  // Storage operations
  private loadFromStorage(): void {
    if (this.config.storage.type === 'memory') return;

    try {
      const storage = this.config.storage.type === 'localStorage' ? localStorage : sessionStorage;
      const data = storage.getItem('migration_platform_metrics');

      if (data) {
        const parsed = JSON.parse(data);
        this.storage = { ...this.storage, ...parsed };
        this.cleanupOldData();
      }
    } catch (error) {
      console.error('Failed to load metrics from storage:', error);
    }
  }

  private saveToStorage(): void {
    if (this.config.storage.type === 'memory') return;

    try {
      const storage = this.config.storage.type === 'localStorage' ? localStorage : sessionStorage;
      storage.setItem('migration_platform_metrics', JSON.stringify(this.storage));
    } catch (error) {
      console.error('Failed to save metrics to storage:', error);
    }
  }

  private cleanupOldData(): void {
    const cutoffDate = new Date();
    cutoffDate.setDate(cutoffDate.getDate() - this.storage.retentionPeriod);

    const cutoffTime = cutoffDate.toISOString();

    this.storage.processingMetrics = this.storage.processingMetrics.filter(m => m.startTime > cutoffTime);
    this.storage.webSocketMetrics = this.storage.webSocketMetrics.filter(m => m.timestamp > cutoffTime);
    this.storage.performanceMetrics = this.storage.performanceMetrics.filter(m => m.timestamp > cutoffTime);
    this.storage.progressMetrics = this.storage.progressMetrics.filter(m => m.timestamp > cutoffTime);

    // Enforce max entries limit
    this.enforceMaxEntries();
  }

  private enforceMaxEntries(): void {
    if (this.storage.processingMetrics.length > this.storage.maxEntries) {
      this.storage.processingMetrics = this.storage.processingMetrics.slice(-this.storage.maxEntries);
    }
    if (this.storage.webSocketMetrics.length > this.storage.maxEntries) {
      this.storage.webSocketMetrics = this.storage.webSocketMetrics.slice(-this.storage.maxEntries);
    }
    if (this.storage.performanceMetrics.length > this.storage.maxEntries) {
      this.storage.performanceMetrics = this.storage.performanceMetrics.slice(-this.storage.maxEntries);
    }
    if (this.storage.progressMetrics.length > this.storage.maxEntries) {
      this.storage.progressMetrics = this.storage.progressMetrics.slice(-this.storage.maxEntries);
    }
  }

  // Processing metrics tracking
  trackProcessingStart(operationId: string, operationType: string, documentId?: string, fileSize?: number, fileType?: string): void {
    if (!this.config.tracking.processing) return;

    const metrics: ProcessingMetrics = {
      operationId,
      documentId,
      projectId: this.config.projectId,
      startTime: new Date().toISOString(),
      duration: 0,
      status: 'in_progress',
      operationType,
      fileSize,
      fileType,
      processingStages: []
    };

    this.activeOperations.set(operationId, metrics);
  }

  trackProcessingEnd(operationId: string, status: 'success' | 'failed' | 'cancelled', errorMessage?: string, retryCount?: number): void {
    if (!this.config.tracking.processing) return;

    const metrics = this.activeOperations.get(operationId);
    if (!metrics) return;

    const endTime = new Date().toISOString();
    const duration = new Date(endTime).getTime() - new Date(metrics.startTime).getTime();

    const completedMetrics: ProcessingMetrics = {
      ...metrics,
      endTime,
      duration,
      status,
      errorMessage,
      retryCount
    };

    this.storage.processingMetrics.push(completedMetrics);
    this.activeOperations.delete(operationId);
    this.saveToStorage();

    // Check for alerts
    this.checkProcessingAlerts(completedMetrics);
  }

  trackProcessingStage(operationId: string, stageName: string, progress?: number): void {
    if (!this.config.tracking.processing) return;

    const metrics = this.activeOperations.get(operationId);
    if (!metrics) return;

    const stage: ProcessingStage = {
      stageName,
      startTime: new Date().toISOString(),
      status: 'in_progress',
      progress
    };

    metrics.processingStages.push(stage);
  }

  // WebSocket metrics tracking
  trackWebSocketEvent(event: WebSocketMetrics['event'], details: Partial<WebSocketMetrics> = {}): void {
    if (!this.config.tracking.websocket) return;

    const metrics: WebSocketMetrics = {
      projectId: this.config.projectId,
      connectionId: details.connectionId || 'default',
      timestamp: new Date().toISOString(),
      event,
      connectionState: details.connectionState || 'connected',
      duration: details.duration,
      errorMessage: details.errorMessage,
      messageCount: details.messageCount,
      reconnectAttempts: details.reconnectAttempts,
      latency: details.latency
    };

    this.storage.webSocketMetrics.push(metrics);
    this.saveToStorage();

    // Check for connection alerts
    if (event === 'error' || event === 'disconnect') {
      this.checkConnectionAlerts(metrics);
    }
  }

  // Performance metrics tracking
  trackPerformanceMetric(metrics: Omit<PerformanceMetrics, 'timestamp' | 'projectId'>): void {
    if (!this.config.tracking.performance) return;

    const performanceMetrics: PerformanceMetrics = {
      timestamp: new Date().toISOString(),
      projectId: this.config.projectId,
      memoryUsage: metrics.memoryUsage,
      cpuUsage: metrics.cpuUsage,
      networkLatency: metrics.networkLatency,
      domNodes: metrics.domNodes,
      renderTime: metrics.renderTime,
      jsHeapSize: metrics.jsHeapSize,
      jsHeapSizeLimit: metrics.jsHeapSizeLimit
    };

    this.storage.performanceMetrics.push(performanceMetrics);
    this.saveToStorage();

    // Check for performance alerts
    this.checkPerformanceAlerts(performanceMetrics);
  }

  // Progress metrics tracking
  trackProgressUpdate(operationId: string, progressPercentage: number, stage: string, message?: string, estimatedTimeRemaining?: number): void {
    if (!this.config.tracking.progress) return;

    const metrics: ProgressMetrics = {
      operationId,
      projectId: this.config.projectId,
      timestamp: new Date().toISOString(),
      progressPercentage,
      stage,
      message,
      estimatedTimeRemaining,
      updateFrequency: this.calculateUpdateFrequency(operationId),
      reliability: this.calculateProgressReliability(operationId)
    };

    this.storage.progressMetrics.push(metrics);
    this.saveToStorage();
  }

  // Alert checking
  private checkProcessingAlerts(metrics: ProcessingMetrics): void {
    if (!this.config.alerts.enabled) return;

    if (metrics.status === 'failed') {
      this.createInsight('error', 'Processing Operation Failed',
        `Operation ${metrics.operationId} failed after ${metrics.duration}ms`,
        'high', 'Check error logs and retry the operation');
    }

    if (metrics.duration > this.config.alerts.thresholds.processingTime) {
      this.createInsight('warning', 'Slow Processing Detected',
        `Operation ${metrics.operationId} took ${metrics.duration}ms`,
        'medium', 'Consider optimizing the processing pipeline');
    }
  }

  private checkConnectionAlerts(metrics: WebSocketMetrics): void {
    if (!this.config.alerts.enabled) return;

    const recentFailures = this.storage.webSocketMetrics
      .filter(m => m.event === 'error' || m.event === 'disconnect')
      .filter(m => Date.now() - new Date(m.timestamp).getTime() < 3600000) // Last hour
      .length;

    if (recentFailures > this.config.alerts.thresholds.connectionFailures) {
      this.createInsight('warning', 'Connection Instability Detected',
        `${recentFailures} connection issues in the last hour`,
        'high', 'Check network connectivity and WebSocket configuration');
    }
  }

  private checkPerformanceAlerts(metrics: PerformanceMetrics): void {
    if (!this.config.alerts.enabled) return;

    if (metrics.memoryUsage.percentage > this.config.alerts.thresholds.memoryUsage) {
      this.createInsight('warning', 'High Memory Usage',
        `Memory usage at ${metrics.memoryUsage.percentage}%`,
        'medium', 'Consider clearing cache or optimizing memory usage');
    }
  }

  private createInsight(type: 'warning' | 'info' | 'success' | 'error', title: string, description: string, impact: 'low' | 'medium' | 'high', recommendation?: string): void {
    // This would integrate with a notification system
    console.log(`[${type.toUpperCase()}] ${title}: ${description}`);
    if (recommendation) {
      console.log(`Recommendation: ${recommendation}`);
    }
  }

  // Analytics and aggregation
  getAnalyticsDashboard(timeRange: TimeRange = '24h'): AnalyticsDashboardData {
    const now = new Date();
    const startTime = this.getTimeRangeStart(timeRange);

    const filteredProcessing = this.storage.processingMetrics.filter(m => new Date(m.startTime) >= startTime);
    const filteredWebSocket = this.storage.webSocketMetrics.filter(m => new Date(m.timestamp) >= startTime);
    const filteredPerformance = this.storage.performanceMetrics.filter(m => new Date(m.timestamp) >= startTime);

    const totalOperations = filteredProcessing.length;
    const successfulOperations = filteredProcessing.filter(m => m.status === 'success').length;
    const successRate = totalOperations > 0 ? (successfulOperations / totalOperations) * 100 : 0;

    const averageProcessingTime = filteredProcessing.length > 0
      ? filteredProcessing.reduce((sum, m) => sum + m.duration, 0) / filteredProcessing.length
      : 0;

    const totalDataProcessed = filteredProcessing.reduce((sum, m) => sum + (m.fileSize || 0), 0);

    return {
      projectId: this.config.projectId,
      timeRange: { start: startTime.toISOString(), end: now.toISOString() },
      summary: {
        totalOperations,
        successRate,
        averageProcessingTime,
        totalDataProcessed,
        activeUsers: 1 // Would be tracked separately
      },
      trends: {
        processingTime: this.calculateTrend(filteredProcessing.map(m => ({ timestamp: m.startTime, value: m.duration }))),
        successRate: this.calculateSuccessRateTrend(filteredProcessing),
        memoryUsage: this.calculateMemoryTrend(filteredPerformance),
        connectionStability: this.calculateConnectionStabilityTrend(filteredWebSocket)
      },
      topOperations: filteredProcessing
        .sort((a, b) => b.duration - a.duration)
        .slice(0, 10),
      recentErrors: this.getRecentErrors(filteredProcessing),
      performanceInsights: this.generatePerformanceInsights(filteredProcessing, filteredWebSocket, filteredPerformance)
    };
  }

  private getTimeRangeStart(timeRange: TimeRange): Date {
    const now = new Date();
    switch (timeRange) {
      case '1h': return new Date(now.getTime() - 3600000);
      case '24h': return new Date(now.getTime() - 86400000);
      case '7d': return new Date(now.getTime() - 604800000);
      case '30d': return new Date(now.getTime() - 2592000000);
      default: return new Date(now.getTime() - 86400000);
    }
  }

  private calculateTrend(data: Array<{ timestamp: string; value: number }>): TrendData {
    if (data.length === 0) {
      return { current: 0, previous: 0, change: 0, changePercentage: 0, direction: 'stable', data: [] };
    }

    const sorted = data.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
    const midpoint = Math.floor(sorted.length / 2);

    const firstHalf = sorted.slice(0, midpoint);
    const secondHalf = sorted.slice(midpoint);

    const firstHalfAvg = firstHalf.reduce((sum, d) => sum + d.value, 0) / firstHalf.length;
    const secondHalfAvg = secondHalf.reduce((sum, d) => sum + d.value, 0) / secondHalf.length;

    const change = secondHalfAvg - firstHalfAvg;
    const changePercentage = firstHalfAvg > 0 ? (change / firstHalfAvg) * 100 : 0;

    let direction: 'up' | 'down' | 'stable' = 'stable';
    if (Math.abs(changePercentage) > 5) {
      direction = change > 0 ? 'up' : 'down';
    }

    return {
      current: secondHalfAvg,
      previous: firstHalfAvg,
      change,
      changePercentage,
      direction,
      data: sorted
    };
  }

  private calculateSuccessRateTrend(processingMetrics: ProcessingMetrics[]): TrendData {
    const successRates = processingMetrics.map(m => ({
      timestamp: m.startTime,
      value: m.status === 'success' ? 100 : 0
    }));

    return this.calculateTrend(successRates);
  }

  private calculateMemoryTrend(performanceMetrics: PerformanceMetrics[]): TrendData {
    const memoryData = performanceMetrics.map(m => ({
      timestamp: m.timestamp,
      value: m.memoryUsage.percentage
    }));

    return this.calculateTrend(memoryData);
  }

  private calculateConnectionStabilityTrend(webSocketMetrics: WebSocketMetrics[]): TrendData {
    const connectionData = webSocketMetrics.map(m => ({
      timestamp: m.timestamp,
      value: m.connectionState === 'connected' ? 100 : 0
    }));

    return this.calculateTrend(connectionData);
  }

  private getRecentErrors(processingMetrics: ProcessingMetrics[]): ErrorMetrics[] {
    return processingMetrics
      .filter(m => m.status === 'failed')
      .slice(-10)
      .map(m => ({
        operationId: m.operationId,
        timestamp: m.endTime || m.startTime,
        errorType: 'processing_error',
        errorMessage: m.errorMessage || 'Unknown error',
        operationType: m.operationType,
        projectId: m.projectId,
        retryCount: m.retryCount
      }));
  }

  private generatePerformanceInsights(
    processingMetrics: ProcessingMetrics[],
    webSocketMetrics: WebSocketMetrics[],
    performanceMetrics: PerformanceMetrics[]
  ): PerformanceInsight[] {
    const insights: PerformanceInsight[] = [];

    // Processing time insights
    const avgProcessingTime = processingMetrics.reduce((sum, m) => sum + m.duration, 0) / processingMetrics.length;
    if (avgProcessingTime > 120000) { // 2 minutes
      insights.push({
        id: 'slow_processing',
        type: 'warning',
        title: 'Slow Processing Detected',
        description: `Average processing time is ${Math.round(avgProcessingTime / 1000)}s`,
        recommendation: 'Consider optimizing the processing pipeline or increasing resources',
        impact: 'high',
        timestamp: new Date().toISOString()
      });
    }

    // Memory usage insights
    const avgMemoryUsage = performanceMetrics.reduce((sum, m) => sum + m.memoryUsage.percentage, 0) / performanceMetrics.length;
    if (avgMemoryUsage > 70) {
      insights.push({
        id: 'high_memory',
        type: 'warning',
        title: 'High Memory Usage',
        description: `Average memory usage is ${Math.round(avgMemoryUsage)}%`,
        recommendation: 'Monitor memory usage and consider memory optimization',
        impact: 'medium',
        timestamp: new Date().toISOString()
      });
    }

    return insights;
  }

  // Utility methods
  private calculateUpdateFrequency(operationId: string): number {
    const recentUpdates = this.storage.progressMetrics
      .filter(m => m.operationId === operationId)
      .filter(m => Date.now() - new Date(m.timestamp).getTime() < 60000) // Last minute
      .length;

    return recentUpdates;
  }

  private calculateProgressReliability(operationId: string): number {
    const operationUpdates = this.storage.progressMetrics.filter(m => m.operationId === operationId);
    if (operationUpdates.length === 0) return 100;

    const expectedUpdates = Math.max(1, operationUpdates.length);
    const actualUpdates = operationUpdates.length;

    return Math.min(100, (actualUpdates / expectedUpdates) * 100);
  }

  // Export functionality
  async exportData(format: 'json' | 'csv', timeRange?: TimeRange): Promise<string> {
    const startTime = timeRange ? this.getTimeRangeStart(timeRange) : new Date(0);
    const data = this.getAnalyticsDashboard(timeRange);

    if (format === 'json') {
      return JSON.stringify(data, null, 2);
    } else {
      // CSV export
      const csvRows = [
        ['Metric', 'Value', 'Timestamp'],
        ['Total Operations', data.summary.totalOperations.toString(), new Date().toISOString()],
        ['Success Rate', `${data.summary.successRate.toFixed(2)}%`, new Date().toISOString()],
        ['Average Processing Time', `${(data.summary.averageProcessingTime / 1000).toFixed(2)}s`, new Date().toISOString()],
        ['Total Data Processed', `${(data.summary.totalDataProcessed / 1024 / 1024).toFixed(2)}MB`, new Date().toISOString()]
      ];

      return csvRows.map(row => row.join(',')).join('\n');
    }
  }

  // Cleanup
  clearMetrics(): void {
    this.storage = {
      processingMetrics: [],
      webSocketMetrics: [],
      performanceMetrics: [],
      progressMetrics: [],
      maxEntries: this.config.storage.maxEntries,
      retentionPeriod: this.config.storage.retentionPeriod
    };
    this.activeOperations.clear();
    this.saveToStorage();
  }

  // Getters
  getProcessingMetrics(): ProcessingMetrics[] {
    return [...this.storage.processingMetrics];
  }

  getWebSocketMetrics(): WebSocketMetrics[] {
    return [...this.storage.webSocketMetrics];
  }

  getPerformanceMetrics(): PerformanceMetrics[] {
    return [...this.storage.performanceMetrics];
  }

  getProgressMetrics(): ProgressMetrics[] {
    return [...this.storage.progressMetrics];
  }

  getActiveOperations(): ProcessingMetrics[] {
    return Array.from(this.activeOperations.values());
  }

  // Configuration
  updateConfig(config: Partial<MetricsConfig>): void {
    this.config = { ...this.config, ...config };
    this.saveToStorage();
  }

  getConfig(): MetricsConfig {
    return { ...this.config };
  }

  // Cleanup on destroy
  destroy(): void {
    if (this.performanceObserver) {
      this.performanceObserver.disconnect();
    }
    if (this.memoryInterval) {
      clearInterval(this.memoryInterval);
    }
    this.clearMetrics();
  }
}

// Singleton instance
export const metricsService = new MetricsService();

// Export the class for testing or custom instances
export { MetricsService };