/**
 * Real-time Metrics Visualization Components
 * Provides charts and graphs for analytics data
 */

import React, { useMemo } from 'react';
import {
  Card,
  Text,
  Group,
  Stack,
  SimpleGrid,
  Paper,
  Select,
  Button,
  ActionIcon,
  Tooltip,
  Loader,
  Center
} from '@mantine/core';
import {
  IconChartLine,
  IconChartBar,
  IconChartArea,
  IconRefresh,
  IconDownload,
  IconZoomIn,
  IconZoomOut
} from '@tabler/icons-react';
import { useMetrics, useRealTimeMetrics } from '../hooks/useMetrics';
import { TimeRange, ChartDataPoint, ChartSeries } from '../types/metrics';

interface MetricsVisualizationProps {
  projectId: string;
  timeRange?: TimeRange;
  height?: number;
  showControls?: boolean;
  autoRefresh?: boolean;
}

// Simple chart components (fallback if recharts is not available)
const SimpleLineChart: React.FC<{
  data: ChartDataPoint[];
  height: number;
  color?: string;
  title?: string;
}> = ({ data, height, color = '#228be6', title }) => {
  const maxValue = Math.max(...data.map(d => d.value));
  const minValue = Math.min(...data.map(d => d.value));

  return (
    <div style={{ height, position: 'relative' }}>
      {title && (
        <Text size="sm" fw={600} mb="xs">{title}</Text>
      )}
      <svg width="100%" height={height - 40} style={{ border: '1px solid #e9ecef', borderRadius: '4px' }}>
        {/* Grid lines */}
        {[0, 0.25, 0.5, 0.75, 1].map(ratio => (
          <line
            key={ratio}
            x1="0"
            y1={ratio * (height - 40)}
            x2="100%"
            y2={ratio * (height - 40)}
            stroke="#f1f3f5"
            strokeWidth="1"
          />
        ))}

        {/* Data line */}
        <polyline
          fill="none"
          stroke={color}
          strokeWidth="2"
          points={
            data.map((point, index) => {
              const x = (index / (data.length - 1)) * 100;
              const y = ((maxValue - point.value) / (maxValue - minValue || 1)) * (height - 40);
              return `${x}%,${y}`;
            }).join(' ')
          }
        />

        {/* Data points */}
        {data.map((point, index) => {
          const x = (index / (data.length - 1)) * 100;
          const y = ((maxValue - point.value) / (maxValue - minValue || 1)) * (height - 40);
          return (
            <circle
              key={index}
              cx={`${x}%`}
              cy={y}
              r="3"
              fill={color}
              stroke="white"
              strokeWidth="2"
            >
              <title>{`${point.label || ''}: ${point.value.toFixed(2)}`}</title>
            </circle>
          );
        })}
      </svg>
    </div>
  );
};

const SimpleBarChart: React.FC<{
  data: ChartDataPoint[];
  height: number;
  color?: string;
  title?: string;
}> = ({ data, height, color = '#228be6', title }) => {
  const maxValue = Math.max(...data.map(d => d.value));

  return (
    <div style={{ height, position: 'relative' }}>
      {title && (
        <Text size="sm" fw={600} mb="xs">{title}</Text>
      )}
      <svg width="100%" height={height - 40} style={{ border: '1px solid #e9ecef', borderRadius: '4px' }}>
        {/* Grid lines */}
        {[0, 0.25, 0.5, 0.75, 1].map(ratio => (
          <line
            key={ratio}
            x1="0"
            y1={ratio * (height - 40)}
            x2="100%"
            y2={ratio * (height - 40)}
            stroke="#f1f3f5"
            strokeWidth="1"
          />
        ))}

        {/* Bars */}
        {data.map((point, index) => {
          const barWidth = 80 / data.length; // 80% of available width
          const x = (index * barWidth) + 10; // 10% margin on each side
          const barHeight = (point.value / maxValue) * (height - 40);
          const y = (height - 40) - barHeight;

          return (
            <rect
              key={index}
              x={`${x}%`}
              y={y}
              width={`${barWidth}%`}
              height={barHeight}
              fill={color}
              stroke="white"
              strokeWidth="1"
            >
              <title>{`${point.label || ''}: ${point.value.toFixed(2)}`}</title>
            </rect>
          );
        })}
      </svg>
    </div>
  );
};

