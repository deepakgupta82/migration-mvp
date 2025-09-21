/**
 * Metrics Export Utilities
 * Provides comprehensive export functionality for analytics data
 */

import {
  ProcessingMetrics,
  WebSocketMetrics,
  PerformanceMetrics,
  AnalyticsDashboardData,
  MetricsExportData,
  TimeRange
} from '../types/metrics';
import { metricsService } from '../services/MetricsService';

export interface ExportOptions {
  format: 'json' | 'csv' | 'xml' | 'pdf';
  timeRange: TimeRange;
  projectId?: string;
  includeMetadata: boolean;
  compress: boolean;
  filename?: string;
}

export interface ExportResult {
  data: string | Blob;
  filename: string;
  mimeType: string;
  size: number;
}

/**
 * Export metrics data in various formats
 */
export class MetricsExporter {
  static async export(options: ExportOptions): Promise<ExportResult> {
    const { format, timeRange, projectId, includeMetadata } = options;

    // Get dashboard data
    const dashboardData = metricsService.getAnalyticsDashboard(timeRange);

    // Filter by project if specified
    const filteredData = projectId
      ? this.filterByProject(dashboardData, projectId)
      : dashboardData;

    switch (format) {
      case 'json':
        return this.exportJSON(filteredData, options);
      case 'csv':
        return this.exportCSV(filteredData, options);
      case 'xml':
        return this.exportXML(filteredData, options);
      case 'pdf':
        return this.exportPDF(filteredData, options);
      default:
        throw new Error(`Unsupported export format: ${format}`);
    }
  }

  private static filterByProject(data: AnalyticsDashboardData, projectId: string): AnalyticsDashboardData {
    return {
      ...data,
      topOperations: data.topOperations.filter(op => op.projectId === projectId),
      recentErrors: data.recentErrors.filter(err => err.projectId === projectId)
    };
  }

  private static exportJSON(data: AnalyticsDashboardData, options: ExportOptions): ExportResult {
    const exportData = {
      metadata: {
        exportDate: new Date().toISOString(),
        timeRange: data.timeRange,
        projectId: options.projectId || 'all',
        format: 'json',
        version: '1.0'
      },
      data: options.includeMetadata ? data : {
        summary: data.summary,
        trends: data.trends,
        topOperations: data.topOperations,
        recentErrors: data.recentErrors,
        performanceInsights: data.performanceInsights
      }
    };

    const jsonString = JSON.stringify(exportData, null, 2);
    const filename = this.generateFilename('analytics', options, 'json');

    return {
      data: jsonString,
      filename,
      mimeType: 'application/json',
      size: jsonString.length
    };
  }

  private static exportCSV(data: AnalyticsDashboardData, options: ExportOptions): ExportResult {
    const csvRows: string[] = [];

    // Summary section
    csvRows.push('=== SUMMARY ===');
    csvRows.push('Metric,Value');
    csvRows.push(`Total Operations,${data.summary.totalOperations}`);
    csvRows.push(`Success Rate,${data.summary.successRate.toFixed(2)}%`);
    csvRows.push(`Average Processing Time,${(data.summary.averageProcessingTime / 1000).toFixed(2)}s`);
    csvRows.push(`Total Data Processed,${this.formatBytes(data.summary.totalDataProcessed)}`);
    csvRows.push(`Active Users,${data.summary.activeUsers}`);
    csvRows.push('');

    // Trends section
    csvRows.push('=== TRENDS ===');
    csvRows.push('Metric,Current,Previous,Change,Change %,Direction');
    csvRows.push(`Processing Time,${(data.trends.processingTime.current / 1000).toFixed(2)}s,${(data.trends.processingTime.previous / 1000).toFixed(2)}s,${data.trends.processingTime.change.toFixed(2)},${data.trends.processingTime.changePercentage.toFixed(2)}%,${data.trends.processingTime.direction}`);
    csvRows.push(`Success Rate,${data.trends.successRate.current.toFixed(2)}%,${data.trends.successRate.previous.toFixed(2)}%,${data.trends.successRate.change.toFixed(2)},${data.trends.successRate.changePercentage.toFixed(2)}%,${data.trends.successRate.direction}`);
    csvRows.push(`Memory Usage,${data.trends.memoryUsage.current.toFixed(2)}%,${data.trends.memoryUsage.previous.toFixed(2)}%,${data.trends.memoryUsage.change.toFixed(2)},${data.trends.memoryUsage.changePercentage.toFixed(2)}%,${data.trends.memoryUsage.direction}`);
    csvRows.push(`Connection Stability,${data.trends.connectionStability.current.toFixed(2)}%,${data.trends.connectionStability.previous.toFixed(2)}%,${data.trends.connectionStability.change.toFixed(2)},${data.trends.connectionStability.changePercentage.toFixed(2)}%,${data.trends.connectionStability.direction}`);
    csvRows.push('');

    // Top operations
    if (data.topOperations.length > 0) {
      csvRows.push('=== TOP OPERATIONS ===');
      csvRows.push('Rank,Operation Type,Status,Duration (s),Start Time,Project ID');
      data.topOperations.forEach((op, index) => {
        csvRows.push(`${index + 1},${op.operationType},${op.status},${(op.duration / 1000).toFixed(2)},${op.startTime},${op.projectId}`);
      });
      csvRows.push('');
    }

    // Recent errors
    if (data.recentErrors.length > 0) {
      csvRows.push('=== RECENT ERRORS ===');
      csvRows.push('Timestamp,Operation ID,Error Type,Error Message,Operation Type,Project ID');
      data.recentErrors.forEach(err => {
        csvRows.push(`${err.timestamp},${err.operationId},${err.errorType},"${err.errorMessage}",${err.operationType},${err.projectId}`);
      });
      csvRows.push('');
    }

    // Performance insights
    if (data.performanceInsights.length > 0) {
      csvRows.push('=== PERFORMANCE INSIGHTS ===');
      csvRows.push('Timestamp,Type,Title,Description,Impact,Resolved');
      data.performanceInsights.forEach(insight => {
        csvRows.push(`${insight.timestamp},${insight.type},"${insight.title}","${insight.description}",${insight.impact},${insight.resolved || false}`);
      });
    }

    const csvString = csvRows.join('\n');
    const filename = this.generateFilename('analytics', options, 'csv');

    return {
      data: csvString,
      filename,
      mimeType: 'text/csv',
      size: csvString.length
    };
  }

