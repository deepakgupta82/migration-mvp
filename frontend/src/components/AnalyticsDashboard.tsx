/**
 * Comprehensive Analytics Dashboard Component
 * Displays real-time metrics, KPIs, and performance insights
 */

import React, { useState } from 'react';
import {
  Card,
  Text,
  Group,
  Stack,
  SimpleGrid,
  RingProgress,
  Progress,
  Badge,
  Button,
  Select,
  Tabs,
  Paper,
  Divider,
  ActionIcon,
  Tooltip,
  Alert,
  Loader,
  Center
} from '@mantine/core';
import {
  IconActivity,
  IconTrendingUp,
  IconTrendingDown,
  IconEqual,
  IconDownload,
  IconRefresh,
  IconAlertTriangle,
  IconInfoCircle,
  IconCircleCheck,
  IconX,
  IconClock,
  IconDatabase,
  IconWifi,
  IconCpu,
  IconServer,
  IconChartLine,
  IconChartBar,
  IconChartPie
} from '@tabler/icons-react';
import { useMetrics, useRealTimeMetrics, useMetricsAlerts } from '../hooks/useMetrics';
import { TimeRange } from '../types/metrics';

interface AnalyticsDashboardProps {
  projectId: string;
  compact?: boolean;
  showExport?: boolean;
  autoRefresh?: boolean;
}