const SimpleAreaChart: React.FC<{
  data: ChartDataPoint[];
  height: number;
  color?: string;
  title?: string;
}> = ({ data, height, color = '#228be6', title }) => {
  const maxValue = Math.max(...data.map(d => d.value));
  const minValue = Math.min(...data.map(d => d.value));

  const points = data.map((point, index) => {
    const x = (index / (data.length - 1)) * 100;
    const y = ((maxValue - point.value) / (maxValue - minValue || 1)) * (height - 40);
    return `${x},${y}`;
  }).join(' ');

  const areaPoints = `0,${height - 40} ${points} 100%,${height - 40}`;

  return (
    <div style={{ height, position: 'relative' }}>
      {title && (
        <Text size="sm" fw={600} mb="xs">{title}</Text>
      )}
      <svg width="100%" height={height - 40} style={{ border: '1px solid #e9ecef', borderRadius: '4px' }}>
        {/* Grid lines */}
        {[0, 0.25, 0.5, 0.75, 1].map(ratio => (
          <line
            key={ratio}
            x1="0"
            y1={ratio * (height - 40)}
            x2="100%"
            y2={ratio * (height - 40)}
            stroke="#f1f3f5"
            strokeWidth="1"
          />
        ))}

        {/* Area fill */}
        <polygon
          fill={color}
          fillOpacity="0.3"
          stroke="none"
          points={areaPoints}
        />

        {/* Data line */}
        <polyline
          fill="none"
          stroke={color}
          strokeWidth="2"
          points={points}
        />

        {/* Data points */}
        {data.map((point, index) => {
          const x = (index / (data.length - 1)) * 100;
          const y = ((maxValue - point.value) / (maxValue - minValue || 1)) * (height - 40);
          return (
            <circle
              key={index}
              cx={`${x}%`}
              cy={y}
              r="3"
              fill={color}
              stroke="white"
              strokeWidth="2"
            >
              <title>{`${point.label || ''}: ${point.value.toFixed(2)}`}</title>
            </circle>
          );
        })}
      </svg>
    </div>
  );
};

