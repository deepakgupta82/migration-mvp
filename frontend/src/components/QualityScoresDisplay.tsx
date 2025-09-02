import React, { useMemo, useState } from 'react';
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
  SegmentedControl,
  Box,
  Center,
  Table,
  ScrollArea,
} from '@mantine/core';
import {
  IconStar,
  IconTrendingUp,
  IconTrendingDown,
  IconEqual,
  IconChartBar,
  IconChartPie,
  IconList,
  IconFilter,
  IconSortAscending,
  IconSortDescending,
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

interface QualityScoresDisplayProps {
  analyses: AnalysisResult[];
  showTrends?: boolean;
  showDistribution?: boolean;
  showBreakdown?: boolean;
  compact?: boolean;
}

type ViewMode = 'overview' | 'distribution' | 'breakdown' | 'comparison';

export const QualityScoresDisplay: React.FC<QualityScoresDisplayProps> = ({
  analyses,
  showTrends = true,
  showDistribution = true,
  showBreakdown = true,
  compact = false
}) => {
  const [viewMode, setViewMode] = useState<ViewMode>('overview');
  const [sortBy, setSortBy] = useState<'score' | 'filename' | 'date'>('score');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');

  const qualityData = useMemo(() => {
    if (!analyses || analyses.length === 0) {
      return {
        validAnalyses: [],
        avgScore: 0,
        medianScore: 0,
        scoreRange: { min: 0, max: 0 },
        distribution: { excellent: 0, good: 0, fair: 0, poor: 0 },
        trends: [],
        categoryBreakdown: {},
        topPerformers: [],
        lowPerformers: [],
      };
    }

    const validAnalyses = analyses.filter(a => a.quality_score !== undefined);
    const scores = validAnalyses.map(a => a.quality_score!);

    const avgScore = scores.reduce((sum, score) => sum + score, 0) / scores.length;
    const sortedScores = [...scores].sort((a, b) => a - b);
    const medianScore = sortedScores.length % 2 === 0
      ? (sortedScores[sortedScores.length / 2 - 1] + sortedScores[sortedScores.length / 2]) / 2
      : sortedScores[Math.floor(sortedScores.length / 2)];

    const scoreRange = {
      min: Math.min(...scores),
      max: Math.max(...scores)
    };

    // Distribution
    const distribution = { excellent: 0, good: 0, fair: 0, poor: 0 };
    validAnalyses.forEach(analysis => {
      const score = analysis.quality_score!;
      if (score >= 0.8) distribution.excellent++;
      else if (score >= 0.6) distribution.good++;
      else if (score >= 0.4) distribution.fair++;
      else distribution.poor++;
    });

    // Category breakdown
    const categoryBreakdown: Record<string, { count: number; avgScore: number; analyses: AnalysisResult[] }> = {};
    validAnalyses.forEach(analysis => {
      analysis.categories.forEach(category => {
        if (!categoryBreakdown[category]) {
          categoryBreakdown[category] = { count: 0, avgScore: 0, analyses: [] };
        }
        categoryBreakdown[category].count++;
        categoryBreakdown[category].avgScore += analysis.quality_score!;
        categoryBreakdown[category].analyses.push(analysis);
      });
    });

    // Calculate average scores for categories
    Object.keys(categoryBreakdown).forEach(category => {
      categoryBreakdown[category].avgScore /= categoryBreakdown[category].count;
    });

    // Top and low performers
    const sortedByScore = [...validAnalyses].sort((a, b) => (b.quality_score || 0) - (a.quality_score || 0));
    const topPerformers = sortedByScore.slice(0, 5);
    const lowPerformers = sortedByScore.slice(-5).reverse();

    // Trends (simplified - would use historical data in real app)
    const trends = validAnalyses
      .sort((a, b) => new Date(a.analysis_timestamp).getTime() - new Date(b.analysis_timestamp).getTime())
      .slice(-10); // Last 10 analyses

    return {
      validAnalyses,
      avgScore,
      medianScore,
      scoreRange,
      distribution,
      trends,
      categoryBreakdown,
      topPerformers,
      lowPerformers,
    };
  }, [analyses]);

  const getQualityScoreColor = (score: number): string => {
    if (score >= 0.8) return 'green';
    if (score >= 0.6) return 'yellow';
    if (score >= 0.4) return 'orange';
    return 'red';
  };

  const getQualityScoreLabel = (score: number): string => {
    if (score >= 0.8) return 'Excellent';
    if (score >= 0.6) return 'Good';
    if (score >= 0.4) return 'Fair';
    return 'Poor';
  };

  const sortedAnalyses = useMemo(() => {
    const sorted = [...qualityData.validAnalyses];
    sorted.sort((a, b) => {
      let aVal: any, bVal: any;

      switch (sortBy) {
        case 'score':
          aVal = a.quality_score || 0;
          bVal = b.quality_score || 0;
          break;
        case 'filename':
          aVal = a.filename.toLowerCase();
          bVal = b.filename.toLowerCase();
          break;
        case 'date':
          aVal = new Date(a.analysis_timestamp).getTime();
          bVal = new Date(b.analysis_timestamp).getTime();
          break;
        default:
          return 0;
      }

      if (sortOrder === 'asc') {
        return aVal > bVal ? 1 : -1;
      } else {
        return aVal < bVal ? 1 : -1;
      }
    });
    return sorted;
  }, [qualityData.validAnalyses, sortBy, sortOrder]);

  if (!analyses || analyses.length === 0) {
    return (
      <Card p="md" radius="md" withBorder>
        <Text c="dimmed" ta="center">No quality score data available</Text>
      </Card>
    );
  }

  if (compact) {
    return (
      <Card p="sm" radius="md" withBorder>
        <Group justify="space-between" align="center">
          <Group gap="xs">
            <ThemeIcon size={32} radius="md" variant="light" color="green">
              <IconStar size={18} />
            </ThemeIcon>
            <div>
              <Text size="sm" fw={600}>
                {qualityData.validAnalyses.length}/{analyses.length} Valid Scores
              </Text>
              <Text size="xs" c="dimmed">
                Avg: {Math.round(qualityData.avgScore * 100)}%
              </Text>
            </div>
          </Group>

          <RingProgress
            size={40}
            thickness={4}
            sections={[
              {
                value: qualityData.avgScore * 100,
                color: getQualityScoreColor(qualityData.avgScore)
              }
            ]}
            label={
              <Text size="xs" ta="center" fw={600}>
                {Math.round(qualityData.avgScore * 100)}
              </Text>
            }
          />
        </Group>
      </Card>
    );
  }

  return (
    <Stack gap="md">
      {/* View Mode Selector */}
      <Card p="sm" radius="md" withBorder>
        <Group justify="space-between" align="center">
          <Text size="lg" fw={600}>Quality Scores Analysis</Text>
          <SegmentedControl
            value={viewMode}
            onChange={(value) => setViewMode(value as ViewMode)}
            data={[
              { label: 'Overview', value: 'overview' },
              { label: 'Distribution', value: 'distribution' },
              { label: 'Breakdown', value: 'breakdown' },
              { label: 'Comparison', value: 'comparison' },
            ]}
          />
        </Group>
      </Card>

      {/* Overview Mode */}
      {viewMode === 'overview' && (
        <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }} spacing="md">
          <Card p="md" radius="md" withBorder>
            <Group justify="space-between" align="center">
              <div>
                <Text size="sm" c="dimmed" tt="uppercase" fw={600}>
                  Average Score
                </Text>
                <Text size="xl" fw={700}>
                  {Math.round(qualityData.avgScore * 100)}%
                </Text>
              </div>
              <ThemeIcon size={40} radius="md" variant="light" color={getQualityScoreColor(qualityData.avgScore)}>
                <IconStar size={20} />
              </ThemeIcon>
            </Group>
          </Card>

          <Card p="md" radius="md" withBorder>
            <Group justify="space-between" align="center">
              <div>
                <Text size="sm" c="dimmed" tt="uppercase" fw={600}>
                  Median Score
                </Text>
                <Text size="xl" fw={700}>
                  {Math.round(qualityData.medianScore * 100)}%
                </Text>
              </div>
              <ThemeIcon size={40} radius="md" variant="light" color="blue">
                <IconChartBar size={20} />
              </ThemeIcon>
            </Group>
          </Card>

          <Card p="md" radius="md" withBorder>
            <Group justify="space-between" align="center">
              <div>
                <Text size="sm" c="dimmed" tt="uppercase" fw={600}>
                  Score Range
                </Text>
                <Text size="xl" fw={700}>
                  {Math.round(qualityData.scoreRange.min * 100)} - {Math.round(qualityData.scoreRange.max * 100)}%
                </Text>
              </div>
              <ThemeIcon size={40} radius="md" variant="light" color="orange">
                <IconTrendingUp size={20} />
              </ThemeIcon>
            </Group>
          </Card>

          <Card p="md" radius="md" withBorder>
            <Group justify="space-between" align="center">
              <div>
                <Text size="sm" c="dimmed" tt="uppercase" fw={600}>
                  Valid Scores
                </Text>
                <Text size="xl" fw={700}>
                  {qualityData.validAnalyses.length}/{analyses.length}
                </Text>
              </div>
              <ThemeIcon size={40} radius="md" variant="light" color="teal">
                <IconList size={20} />
              </ThemeIcon>
            </Group>
          </Card>
        </SimpleGrid>
      )}

      {/* Distribution Mode */}
      {viewMode === 'distribution' && (
        <SimpleGrid cols={{ base: 1, lg: 2 }} spacing="md">
          <Card p="md" radius="md" withBorder>
            <Text size="lg" fw={600} mb="md">
              Quality Score Distribution
            </Text>
            <Stack gap="md">
              {Object.entries(qualityData.distribution).map(([level, count]) => {
                if (count === 0) return null;
                const colors = { excellent: 'green', good: 'yellow', fair: 'orange', poor: 'red' };
                const color = colors[level as keyof typeof colors];
                const percentage = (count / qualityData.validAnalyses.length) * 100;

                return (
                  <Group key={level} justify="space-between" align="center">
                    <Group gap="xs" align="center">
                      <Badge variant="light" color={color} size="sm" tt="capitalize">
                        {level}
                      </Badge>
                      <Text size="sm" fw={500}>{count} analyses</Text>
                    </Group>
                    <Group gap="xs" align="center">
                      <Text size="sm" fw={500}>{percentage.toFixed(1)}%</Text>
                      <Progress
                        value={percentage}
                        size="sm"
                        w={80}
                        color={color}
                      />
                    </Group>
                  </Group>
                );
              })}
            </Stack>
          </Card>

          <Card p="md" radius="md" withBorder>
            <Text size="lg" fw={600} mb="md">
              Score Ranges
            </Text>
            <Stack gap="sm">
              <Group justify="space-between">
                <Text size="sm">Excellent (80-100%)</Text>
                <Badge color="green">{qualityData.distribution.excellent}</Badge>
              </Group>
              <Group justify="space-between">
                <Text size="sm">Good (60-79%)</Text>
                <Badge color="yellow">{qualityData.distribution.good}</Badge>
              </Group>
              <Group justify="space-between">
                <Text size="sm">Fair (40-59%)</Text>
                <Badge color="orange">{qualityData.distribution.fair}</Badge>
              </Group>
              <Group justify="space-between">
                <Text size="sm">Poor (0-39%)</Text>
                <Badge color="red">{qualityData.distribution.poor}</Badge>
              </Group>
            </Stack>
          </Card>
        </SimpleGrid>
      )}

      {/* Breakdown Mode */}
      {viewMode === 'breakdown' && (
        <Card p="md" radius="md" withBorder>
          <Text size="lg" fw={600} mb="md">
            Quality Scores by Category
          </Text>
          <ScrollArea h={400}>
            <Table>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Category</Table.Th>
                  <Table.Th>Analysis Count</Table.Th>
                  <Table.Th>Average Score</Table.Th>
                  <Table.Th>Score Distribution</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {Object.entries(qualityData.categoryBreakdown)
                  .sort(([, a], [, b]) => b.avgScore - a.avgScore)
                  .map(([category, data]) => (
                    <Table.Tr key={category}>
                      <Table.Td>
                        <Badge variant="light" color="blue" size="sm">
                          {category}
                        </Badge>
                      </Table.Td>
                      <Table.Td>{data.count}</Table.Td>
                      <Table.Td>
                        <Group gap="xs" align="center">
                          <Text fw={500}>{Math.round(data.avgScore * 100)}%</Text>
                          <RingProgress
                            size={24}
                            thickness={3}
                            sections={[
                              {
                                value: data.avgScore * 100,
                                color: getQualityScoreColor(data.avgScore)
                              }
                            ]}
                          />
                        </Group>
                      </Table.Td>
                      <Table.Td>
                        <Group gap="xs">
                          {data.analyses.slice(0, 3).map((analysis, idx) => (
                            <Tooltip key={idx} label={`${analysis.filename}: ${Math.round((analysis.quality_score || 0) * 100)}%`}>
                              <RingProgress
                                size={20}
                                thickness={2}
                                sections={[
                                  {
                                    value: (analysis.quality_score || 0) * 100,
                                    color: getQualityScoreColor(analysis.quality_score || 0)
                                  }
                                ]}
                              />
                            </Tooltip>
                          ))}
                          {data.analyses.length > 3 && (
                            <Text size="xs" c="dimmed">+{data.analyses.length - 3} more</Text>
                          )}
                        </Group>
                      </Table.Td>
                    </Table.Tr>
                  ))}
              </Table.Tbody>
            </Table>
          </ScrollArea>
        </Card>
      )}

      {/* Comparison Mode */}
      {viewMode === 'comparison' && (
        <Stack gap="md">
          <Group justify="space-between" align="center">
            <Text size="lg" fw={600}>Analysis Comparison</Text>
            <Group gap="xs">
              <Text size="sm" c="dimmed">Sort by:</Text>
              <SegmentedControl
                size="xs"
                value={sortBy}
                onChange={(value) => setSortBy(value as typeof sortBy)}
                data={[
                  { label: 'Score', value: 'score' },
                  { label: 'Filename', value: 'filename' },
                  { label: 'Date', value: 'date' },
                ]}
              />
              <ThemeIcon
                size={24}
                variant="light"
                onClick={() => setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')}
                style={{ cursor: 'pointer' }}
              >
                {sortOrder === 'asc' ? <IconSortAscending size={14} /> : <IconSortDescending size={14} />}
              </ThemeIcon>
            </Group>
          </Group>

          <ScrollArea h={500}>
            <Stack gap="sm">
              {sortedAnalyses.map((analysis) => (
                <Card key={analysis.analysis_id} p="sm" radius="md" withBorder>
                  <Group justify="space-between" align="center">
                    <div style={{ flex: 1 }}>
                      <Group gap="xs" align="center" mb="xs">
                        <Text size="sm" fw={600} lineClamp={1}>
                          {analysis.filename}
                        </Text>
                        <Badge size="xs" variant="light" color="gray">
                          {analysis.analysis_type}
                        </Badge>
                      </Group>
                      <Group gap="xs">
                        {analysis.categories.slice(0, 3).map((category, idx) => (
                          <Badge key={idx} size="xs" variant="dot" color="blue">
                            {category}
                          </Badge>
                        ))}
                        {analysis.categories.length > 3 && (
                          <Badge size="xs" variant="light" color="gray">
                            +{analysis.categories.length - 3}
                          </Badge>
                        )}
                      </Group>
                    </div>

                    <Group gap="xs" align="center">
                      <RingProgress
                        size={32}
                        thickness={3}
                        sections={[
                          {
                            value: (analysis.quality_score || 0) * 100,
                            color: getQualityScoreColor(analysis.quality_score || 0)
                          }
                        ]}
                        label={
                          <Text size="xs" ta="center" fw={600}>
                            {Math.round((analysis.quality_score || 0) * 100)}
                          </Text>
                        }
                      />
                      <div>
                        <Text size="sm" fw={600}>
                          {getQualityScoreLabel(analysis.quality_score || 0)}
                        </Text>
                        <Text size="xs" c="dimmed">
                          {new Date(analysis.analysis_timestamp).toLocaleDateString()}
                        </Text>
                      </div>
                    </Group>
                  </Group>
                </Card>
              ))}
            </Stack>
          </ScrollArea>
        </Stack>
      )}
    </Stack>
  );
};

export default QualityScoresDisplay;