/**
 * Performance Monitor Component
 * Tracks memory usage, CPU performance, and other system metrics
 */

import React, { useEffect, useState, useRef } from 'react';
import {
  Card,
  Text,
  Group,
  Stack,
  Progress,
  SimpleGrid,
  Badge,
  Alert,
  Button,
  ActionIcon,
  Tooltip,
  RingProgress,
  Paper,
  Divider
} from '@mantine/core';
import {
  IconCpu,
  IconServer,
  IconActivity,
  IconGauge,
  IconRefresh,
  IconAlertTriangle,
  IconInfoCircle,
  IconCircleCheck,
  IconX
} from '@tabler/icons-react';
import { usePerformanceMetrics } from '../hooks/useMetrics';
import { PerformanceMetrics } from '../types/metrics';

interface PerformanceMonitorProps {
  projectId: string;
  autoStart?: boolean;
  showDetailed?: boolean;
  alertThresholds?: {
    memoryUsage: number;
    cpuUsage?: number;
    renderTime?: number;
  };
}

interface PerformanceStats {
  averageMemoryUsage: number;
  peakMemoryUsage: number;
  averageRenderTime: number;
  totalRenders: number;
  memoryTrend: 'increasing' | 'decreasing' | 'stable';
  performanceScore: number;
  recommendations: string[];
}