export const MetricsVisualization: React.FC<MetricsVisualizationProps> = ({
  projectId,
  timeRange = '24h',
  height = 300,
  showControls = true,
  autoRefresh = true
}) => {
  const { metrics, isLoading, error, refresh } = useMetrics(projectId, timeRange);
  const realTimeData = useRealTimeMetrics(projectId);

  // Transform metrics data for charts
  const chartData = useMemo(() => {
    if (!metrics) return null;

    const processingTimeData: ChartDataPoint[] = metrics.trends.processingTime.data.map(d => ({
      timestamp: d.timestamp,
      value: d.value / 1000, // Convert to seconds
      label: 'Processing Time (s)'
    }));

    const successRateData: ChartDataPoint[] = metrics.trends.successRate.data.map(d => ({
      timestamp: d.timestamp,
      value: d.value,
      label: 'Success Rate (%)'
    }));

    const memoryUsageData: ChartDataPoint[] = metrics.trends.memoryUsage.data.map(d => ({
      timestamp: d.timestamp,
      value: d.value,
      label: 'Memory Usage (%)'
    }));

    const operationsData: ChartDataPoint[] = [
      { timestamp: new Date().toISOString(), value: metrics.summary.totalOperations, label: 'Total Operations' },
      { timestamp: new Date().toISOString(), value: realTimeData.activeOperations, label: 'Active Operations' }
    ];

    return {
      processingTime: processingTimeData,
      successRate: successRateData,
      memoryUsage: memoryUsageData,
      operations: operationsData
    };
  }, [metrics, realTimeData]);

  const formatTimestamp = (timestamp: string) => {
    return new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  if (error) {
    return (
      <Card p="md" radius="md" withBorder>
        <Text c="red">Error loading visualization: {error}</Text>
      </Card>
    );
  }

  if (isLoading || !chartData) {
    return (
      <Card p="md" radius="md" withBorder>
        <Center style={{ height }}>
          <Stack align="center" gap="md">
            <Loader size="lg" />
            <Text>Loading visualization...</Text>
          </Stack>
        </Center>
      </Card>
    );
  }

  return (
    <Stack gap="md">
      {showControls && (
        <Card p="md" radius="md" withBorder>
          <Group justify="space-between" align="center">
            <Text fw={600}>Metrics Visualization</Text>
            <Group>
              <Select
                size="sm"
                value={timeRange}
                onChange={() => {}} // Would implement time range change
                data={[
                  { value: '1h', label: 'Last Hour' },
                  { value: '24h', label: 'Last 24 Hours' },
                  { value: '7d', label: 'Last 7 Days' },
                  { value: '30d', label: 'Last 30 Days' }
                ]}
              />
              <ActionIcon variant="light" onClick={refresh}>
                <IconRefresh size={16} />
              </ActionIcon>
            </Group>
          </Group>
        </Card>
      )}

      <SimpleGrid cols={{ base: 1, lg: 2 }} spacing="md">
        {/* Processing Time Trend */}
        <Card p="md" radius="md" withBorder>
          <Group justify="space-between" align="center" mb="md">
            <Group>
              <IconChartLine size={20} />
              <Text fw={600}>Processing Time Trend</Text>
            </Group>
            <Text size="sm" c="dimmed">
              {metrics.trends.processingTime.changePercentage > 0 ? '+' : ''}
              {metrics.trends.processingTime.changePercentage.toFixed(1)}%
            </Text>
          </Group>
          <SimpleLineChart
            data={chartData.processingTime}
            height={height}
            color="#228be6"
            title="Processing Time (seconds)"
          />
        </Card>

        {/* Success Rate Trend */}
        <Card p="md" radius="md" withBorder>
          <Group justify="space-between" align="center" mb="md">
            <Group>
              <IconChartArea size={20} />
              <Text fw={600}>Success Rate Trend</Text>
            </Group>
            <Text size="sm" c="dimmed">
              {metrics.trends.successRate.changePercentage > 0 ? '+' : ''}
              {metrics.trends.successRate.changePercentage.toFixed(1)}%
            </Text>
          </Group>
          <SimpleAreaChart
            data={chartData.successRate}
            height={height}
            color="#40c057"
            title="Success Rate (%)"
          />
        </Card>

        {/* Memory Usage Trend */}
        <Card p="md" radius="md" withBorder>
          <Group justify="space-between" align="center" mb="md">
            <Group>
              <IconChartBar size={20} />
              <Text fw={600}>Memory Usage Trend</Text>
            </Group>
            <Text size="sm" c="dimmed">
              {metrics.trends.memoryUsage.changePercentage > 0 ? '+' : ''}
              {metrics.trends.memoryUsage.changePercentage.toFixed(1)}%
            </Text>
          </Group>
          <SimpleBarChart
            data={chartData.memoryUsage}
            height={height}
            color="#fd7e14"
            title="Memory Usage (%)"
          />
        </Card>

        {/* Operations Overview */}
        <Card p="md" radius="md" withBorder>
          <Group justify="space-between" align="center" mb="md">
            <Group>
              <IconChartBar size={20} />
              <Text fw={600}>Operations Overview</Text>
            </Group>
            <Text size="sm" c="dimmed">
              {realTimeData.operationsPerMinute}/min
            </Text>
          </Group>
          <SimpleBarChart
            data={chartData.operations}
            height={height}
            color="#9775fa"
            title="Operations Count"
          />
        </Card>
      </SimpleGrid>

      {/* Real-time Metrics Cards */}
      <Card p="md" radius="md" withBorder>
        <Text fw={600} mb="md">Real-time Performance Indicators</Text>
        <SimpleGrid cols={{ base: 2, sm: 4 }} spacing="md">
          <Paper p="sm" withBorder radius="sm" style={{ textAlign: 'center' }}>
            <Text size="xs" c="dimmed" tt="uppercase">Active Ops</Text>
            <Text size="xl" fw={700} c="blue">{realTimeData.activeOperations}</Text>
          </Paper>

          <Paper p="sm" withBorder radius="sm" style={{ textAlign: 'center' }}>
            <Text size="xs" c="dimmed" tt="uppercase">Ops/Min</Text>
            <Text size="xl" fw={700} c="green">{realTimeData.operationsPerMinute}</Text>
          </Paper>

          <Paper p="sm" withBorder radius="sm" style={{ textAlign: 'center' }}>
            <Text size="xs" c="dimmed" tt="uppercase">Avg Latency</Text>
            <Text size="xl" fw={700} c="orange">
              {realTimeData.averageLatency < 1000
                ? `${realTimeData.averageLatency.toFixed(0)}ms`
                : `${(realTimeData.averageLatency / 1000).toFixed(1)}s`
              }
            </Text>
          </Paper>

          <Paper p="sm" withBorder radius="sm" style={{ textAlign: 'center' }}>
            <Text size="xs" c="dimmed" tt="uppercase">Memory</Text>
            <Text size="xl" fw={700} c="red">{realTimeData.memoryUsage.toFixed(1)}%</Text>
          </Paper>
        </SimpleGrid>
      </Card>

      {/* Performance Insights */}
      {metrics.performanceInsights.length > 0 && (
        <Card p="md" radius="md" withBorder>
          <Text fw={600} mb="md">Performance Insights</Text>
          <Stack gap="sm">
            {metrics.performanceInsights.slice(0, 3).map(insight => (
              <Paper key={insight.id} p="sm" withBorder radius="sm">
                <Group align="flex-start" gap="xs">
                  <div style={{ flex: 1 }}>
                    <Text size="sm" fw={600}>{insight.title}</Text>
                    <Text size="xs" c="dimmed">{insight.description}</Text>
                    {insight.recommendation && (
                      <Text size="xs" mt="xs" fw={500}>
                        💡 {insight.recommendation}
                      </Text>
                    )}
                  </div>
                  <Text size="xs" c="dimmed">
                    {new Date(insight.timestamp).toLocaleTimeString()}
                  </Text>
                </Group>
              </Paper>
            ))}
          </Stack>
        </Card>
      )}
    </Stack>
  );
};

// Compact version for embedding in other components
export const CompactMetricsChart: React.FC<{
  projectId: string;
  metric: 'processing' | 'success' | 'memory' | 'operations';
  height?: number;
  showTitle?: boolean;
}> = ({ projectId, metric, height = 200, showTitle = true }) => {
  const { metrics, isLoading } = useMetrics(projectId, '24h');

  const getChartData = () => {
    if (!metrics) return [];

    switch (metric) {
      case 'processing':
        return metrics.trends.processingTime.data.map(d => ({
          timestamp: d.timestamp,
          value: d.value / 1000,
          label: 'Processing Time (s)'
        }));
      case 'success':
        return metrics.trends.successRate.data.map(d => ({
          timestamp: d.timestamp,
          value: d.value,
          label: 'Success Rate (%)'
        }));
      case 'memory':
        return metrics.trends.memoryUsage.data.map(d => ({
          timestamp: d.timestamp,
          value: d.value,
          label: 'Memory Usage (%)'
        }));
      case 'operations':
        return [{
          timestamp: new Date().toISOString(),
          value: metrics.summary.totalOperations,
          label: 'Total Operations'
        }];
      default:
        return [];
    }
  };

  const getTitle = () => {
    switch (metric) {
      case 'processing': return 'Processing Time';
      case 'success': return 'Success Rate';
      case 'memory': return 'Memory Usage';
      case 'operations': return 'Operations';
      default: return '';
    }
  };

  const getColor = () => {
    switch (metric) {
      case 'processing': return '#228be6';
      case 'success': return '#40c057';
      case 'memory': return '#fd7e14';
      case 'operations': return '#9775fa';
      default: return '#228be6';
    }
  };

  if (isLoading) {
    return (
      <Center style={{ height }}>
        <Loader size="sm" />
      </Center>
    );
  }

  const data = getChartData();
  if (data.length === 0) {
    return (
      <Center style={{ height }}>
        <Text size="sm" c="dimmed">No data available</Text>
      </Center>
    );
  }

  return (
    <SimpleLineChart
      data={data}
      height={height}
      color={getColor()}
      title={showTitle ? getTitle() : undefined}
    />
  );
};

export default MetricsVisualization;