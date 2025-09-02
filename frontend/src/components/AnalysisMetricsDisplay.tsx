import React, { useMemo } from 'react';
import {
  Card,
  Text,
  Group,
  Stack,
  Progress,
  SimpleGrid,
  RingProgress,
  Badge,
  Paper,
  Divider,
  ThemeIcon,
  Tooltip,
} from '@mantine/core';
import {
  IconClock,
  IconStar,
  IconFileText,
  IconTrendingUp,
  IconTrendingDown,
  IconEqual,
  IconBrain,
  IconCircleCheck,
  IconCircleX,
  IconAlertTriangle,
  IconBulb,
} from '@tabler/icons-react';

interface AnalysisResult {
  analysis_id: string;
  project_id: string;
  filename: string;
  analysis_type: string;
  summary?: string;
  categories: string[];
  key_insights: string[];
  structure_analysis?: Record<string, any>;
  content_preview?: string;
  quality_score?: number;
  processing_time: number;
  analysis_timestamp: string;
  metadata?: Record<string, any>;
  versions?: Array<{
    version_number: number;
    created_at: string;
    changes: string[];
  }>;
}

interface AnalysisMetricsDisplayProps {
  analyses: AnalysisResult[];
  showTrends?: boolean;
  compact?: boolean;
}

export const AnalysisMetricsDisplay: React.FC<AnalysisMetricsDisplayProps> = ({
  analyses,
  showTrends = true,
  compact = false
}) => {
  const metrics = useMemo(() => {
    if (!analyses || analyses.length === 0) {
      return {
        totalAnalyses: 0,
        avgProcessingTime: 0,
        avgQualityScore: 0,
        analysisTypeDistribution: {},
        qualityScoreDistribution: { excellent: 0, good: 0, fair: 0, poor: 0 },
        processingTimeTrend: 'stable',
        qualityScoreTrend: 'stable',
        successRate: 0,
        totalCategories: 0,
        avgInsightsPerAnalysis: 0,
      };
    }

    const totalAnalyses = analyses.length;
    const avgProcessingTime = analyses.reduce((sum, a) => sum + a.processing_time, 0) / totalAnalyses;
    const avgQualityScore = analyses
      .filter(a => a.quality_score !== undefined)
      .reduce((sum, a) => sum + (a.quality_score || 0), 0) / analyses.filter(a => a.quality_score !== undefined).length || 0;

    // Analysis type distribution
    const analysisTypeDistribution: Record<string, number> = {};
    analyses.forEach(analysis => {
      analysisTypeDistribution[analysis.analysis_type] = (analysisTypeDistribution[analysis.analysis_type] || 0) + 1;
    });

    // Quality score distribution
    const qualityScoreDistribution = { excellent: 0, good: 0, fair: 0, poor: 0 };
    analyses.forEach(analysis => {
      if (analysis.quality_score !== undefined) {
        if (analysis.quality_score >= 0.8) qualityScoreDistribution.excellent++;
        else if (analysis.quality_score >= 0.6) qualityScoreDistribution.good++;
        else if (analysis.quality_score >= 0.4) qualityScoreDistribution.fair++;
        else qualityScoreDistribution.poor++;
      }
    });

    // Calculate trends (simplified - in real app would compare with historical data)
    const processingTimeTrend = avgProcessingTime > 2 ? 'up' : avgProcessingTime < 1 ? 'down' : 'stable';
    const qualityScoreTrend = avgQualityScore > 0.7 ? 'up' : avgQualityScore < 0.5 ? 'down' : 'stable';

    // Success rate (analyses with quality scores)
    const successRate = (analyses.filter(a => a.quality_score !== undefined).length / totalAnalyses) * 100;

    // Total unique categories
    const allCategories = new Set<string>();
    analyses.forEach(analysis => {
      analysis.categories.forEach(cat => allCategories.add(cat));
    });

    // Average insights per analysis
    const avgInsightsPerAnalysis = analyses.reduce((sum, a) => sum + a.key_insights.length, 0) / totalAnalyses;

    return {
      totalAnalyses,
      avgProcessingTime,
      avgQualityScore,
      analysisTypeDistribution,
      qualityScoreDistribution,
      processingTimeTrend,
      qualityScoreTrend,
      successRate,
      totalCategories: allCategories.size,
      avgInsightsPerAnalysis,
    };
  }, [analyses]);

  const formatProcessingTime = (seconds: number): string => {
    if (seconds < 1) return `${(seconds * 1000).toFixed(0)}ms`;
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds.toFixed(1)}s`;
  };

  const getTrendIcon = (trend: string) => {
    switch (trend) {
      case 'up':
        return <IconTrendingUp size={16} color="red" />;
      case 'down':
        return <IconTrendingDown size={16} color="green" />;
      default:
        return <IconEqual size={16} color="gray" />;
    }
  };

  const getQualityScoreColor = (score: number): string => {
    if (score >= 0.8) return 'green';
    if (score >= 0.6) return 'yellow';
    if (score >= 0.4) return 'orange';
    return 'red';
  };

  if (!analyses || analyses.length === 0) {
    return (
      <Card p="md" radius="md" withBorder>
        <Text c="dimmed" ta="center">No analysis data available</Text>
      </Card>
    );
  }

  if (compact) {
    return (
      <Card p="sm" radius="md" withBorder>
        <Group justify="space-between" align="center">
          <Group gap="xs">
            <ThemeIcon size={32} radius="md" variant="light" color="blue">
              <IconBrain size={18} />
            </ThemeIcon>
            <div>
              <Text size="sm" fw={600}>{metrics.totalAnalyses} Analyses</Text>
              <Text size="xs" c="dimmed">Avg: {formatProcessingTime(metrics.avgProcessingTime)}</Text>
            </div>
          </Group>

          <Group gap="xs">
            <RingProgress
              size={40}
              thickness={4}
              sections={[
                {
                  value: metrics.avgQualityScore * 100,
                  color: getQualityScoreColor(metrics.avgQualityScore)
                }
              ]}
              label={
                <Text size="xs" ta="center" fw={600}>
                  {Math.round(metrics.avgQualityScore * 100)}
                </Text>
              }
            />
            <div>
              <Text size="sm" fw={600}>{Math.round(metrics.avgQualityScore * 100)}%</Text>
              <Text size="xs" c="dimmed">Quality</Text>
            </div>
          </Group>
        </Group>
      </Card>
    );
  }

  return (
    <Stack gap="md">
      {/* Overview Cards */}
      <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }} spacing="md">
        <Card p="md" radius="md" withBorder>
          <Group justify="space-between" align="center">
            <div>
              <Text size="sm" c="dimmed" tt="uppercase" fw={600}>
                Total Analyses
              </Text>
              <Text size="xl" fw={700}>
                {metrics.totalAnalyses}
              </Text>
            </div>
            <ThemeIcon size={40} radius="md" variant="light" color="blue">
              <IconFileText size={20} />
            </ThemeIcon>
          </Group>
        </Card>

        <Card p="md" radius="md" withBorder>
          <Group justify="space-between" align="center">
            <div>
              <Text size="sm" c="dimmed" tt="uppercase" fw={600}>
                Avg Processing Time
              </Text>
              <Group gap="xs" align="center">
                <Text size="xl" fw={700}>
                  {formatProcessingTime(metrics.avgProcessingTime)}
                </Text>
                {showTrends && getTrendIcon(metrics.processingTimeTrend)}
              </Group>
            </div>
            <ThemeIcon size={40} radius="md" variant="light" color="orange">
              <IconClock size={20} />
            </ThemeIcon>
          </Group>
        </Card>

        <Card p="md" radius="md" withBorder>
          <Group justify="space-between" align="center">
            <div>
              <Text size="sm" c="dimmed" tt="uppercase" fw={600}>
                Avg Quality Score
              </Text>
              <Group gap="xs" align="center">
                <Text size="xl" fw={700}>
                  {Math.round(metrics.avgQualityScore * 100)}%
                </Text>
                {showTrends && getTrendIcon(metrics.qualityScoreTrend)}
              </Group>
            </div>
            <ThemeIcon size={40} radius="md" variant="light" color="green">
              <IconStar size={20} />
            </ThemeIcon>
          </Group>
        </Card>

        <Card p="md" radius="md" withBorder>
          <Group justify="space-between" align="center">
            <div>
              <Text size="sm" c="dimmed" tt="uppercase" fw={600}>
                Success Rate
              </Text>
              <Text size="xl" fw={700}>
                {Math.round(metrics.successRate)}%
              </Text>
            </div>
            <ThemeIcon size={40} radius="md" variant="light" color="teal">
              <IconCircleCheck size={20} />
            </ThemeIcon>
          </Group>
        </Card>
      </SimpleGrid>

      {/* Detailed Metrics */}
      <SimpleGrid cols={{ base: 1, lg: 2 }} spacing="md">
        {/* Analysis Type Distribution */}
        <Card p="md" radius="md" withBorder>
          <Text size="lg" fw={600} mb="md">
            Analysis Types
          </Text>
          <Stack gap="sm">
            {Object.entries(metrics.analysisTypeDistribution).map(([type, count]) => (
              <Group key={type} justify="space-between" align="center">
                <Badge variant="light" color="blue" size="sm">
                  {type}
                </Badge>
                <Group gap="xs" align="center">
                  <Text size="sm" fw={500}>{count}</Text>
                  <Progress
                    value={(count / metrics.totalAnalyses) * 100}
                    size="sm"
                    w={60}
                    color="blue"
                  />
                </Group>
              </Group>
            ))}
          </Stack>
        </Card>

        {/* Quality Score Distribution */}
        <Card p="md" radius="md" withBorder>
          <Text size="lg" fw={600} mb="md">
            Quality Distribution
          </Text>
          <Stack gap="sm">
            {Object.entries(metrics.qualityScoreDistribution).map(([level, count]) => {
              if (count === 0) return null;
              const colors = { excellent: 'green', good: 'yellow', fair: 'orange', poor: 'red' };
              const color = colors[level as keyof typeof colors];
              return (
                <Group key={level} justify="space-between" align="center">
                  <Badge variant="light" color={color} size="sm" tt="capitalize">
                    {level}
                  </Badge>
                  <Group gap="xs" align="center">
                    <Text size="sm" fw={500}>{count}</Text>
                    <Progress
                      value={(count / metrics.totalAnalyses) * 100}
                      size="sm"
                      w={60}
                      color={color}
                    />
                  </Group>
                </Group>
              );
            })}
          </Stack>
        </Card>
      </SimpleGrid>

      {/* Additional Stats */}
      <Card p="md" radius="md" withBorder>
        <Text size="lg" fw={600} mb="md">
          Additional Metrics
        </Text>
        <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }} spacing="md">
          <Paper p="sm" withBorder radius="sm">
            <Group gap="xs" align="center">
              <IconFileText size={16} />
              <div>
                <Text size="sm" c="dimmed">Total Categories</Text>
                <Text size="lg" fw={600}>{metrics.totalCategories}</Text>
              </div>
            </Group>
          </Paper>

          <Paper p="sm" withBorder radius="sm">
            <Group gap="xs" align="center">
              <IconBulb size={16} />
              <div>
                <Text size="sm" c="dimmed">Avg Insights/Analysis</Text>
                <Text size="lg" fw={600}>{metrics.avgInsightsPerAnalysis.toFixed(1)}</Text>
              </div>
            </Group>
          </Paper>

          <Paper p="sm" withBorder radius="sm">
            <Group gap="xs" align="center">
              <IconBrain size={16} />
              <div>
                <Text size="sm" c="dimmed">Analysis Types</Text>
                <Text size="lg" fw={600}>{Object.keys(metrics.analysisTypeDistribution).length}</Text>
              </div>
            </Group>
          </Paper>
        </SimpleGrid>
      </Card>
    </Stack>
  );
};

export default AnalysisMetricsDisplay;