  private static exportXML(data: AnalyticsDashboardData, options: ExportOptions): ExportResult {
    const xmlContent = `<?xml version="1.0" encoding="UTF-8"?>
<analytics-export>
  <metadata>
    <export-date>${new Date().toISOString()}</export-date>
    <time-range>
      <start>${data.timeRange.start}</start>
      <end>${data.timeRange.end}</end>
    </time-range>
    <project-id>${options.projectId || 'all'}</project-id>
    <format>xml</format>
    <version>1.0</version>
  </metadata>
  <data>
    <summary>
      <total-operations>${data.summary.totalOperations}</total-operations>
      <success-rate>${data.summary.successRate}</success-rate>
      <average-processing-time>${data.summary.averageProcessingTime}</average-processing-time>
      <total-data-processed>${data.summary.totalDataProcessed}</total-data-processed>
      <active-users>${data.summary.activeUsers}</active-users>
    </summary>
    <trends>
      <processing-time>
        <current>${data.trends.processingTime.current}</current>
        <previous>${data.trends.processingTime.previous}</previous>
        <change>${data.trends.processingTime.change}</change>
        <change-percentage>${data.trends.processingTime.changePercentage}</change-percentage>
        <direction>${data.trends.processingTime.direction}</direction>
      </processing-time>
      <success-rate>
        <current>${data.trends.successRate.current}</current>
        <previous>${data.trends.successRate.previous}</previous>
        <change>${data.trends.successRate.change}</change>
        <change-percentage>${data.trends.successRate.changePercentage}</change-percentage>
        <direction>${data.trends.successRate.direction}</direction>
      </success-rate>
      <memory-usage>
        <current>${data.trends.memoryUsage.current}</current>
        <previous>${data.trends.memoryUsage.previous}</previous>
        <change>${data.trends.memoryUsage.change}</change>
        <change-percentage>${data.trends.memoryUsage.changePercentage}</change-percentage>
        <direction>${data.trends.memoryUsage.direction}</direction>
      </memory-usage>
      <connection-stability>
        <current>${data.trends.connectionStability.current}</current>
        <previous>${data.trends.connectionStability.previous}</previous>
        <change>${data.trends.connectionStability.change}</change>
        <change-percentage>${data.trends.connectionStability.changePercentage}</change-percentage>
        <direction>${data.trends.connectionStability.direction}</direction>
      </connection-stability>
    </trends>
    ${data.topOperations.length > 0 ? `
    <top-operations>
      ${data.topOperations.map(op => `
      <operation>
        <operation-id>${op.operationId}</operation-id>
        <operation-type>${op.operationType}</operation-type>
        <status>${op.status}</status>
        <duration>${op.duration}</duration>
        <start-time>${op.startTime}</start-time>
        <project-id>${op.projectId}</project-id>
      </operation>`).join('')}
    </top-operations>` : ''}
    ${data.recentErrors.length > 0 ? `
    <recent-errors>
      ${data.recentErrors.map(err => `
      <error>
        <timestamp>${err.timestamp}</timestamp>
        <operation-id>${err.operationId}</operation-id>
        <error-type>${err.errorType}</error-type>
        <error-message><![CDATA[${err.errorMessage}]]></error-message>
        <operation-type>${err.operationType}</operation-type>
        <project-id>${err.projectId}</project-id>
      </error>`).join('')}
    </recent-errors>` : ''}
    ${data.performanceInsights.length > 0 ? `
    <performance-insights>
      ${data.performanceInsights.map(insight => `
      <insight>
        <timestamp>${insight.timestamp}</timestamp>
        <type>${insight.type}</type>
        <title><![CDATA[${insight.title}]]></title>
        <description><![CDATA[${insight.description}]]></description>
        <impact>${insight.impact}</impact>
        <resolved>${insight.resolved || false}</resolved>
      </insight>`).join('')}
    </performance-insights>` : ''}
  </data>
</analytics-export>`;

    const filename = this.generateFilename('analytics', options, 'xml');

    return {
      data: xmlContent,
      filename,
      mimeType: 'application/xml',
      size: xmlContent.length
    };
  }