export const PerformanceMonitor: React.FC<PerformanceMonitorProps> = ({
  projectId,
  autoStart = true,
  showDetailed = false,
  alertThresholds = {
    memoryUsage: 80,
    cpuUsage: 70,
    renderTime: 16 // 60fps threshold
  }
}) => {
  const { trackPerformance, memoryUsage, performanceData, isTracking } = usePerformanceMetrics(projectId);
  const [stats, setStats] = useState<PerformanceStats>({
    averageMemoryUsage: 0,
    peakMemoryUsage: 0,
    averageRenderTime: 0,
    totalRenders: 0,
    memoryTrend: 'stable',
    performanceScore: 100,
    recommendations: []
  });
  const [alerts, setAlerts] = useState<Array<{
    type: 'warning' | 'error' | 'info';
    message: string;
    timestamp: string;
  }>>([]);

  const renderCountRef = useRef(0);
  const lastMemoryUsageRef = useRef(0);

  // Calculate performance statistics
  useEffect(() => {
    if (performanceData.length === 0) return;

    const memoryValues = performanceData.map(p => p.memoryUsage.percentage);
    const renderTimeValues = performanceData.map(p => p.renderTime || 0).filter(t => t > 0);

    const averageMemoryUsage = memoryValues.reduce((sum, val) => sum + val, 0) / memoryValues.length;
    const peakMemoryUsage = Math.max(...memoryValues);
    const averageRenderTime = renderTimeValues.length > 0
      ? renderTimeValues.reduce((sum, val) => sum + val, 0) / renderTimeValues.length
      : 0;

    // Calculate memory trend
    const recentMemory = memoryValues.slice(-5);
    const olderMemory = memoryValues.slice(-10, -5);
    const recentAvg = recentMemory.reduce((sum, val) => sum + val, 0) / recentMemory.length;
    const olderAvg = olderMemory.length > 0
      ? olderMemory.reduce((sum, val) => sum + val, 0) / olderMemory.length
      : recentAvg;

    let memoryTrend: 'increasing' | 'decreasing' | 'stable' = 'stable';
    if (recentAvg > olderAvg + 5) memoryTrend = 'increasing';
    else if (recentAvg < olderAvg - 5) memoryTrend = 'decreasing';

    // Calculate performance score (0-100)
    let performanceScore = 100;
    if (averageMemoryUsage > alertThresholds.memoryUsage) performanceScore -= 30;
    if (averageRenderTime > alertThresholds.renderTime!) performanceScore -= 20;
    if (memoryTrend === 'increasing') performanceScore -= 10;
    performanceScore = Math.max(0, Math.min(100, performanceScore));

    // Generate recommendations
    const recommendations: string[] = [];
    if (averageMemoryUsage > alertThresholds.memoryUsage) {
      recommendations.push('Consider clearing cache or optimizing memory usage');
    }
    if (averageRenderTime > alertThresholds.renderTime!) {
      recommendations.push('Optimize rendering performance to improve frame rate');
    }
    if (memoryTrend === 'increasing') {
      recommendations.push('Monitor memory usage trend to prevent memory leaks');
    }

    setStats({
      averageMemoryUsage,
      peakMemoryUsage,
      averageRenderTime,
      totalRenders: renderCountRef.current,
      memoryTrend,
      performanceScore,
      recommendations
    });

    // Update last memory usage for trend calculation
    lastMemoryUsageRef.current = averageMemoryUsage;
  }, [performanceData, alertThresholds]);

  // Check for alerts
  useEffect(() => {
    const newAlerts: typeof alerts = [];

    if (memoryUsage.percentage > alertThresholds.memoryUsage) {
      newAlerts.push({
        type: 'warning',
        message: `Memory usage is high: ${memoryUsage.percentage.toFixed(1)}%`,
        timestamp: new Date().toISOString()
      });
    }

    if (stats.averageRenderTime > alertThresholds.renderTime!) {
      newAlerts.push({
        type: 'warning',
        message: `Render time is slow: ${stats.averageRenderTime.toFixed(1)}ms`,
        timestamp: new Date().toISOString()
      });
    }

    if (stats.memoryTrend === 'increasing' && stats.averageMemoryUsage > 60) {
      newAlerts.push({
        type: 'info',
        message: 'Memory usage is trending upward',
        timestamp: new Date().toISOString()
      });
    }

    setAlerts(prev => {
      // Avoid duplicate alerts
      const existingMessages = new Set(prev.map(a => a.message));
      return [...prev, ...newAlerts.filter(a => !existingMessages.has(a.message))];
    });
  }, [memoryUsage, stats, alertThresholds]);

  // Track render count
  useEffect(() => {
    renderCountRef.current += 1;
  });

  const getPerformanceColor = (score: number) => {
    if (score >= 80) return 'green';
    if (score >= 60) return 'yellow';
    return 'red';
  };

  const getMemoryColor = (percentage: number) => {
    if (percentage >= alertThresholds.memoryUsage) return 'red';
    if (percentage >= 60) return 'yellow';
    return 'green';
  };

  const dismissAlert = (index: number) => {
    setAlerts(prev => prev.filter((_, i) => i !== index));
  };

  return (
    <Stack gap="md">
      {/* Control Panel */}
      <Card p="md" radius="md" withBorder>
        <Group justify="space-between" align="center">
          <Group>
            <IconActivity size={24} />
            <div>
              <Text fw={600}>Performance Monitor</Text>
              <Text size="sm" c="dimmed">Real-time system metrics</Text>
            </div>
          </Group>

          <Group>
            <Badge color={isTracking ? 'green' : 'gray'}>
              {isTracking ? 'Monitoring' : 'Stopped'}
            </Badge>
            <Button
              size="sm"
              variant={isTracking ? 'light' : 'filled'}
              onClick={trackPerformance}
              leftSection={<IconRefresh size={14} />}
            >
              {isTracking ? 'Restart' : 'Start'} Monitoring
            </Button>
          </Group>
        </Group>
      </Card>

      {/* Performance Score */}
      <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }} spacing="md">
        <Card p="md" radius="md" withBorder>
          <Group justify="space-between" align="center">
            <div>
              <Text size="sm" c="dimmed" tt="uppercase" fw={600}>
                Performance Score
              </Text>
              <Text size="xl" fw={700}>
                {stats.performanceScore.toFixed(0)}
              </Text>
            </div>
            <RingProgress
              size={60}
              thickness={4}
              sections={[
                {
                  value: stats.performanceScore,
                  color: getPerformanceColor(stats.performanceScore)
                }
              ]}
              label={
                <Text size="xs" ta="center" fw={600}>
                  {stats.performanceScore.toFixed(0)}
                </Text>
              }
            />
          </Group>
        </Card>

        <Card p="md" radius="md" withBorder>
          <Group justify="space-between" align="center">
            <div>
              <Text size="sm" c="dimmed" tt="uppercase" fw={600}>
                Memory Usage
              </Text>
              <Text size="xl" fw={700}>
                {memoryUsage.percentage.toFixed(1)}%
              </Text>
            </div>
            <IconServer size={32} color={getMemoryColor(memoryUsage.percentage)} />
          </Group>
          <Progress
            value={memoryUsage.percentage}
            color={getMemoryColor(memoryUsage.percentage)}
            mt="sm"
          />
        </Card>

        <Card p="md" radius="md" withBorder>
          <Group justify="space-between" align="center">
            <div>
              <Text size="sm" c="dimmed" tt="uppercase" fw={600}>
                Avg Render Time
              </Text>
              <Text size="xl" fw={700}>
                {stats.averageRenderTime.toFixed(1)}ms
              </Text>
            </div>
            <IconGauge size={32} color={stats.averageRenderTime > alertThresholds.renderTime! ? 'red' : 'green'} />
          </Group>
        </Card>

        <Card p="md" radius="md" withBorder>
          <Group justify="space-between" align="center">
            <div>
              <Text size="sm" c="dimmed" tt="uppercase" fw={600}>
                Memory Trend
              </Text>
              <Text size="xl" fw={700} tt="capitalize">
                {stats.memoryTrend}
              </Text>
            </div>
            <IconCpu size={32} color={
              stats.memoryTrend === 'increasing' ? 'red' :
              stats.memoryTrend === 'decreasing' ? 'green' : 'blue'
            } />
          </Group>
        </Card>
      </SimpleGrid>

      {/* Detailed Metrics */}
      {showDetailed && (
        <SimpleGrid cols={{ base: 1, lg: 2 }} spacing="md">
          <Card p="md" radius="md" withBorder>
            <Text fw={600} mb="md">Memory Details</Text>
            <Stack gap="sm">
              <Group justify="space-between">
                <Text size="sm">Used Memory</Text>
                <Text size="sm" fw={600}>{memoryUsage.used} MB</Text>
              </Group>
              <Group justify="space-between">
                <Text size="sm">Total Memory</Text>
                <Text size="sm" fw={600}>{memoryUsage.total} MB</Text>
              </Group>
              <Group justify="space-between">
                <Text size="sm">Peak Usage</Text>
                <Text size="sm" fw={600}>{stats.peakMemoryUsage.toFixed(1)}%</Text>
              </Group>
              <Divider />
              <Group justify="space-between">
                <Text size="sm">Average Usage</Text>
                <Text size="sm" fw={600}>{stats.averageMemoryUsage.toFixed(1)}%</Text>
              </Group>
            </Stack>
          </Card>

          <Card p="md" radius="md" withBorder>
            <Text fw={600} mb="md">Performance Details</Text>
            <Stack gap="sm">
              <Group justify="space-between">
                <Text size="sm">Total Renders</Text>
                <Text size="sm" fw={600}>{stats.totalRenders}</Text>
              </Group>
              <Group justify="space-between">
                <Text size="sm">Avg Render Time</Text>
                <Text size="sm" fw={600}>{stats.averageRenderTime.toFixed(1)}ms</Text>
              </Group>
              <Group justify="space-between">
                <Text size="sm">Data Points</Text>
                <Text size="sm" fw={600}>{performanceData.length}</Text>
              </Group>
              <Divider />
              <Group justify="space-between">
                <Text size="sm">Monitoring Status</Text>
                <Badge color={isTracking ? 'green' : 'gray'}>
                  {isTracking ? 'Active' : 'Inactive'}
                </Badge>
              </Group>
            </Stack>
          </Card>
        </SimpleGrid>
      )}

      {/* Alerts */}
      {alerts.length > 0 && (
        <Card p="md" radius="md" withBorder>
          <Text fw={600} mb="md">Performance Alerts</Text>
          <Stack gap="sm">
            {alerts.map((alert, index) => (
              <Alert
                key={index}
                color={alert.type === 'error' ? 'red' : alert.type === 'warning' ? 'yellow' : 'blue'}
                title={alert.type === 'error' ? 'Error' : alert.type === 'warning' ? 'Warning' : 'Info'}
                icon={
                  alert.type === 'error' ? <IconX size={16} /> :
                  alert.type === 'warning' ? <IconAlertTriangle size={16} /> :
                  <IconInfoCircle size={16} />
                }
              >
                <Group justify="space-between" align="center">
                  <Text>{alert.message}</Text>
                  <Button size="xs" variant="subtle" onClick={() => dismissAlert(index)}>
                    Dismiss
                  </Button>
                </Group>
              </Alert>
            ))}
          </Stack>
        </Card>
      )}

      {/* Recommendations */}
      {stats.recommendations.length > 0 && (
        <Card p="md" radius="md" withBorder>
          <Text fw={600} mb="md">Performance Recommendations</Text>
          <Stack gap="sm">
            {stats.recommendations.map((recommendation, index) => (
              <Paper key={index} p="sm" withBorder radius="sm">
                <Group align="flex-start" gap="xs">
                  <IconInfoCircle size={16} color="blue" />
                  <Text size="sm">{recommendation}</Text>
                </Group>
              </Paper>
            ))}
          </Stack>
        </Card>
      )}
    </Stack>
  );
};

export default PerformanceMonitor;