export const AnalyticsDashboard: React.FC<AnalyticsDashboardProps> = ({
  projectId,
  compact = false,
  showExport = true,
  autoRefresh = true
}) => {
  const [timeRange, setTimeRange] = useState<TimeRange>('24h');
  const [activeTab, setActiveTab] = useState<string>('overview');

  const { metrics, isLoading, error, refresh, exportData, clearMetrics } = useMetrics(projectId, timeRange);
  const realTimeData = useRealTimeMetrics(projectId);
  const { alerts, acknowledgeAlert, dismissAlert, activeAlertsCount } = useMetricsAlerts(projectId);

  const handleExport = async (format: 'json' | 'csv') => {
    try {
      const data = await exportData(format);
      const blob = new Blob([data], { type: format === 'json' ? 'application/json' : 'text/csv' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `analytics_${projectId}_${timeRange}.${format}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Export failed:', err);
    }
  };

  const formatDuration = (ms: number): string => {
    if (ms < 1000) return `${ms}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
    if (ms < 3600000) return `${(ms / 60000).toFixed(1)}m`;
    return `${(ms / 3600000).toFixed(1)}h`;
  };

  const formatBytes = (bytes: number): string => {
    if (bytes < 1024) return `${bytes}B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
  };

  const getTrendIcon = (direction: string) => {
    switch (direction) {
      case 'up':
        return <IconTrendingUp size={16} color="red" />;
      case 'down':
        return <IconTrendingDown size={16} color="green" />;
      default:
        return <IconEqual size={16} color="gray" />;
    }
  };

  const getStatusColor = (value: number, thresholds: { good: number; warning: number }) => {
    if (value >= thresholds.good) return 'green';
    if (value >= thresholds.warning) return 'yellow';
    return 'red';
  };

  if (error) {
    return (
      <Card p="md" radius="md" withBorder>
        <Alert color="red" title="Error loading analytics" icon={<IconAlertTriangle />}>
          {error}
        </Alert>
      </Card>
    );
  }

  if (isLoading && !metrics) {
    return (
      <Card p="md" radius="md" withBorder>
        <Center>
          <Stack align="center" gap="md">
            <Loader size="lg" />
            <Text>Loading analytics...</Text>
          </Stack>
        </Center>
      </Card>
    );
  }

  if (!metrics) return null;

  return (
    <Stack gap="md">
      {/* Header */}
      <Card p="md" radius="md" withBorder>
        <Group justify="space-between" align="center">
          <Group>
            <IconActivity size={24} />
            <div>
              <Text size="lg" fw={600}>Analytics Dashboard</Text>
              <Text size="sm" c="dimmed">Project: {projectId}</Text>
            </div>
          </Group>

          <Group>
            <Select
              size="sm"
              value={timeRange}
              onChange={(value) => value && setTimeRange(value as TimeRange)}
              data={[
                { value: '1h', label: 'Last Hour' },
                { value: '24h', label: 'Last 24 Hours' },
                { value: '7d', label: 'Last 7 Days' },
                { value: '30d', label: 'Last 30 Days' }
              ]}
            />

            {showExport && (
              <Button.Group>
                <Button
                  size="sm"
                  variant="light"
                  leftSection={<IconDownload size={14} />}
                  onClick={() => handleExport('json')}
                >
                  JSON
                </Button>
                <Button
                  size="sm"
                  variant="light"
                  onClick={() => handleExport('csv')}
                >
                  CSV
                </Button>
              </Button.Group>
            )}

            <ActionIcon
              variant="light"
              onClick={refresh}
              loading={isLoading}
            >
              <IconRefresh size={16} />
            </ActionIcon>
          </Group>
        </Group>
      </Card>

      {/* Alerts */}
      {activeAlertsCount > 0 && (
        <Card p="md" radius="md" withBorder>
          <Stack gap="sm">
            <Group>
              <IconAlertTriangle size={20} color="orange" />
              <Text fw={600}>Active Alerts ({activeAlertsCount})</Text>
            </Group>
            {alerts.filter(a => !a.acknowledged).slice(0, 3).map(alert => (
              <Alert
                key={alert.id}
                color={alert.type === 'error' ? 'red' : alert.type === 'warning' ? 'yellow' : 'blue'}
                title={alert.title}
                icon={alert.type === 'error' ? <IconX /> : alert.type === 'warning' ? <IconAlertTriangle /> : <IconInfoCircle />}
              >
                <Group justify="space-between" align="center">
                  <Text>{alert.message}</Text>
                  <Group>
                    <Button size="xs" variant="light" onClick={() => acknowledgeAlert(alert.id)}>
                      Acknowledge
                    </Button>
                    <Button size="xs" variant="subtle" onClick={() => dismissAlert(alert.id)}>
                      Dismiss
                    </Button>
                  </Group>
                </Group>
              </Alert>
            ))}
          </Stack>
        </Card>
      )}

      {/* Real-time Metrics */}
      {!compact && (
        <Card p="md" radius="md" withBorder>
          <Group justify="space-between" align="center" mb="md">
            <Text fw={600}>Real-time Metrics</Text>
            <Badge color="green" leftSection={<IconActivity size={12} />}>
              Live
            </Badge>
          </Group>

          <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }} spacing="md">
            <Paper p="sm" withBorder radius="sm">
              <Group justify="space-between" align="center">
                <div>
                  <Text size="sm" c="dimmed">Active Operations</Text>
                  <Text size="xl" fw={700}>{realTimeData.activeOperations}</Text>
                </div>
                <IconActivity size={24} color="blue" />
              </Group>
            </Paper>

            <Paper p="sm" withBorder radius="sm">
              <Group justify="space-between" align="center">
                <div>
                  <Text size="sm" c="dimmed">Ops/Min</Text>
                  <Text size="xl" fw={700}>{realTimeData.operationsPerMinute}</Text>
                </div>
                <IconChartBar size={24} color="green" />
              </Group>
            </Paper>

            <Paper p="sm" withBorder radius="sm">
              <Group justify="space-between" align="center">
                <div>
                  <Text size="sm" c="dimmed">Avg Latency</Text>
                  <Text size="xl" fw={700}>{formatDuration(realTimeData.averageLatency)}</Text>
                </div>
                <IconWifi size={24} color="orange" />
              </Group>
            </Paper>

            <Paper p="sm" withBorder radius="sm">
              <Group justify="space-between" align="center">
                <div>
                  <Text size="sm" c="dimmed">Memory Usage</Text>
                  <Text size="xl" fw={700}>{realTimeData.memoryUsage.toFixed(1)}%</Text>
                </div>
                <IconServer size={24} color="red" />
              </Group>
            </Paper>
          </SimpleGrid>
        </Card>
      )}

      {/* Main Dashboard Tabs */}
      <Tabs value={activeTab} onChange={(value) => value && setActiveTab(value)}>
        <Tabs.List>
          <Tabs.Tab value="overview" leftSection={<IconChartLine size={16} />}>
            Overview
          </Tabs.Tab>
          <Tabs.Tab value="performance" leftSection={<IconCpu size={16} />}>
            Performance
          </Tabs.Tab>
          <Tabs.Tab value="operations" leftSection={<IconDatabase size={16} />}>
            Operations
          </Tabs.Tab>
          <Tabs.Tab value="insights" leftSection={<IconInfoCircle size={16} />}>
            Insights
          </Tabs.Tab>
        </Tabs.List>

        {/* Overview Tab */}
        <Tabs.Panel value="overview" pt="md">
          <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }} spacing="md">
            {/* Success Rate */}
            <Card p="md" radius="md" withBorder>
              <Group justify="space-between" align="center">
                <div>
                  <Text size="sm" c="dimmed" tt="uppercase" fw={600}>
                    Success Rate
                  </Text>
                  <Group gap="xs" align="center">
                    <Text size="xl" fw={700}>
                      {metrics.summary.successRate.toFixed(1)}%
                    </Text>
                    {getTrendIcon(metrics.trends.successRate.direction)}
                  </Group>
                </div>
                <RingProgress
                  size={60}
                  thickness={4}
                  sections={[
                    {
                      value: metrics.summary.successRate,
                      color: getStatusColor(metrics.summary.successRate, { good: 90, warning: 70 })
                    }
                  ]}
                  label={
                    <Text size="xs" ta="center" fw={600}>
                      {Math.round(metrics.summary.successRate)}
                    </Text>
                  }
                />
              </Group>
            </Card>

            {/* Processing Time */}
            <Card p="md" radius="md" withBorder>
              <Group justify="space-between" align="center">
                <div>
                  <Text size="sm" c="dimmed" tt="uppercase" fw={600}>
                    Avg Processing Time
                  </Text>
                  <Group gap="xs" align="center">
                    <Text size="xl" fw={700}>
                      {formatDuration(metrics.summary.averageProcessingTime)}
                    </Text>
                    {getTrendIcon(metrics.trends.processingTime.direction)}
                  </Group>
                </div>
                <IconClock size={32} color="orange" />
              </Group>
            </Card>

            {/* Total Operations */}
            <Card p="md" radius="md" withBorder>
              <Group justify="space-between" align="center">
                <div>
                  <Text size="sm" c="dimmed" tt="uppercase" fw={600}>
                    Total Operations
                  </Text>
                  <Text size="xl" fw={700}>
                    {metrics.summary.totalOperations}
                  </Text>
                </div>
                <IconDatabase size={32} color="blue" />
              </Group>
            </Card>

            {/* Data Processed */}
            <Card p="md" radius="md" withBorder>
              <Group justify="space-between" align="center">
                <div>
                  <Text size="sm" c="dimmed" tt="uppercase" fw={600}>
                    Data Processed
                  </Text>
                  <Text size="xl" fw={700}>
                    {formatBytes(metrics.summary.totalDataProcessed)}
                  </Text>
                </div>
                <IconDatabase size={32} color="green" />
              </Group>
            </Card>
          </SimpleGrid>

          {/* Trends */}
          <SimpleGrid cols={{ base: 1, lg: 3 }} spacing="md" mt="md">
            <Card p="md" radius="md" withBorder>
              <Text fw={600} mb="md">Processing Time Trend</Text>
              <Group align="center" gap="xs">
                <Text size="lg" fw={700}>
                  {formatDuration(metrics.trends.processingTime.current)}
                </Text>
                {getTrendIcon(metrics.trends.processingTime.direction)}
                <Text size="sm" c={metrics.trends.processingTime.change > 0 ? 'red' : 'green'}>
                  {metrics.trends.processingTime.changePercentage > 0 ? '+' : ''}
                  {metrics.trends.processingTime.changePercentage.toFixed(1)}%
                </Text>
              </Group>
              <Progress
                value={Math.min(100, (metrics.trends.processingTime.current / 300000) * 100)} // 5 min baseline
                color={metrics.trends.processingTime.direction === 'up' ? 'red' : 'green'}
                mt="sm"
              />
            </Card>

            <Card p="md" radius="md" withBorder>
              <Text fw={600} mb="md">Success Rate Trend</Text>
              <Group align="center" gap="xs">
                <Text size="lg" fw={700}>
                  {metrics.trends.successRate.current.toFixed(1)}%
                </Text>
                {getTrendIcon(metrics.trends.successRate.direction)}
                <Text size="sm" c={metrics.trends.successRate.change > 0 ? 'green' : 'red'}>
                  {metrics.trends.successRate.changePercentage > 0 ? '+' : ''}
                  {metrics.trends.successRate.changePercentage.toFixed(1)}%
                </Text>
              </Group>
              <Progress
                value={metrics.trends.successRate.current}
                color={getStatusColor(metrics.trends.successRate.current, { good: 90, warning: 70 })}
                mt="sm"
              />
            </Card>

            <Card p="md" radius="md" withBorder>
              <Text fw={600} mb="md">Memory Usage Trend</Text>
              <Group align="center" gap="xs">
                <Text size="lg" fw={700}>
                  {metrics.trends.memoryUsage.current.toFixed(1)}%
                </Text>
                {getTrendIcon(metrics.trends.memoryUsage.direction)}
                <Text size="sm" c={metrics.trends.memoryUsage.change > 0 ? 'red' : 'green'}>
                  {metrics.trends.memoryUsage.changePercentage > 0 ? '+' : ''}
                  {metrics.trends.memoryUsage.changePercentage.toFixed(1)}%
                </Text>
              </Group>
              <Progress
                value={metrics.trends.memoryUsage.current}
                color={getStatusColor(100 - metrics.trends.memoryUsage.current, { good: 30, warning: 20 })}
                mt="sm"
              />
            </Card>
          </SimpleGrid>
        </Tabs.Panel>

        {/* Performance Tab */}
        <Tabs.Panel value="performance" pt="md">
          <SimpleGrid cols={{ base: 1, lg: 2 }} spacing="md">
            <Card p="md" radius="md" withBorder>
              <Text fw={600} mb="md">Performance Insights</Text>
              <Stack gap="sm">
                {metrics.performanceInsights.map(insight => (
                  <Alert
                    key={insight.id}
                    color={insight.type === 'error' ? 'red' : insight.type === 'warning' ? 'yellow' : 'blue'}
                    title={insight.title}
                    icon={
                      insight.type === 'error' ? <IconX size={16} /> :
                      insight.type === 'warning' ? <IconAlertTriangle size={16} /> :
                      <IconInfoCircle size={16} />
                    }
                  >
                    <Text>{insight.description}</Text>
                    {insight.recommendation && (
                      <Text size="sm" mt="xs" fw={600}>
                        Recommendation: {insight.recommendation}
                      </Text>
                    )}
                  </Alert>
                ))}
                {metrics.performanceInsights.length === 0 && (
                  <Text c="dimmed" ta="center">No performance insights available</Text>
                )}
              </Stack>
            </Card>

            <Card p="md" radius="md" withBorder>
              <Text fw={600} mb="md">Recent Errors</Text>
              <Stack gap="sm">
                {metrics.recentErrors.slice(0, 5).map(error => (
                  <Paper key={error.operationId} p="sm" withBorder radius="sm">
                    <Group align="flex-start" gap="xs">
                      <IconX size={16} color="red" />
                      <div style={{ flex: 1 }}>
                        <Text size="sm" fw={600}>{error.errorType}</Text>
                        <Text size="xs" c="dimmed">{error.operationType}</Text>
                        <Text size="sm">{error.errorMessage}</Text>
                      </div>
                    </Group>
                  </Paper>
                ))}
                {metrics.recentErrors.length === 0 && (
                  <Text c="dimmed" ta="center">No recent errors</Text>
                )}
              </Stack>
            </Card>
          </SimpleGrid>
        </Tabs.Panel>

        {/* Operations Tab */}
        <Tabs.Panel value="operations" pt="md">
          <Card p="md" radius="md" withBorder>
            <Text fw={600} mb="md">Top Operations by Duration</Text>
            <Stack gap="sm">
              {metrics.topOperations.slice(0, 10).map((op, index) => (
                <Paper key={op.operationId} p="sm" withBorder radius="sm">
                  <Group justify="space-between" align="center">
                    <div>
                      <Group gap="xs" align="center">
                        <Badge size="sm" variant="light">{index + 1}</Badge>
                        <Text fw={600}>{op.operationType}</Text>
                        <Badge
                          size="sm"
                          color={op.status === 'success' ? 'green' : op.status === 'failed' ? 'red' : 'yellow'}
                        >
                          {op.status}
                        </Badge>
                      </Group>
                      <Text size="sm" c="dimmed">
                        {op.documentId ? `Document: ${op.documentId}` : 'No document'}
                      </Text>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <Text fw={600}>{formatDuration(op.duration)}</Text>
                      <Text size="xs" c="dimmed">
                        {new Date(op.startTime).toLocaleString()}
                      </Text>
                    </div>
                  </Group>
                </Paper>
              ))}
              {metrics.topOperations.length === 0 && (
                <Text c="dimmed" ta="center">No operations data available</Text>
              )}
            </Stack>
          </Card>
        </Tabs.Panel>

        {/* Insights Tab */}
        <Tabs.Panel value="insights" pt="md">
          <Stack gap="md">
            <Card p="md" radius="md" withBorder>
              <Text fw={600} mb="md">System Health Overview</Text>
              <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }} spacing="md">
                <Paper p="sm" withBorder radius="sm">
                  <Group gap="xs" align="center">
                    <IconCircleCheck size={20} color="green" />
                    <div>
                      <Text size="sm" c="dimmed">System Status</Text>
                      <Text size="sm" fw={600} c="green">Healthy</Text>
                    </div>
                  </Group>
                </Paper>

                <Paper p="sm" withBorder radius="sm">
                  <Group gap="xs" align="center">
                    <IconWifi size={20} color="blue" />
                    <div>
                      <Text size="sm" c="dimmed">Connection Stability</Text>
                      <Text size="sm" fw={600}>
                        {metrics.trends.connectionStability.current.toFixed(1)}%
                      </Text>
                    </div>
                  </Group>
                </Paper>

                <Paper p="sm" withBorder radius="sm">
                  <Group gap="xs" align="center">
                    <IconServer size={20} color="orange" />
                    <div>
                      <Text size="sm" c="dimmed">Memory Efficiency</Text>
                      <Text size="sm" fw={600}>
                        {(100 - metrics.trends.memoryUsage.current).toFixed(1)}%
                      </Text>
                    </div>
                  </Group>
                </Paper>

                <Paper p="sm" withBorder radius="sm">
                  <Group gap="xs" align="center">
                    <IconActivity size={20} color="purple" />
                    <div>
                      <Text size="sm" c="dimmed">Throughput</Text>
                      <Text size="sm" fw={600}>
                        {realTimeData.throughput}/min
                      </Text>
                    </div>
                  </Group>
                </Paper>
              </SimpleGrid>
            </Card>

            <Card p="md" radius="md" withBorder>
              <Group justify="space-between" align="center" mb="md">
                <Text fw={600}>All Alerts</Text>
                <Button size="xs" variant="light" onClick={clearMetrics}>
                  Clear All Metrics
                </Button>
              </Group>
              <Stack gap="sm">
                {alerts.map(alert => (
                  <Alert
                    key={alert.id}
                    color={alert.type === 'error' ? 'red' : alert.type === 'warning' ? 'yellow' : 'blue'}
                    title={alert.title}
                    icon={
                      alert.type === 'error' ? <IconX size={16} /> :
                      alert.type === 'warning' ? <IconAlertTriangle size={16} /> :
                      <IconInfoCircle size={16} />
                    }
                  >
                    <Group justify="space-between" align="center">
                      <Text>{alert.message}</Text>
                      <Group>
                        {!alert.acknowledged && (
                          <Button size="xs" variant="light" onClick={() => acknowledgeAlert(alert.id)}>
                            Acknowledge
                          </Button>
                        )}
                        <Button size="xs" variant="subtle" onClick={() => dismissAlert(alert.id)}>
                          Dismiss
                        </Button>
                      </Group>
                    </Group>
                  </Alert>
                ))}
                {alerts.length === 0 && (
                  <Text c="dimmed" ta="center">No alerts</Text>
                )}
              </Stack>
            </Card>
          </Stack>
        </Tabs.Panel>
      </Tabs>
    </Stack>
  );
};

export default AnalyticsDashboard;