  private static async exportPDF(data: AnalyticsDashboardData, options: ExportOptions): Promise<ExportResult> {
    // For PDF export, we'll create a simple HTML-based PDF
    const htmlContent = this.generateHTMLReport(data, options);

    // In a real implementation, you would use a library like jsPDF or Puppeteer
    // For now, we'll return the HTML as a blob
    const blob = new Blob([htmlContent], { type: 'text/html' });
    const filename = this.generateFilename('analytics', options, 'html');

    return {
      data: blob,
      filename,
      mimeType: 'text/html',
      size: htmlContent.length
    };
  }

  private static generateHTMLReport(data: AnalyticsDashboardData, options: ExportOptions): string {
    return `
<!DOCTYPE html>
<html>
<head>
  <title>Analytics Report - ${options.projectId || 'All Projects'}</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 20px; }
    .header { text-align: center; border-bottom: 2px solid #333; padding-bottom: 20px; margin-bottom: 30px; }
    .section { margin-bottom: 30px; }
    .metric-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; }
    .metric-card { border: 1px solid #ddd; padding: 15px; border-radius: 5px; }
    .metric-value { font-size: 24px; font-weight: bold; color: #2563eb; }
    .trend { font-size: 14px; margin-top: 5px; }
    .trend.up { color: #dc2626; }
    .trend.down { color: #16a34a; }
    .trend.stable { color: #6b7280; }
    table { width: 100%; border-collapse: collapse; margin-top: 15px; }
    th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
    th { background-color: #f5f5f5; }
  </style>
</head>
<body>
  <div class="header">
    <h1>Analytics Report</h1>
    <p>Generated on ${new Date().toLocaleString()}</p>
    <p>Time Range: ${new Date(data.timeRange.start).toLocaleString()} - ${new Date(data.timeRange.end).toLocaleString()}</p>
    ${options.projectId ? `<p>Project: ${options.projectId}</p>` : '<p>All Projects</p>'}
  </div>

  <div class="section">
    <h2>Summary</h2>
    <div class="metric-grid">
      <div class="metric-card">
        <div>Total Operations</div>
        <div class="metric-value">${data.summary.totalOperations}</div>
      </div>
      <div class="metric-card">
        <div>Success Rate</div>
        <div class="metric-value">${data.summary.successRate.toFixed(1)}%</div>
      </div>
      <div class="metric-card">
        <div>Avg Processing Time</div>
        <div class="metric-value">${(data.summary.averageProcessingTime / 1000).toFixed(1)}s</div>
      </div>
      <div class="metric-card">
        <div>Data Processed</div>
        <div class="metric-value">${this.formatBytes(data.summary.totalDataProcessed)}</div>
      </div>
    </div>
  </div>

  <div class="section">
    <h2>Trends</h2>
    <div class="metric-grid">
      <div class="metric-card">
        <div>Processing Time</div>
        <div class="metric-value">${(data.trends.processingTime.current / 1000).toFixed(1)}s</div>
        <div class="trend ${data.trends.processingTime.direction}">
          ${data.trends.processingTime.changePercentage > 0 ? '+' : ''}${data.trends.processingTime.changePercentage.toFixed(1)}%
        </div>
      </div>
      <div class="metric-card">
        <div>Success Rate</div>
        <div class="metric-value">${data.trends.successRate.current.toFixed(1)}%</div>
        <div class="trend ${data.trends.successRate.direction}">
          ${data.trends.successRate.changePercentage > 0 ? '+' : ''}${data.trends.successRate.changePercentage.toFixed(1)}%
        </div>
      </div>
      <div class="metric-card">
        <div>Memory Usage</div>
        <div class="metric-value">${data.trends.memoryUsage.current.toFixed(1)}%</div>
        <div class="trend ${data.trends.memoryUsage.direction}">
          ${data.trends.memoryUsage.changePercentage > 0 ? '+' : ''}${data.trends.memoryUsage.changePercentage.toFixed(1)}%
        </div>
      </div>
      <div class="metric-card">
        <div>Connection Stability</div>
        <div class="metric-value">${data.trends.connectionStability.current.toFixed(1)}%</div>
        <div class="trend ${data.trends.connectionStability.direction}">
          ${data.trends.connectionStability.changePercentage > 0 ? '+' : ''}${data.trends.connectionStability.changePercentage.toFixed(1)}%
        </div>
      </div>
    </div>
  </div>

  ${data.topOperations.length > 0 ? `
  <div class="section">
    <h2>Top Operations</h2>
    <table>
      <thead>
        <tr>
          <th>Operation Type</th>
          <th>Status</th>
          <th>Duration</th>
          <th>Start Time</th>
        </tr>
      </thead>
      <tbody>
        ${data.topOperations.slice(0, 10).map(op => `
        <tr>
          <td>${op.operationType}</td>
          <td>${op.status}</td>
          <td>${(op.duration / 1000).toFixed(1)}s</td>
          <td>${new Date(op.startTime).toLocaleString()}</td>
        </tr>`).join('')}
      </tbody>
    </table>
  </div>` : ''}

  ${data.recentErrors.length > 0 ? `
  <div class="section">
    <h2>Recent Errors</h2>
    <table>
      <thead>
        <tr>
          <th>Timestamp</th>
          <th>Error Type</th>
          <th>Message</th>
          <th>Operation</th>
        </tr>
      </thead>
      <tbody>
        ${data.recentErrors.map(err => `
        <tr>
          <td>${new Date(err.timestamp).toLocaleString()}</td>
          <td>${err.errorType}</td>
          <td>${err.errorMessage}</td>
          <td>${err.operationType}</td>
        </tr>`).join('')}
      </tbody>
    </table>
  </div>` : ''}
</body>
</html>`;
  }

  private static generateFilename(prefix: string, options: ExportOptions, extension: string): string {
    const timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, '-');
    const projectPart = options.projectId ? `_${options.projectId}` : '';
    const customName = options.filename ? `_${options.filename}` : '';

    return `${prefix}${projectPart}${customName}_${timestamp}.${extension}`;
  }

  private static formatBytes(bytes: number): string {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }
}

/**
 * Quick export functions for common use cases
 */
export const exportToJSON = async (projectId?: string, timeRange: TimeRange = '24h'): Promise<ExportResult> => {
  return MetricsExporter.export({
    format: 'json',
    timeRange,
    projectId,
    includeMetadata: true,
    compress: false
  });
};

export const exportToCSV = async (projectId?: string, timeRange: TimeRange = '24h'): Promise<ExportResult> => {
  return MetricsExporter.export({
    format: 'csv',
    timeRange,
    projectId,
    includeMetadata: false,
    compress: false
  });
};

export const exportToPDF = async (projectId?: string, timeRange: TimeRange = '24h'): Promise<ExportResult> => {
  return MetricsExporter.export({
    format: 'pdf',
    timeRange,
    projectId,
    includeMetadata: true,
    compress: false
  });
};

/**
 * Download helper function
 */
export const downloadExport = (result: ExportResult): void => {
  const url = result.data instanceof Blob
    ? URL.createObjectURL(result.data)
    : URL.createObjectURL(new Blob([result.data], { type: result.mimeType }));

  const a = document.createElement('a');
  a.href = url;
  a.download = result.filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
};

/**
 * Batch export multiple formats
 */
export const exportMultipleFormats = async (
  formats: ('json' | 'csv' | 'xml' | 'pdf')[],
  projectId?: string,
  timeRange: TimeRange = '24h'
): Promise<ExportResult[]> => {
  const promises = formats.map(format =>
    MetricsExporter.export({
      format,
      timeRange,
      projectId,
      includeMetadata: true,
      compress: false
    })
  );

  return Promise.all(promises);
};