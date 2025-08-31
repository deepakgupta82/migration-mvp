/**
 * Lessons Learned View - Professional interface for accessing project insights and best practices
 */

import React, { useState, useEffect } from 'react';
import {
  Card,
  Text,
  Group,
  Badge,
  Button,
  TextInput,
  Select,
  Loader,
  Alert,
  Stack,
  Title,
  Grid,
  Paper,
  ActionIcon,
  Table,
  Tabs,
  Divider,
  ThemeIcon,
  Progress,
  RingProgress,
} from '@mantine/core';
import {
  IconSearch,
  IconBook,
  IconTrendingUp,
  IconTarget,
  IconBulb,
  IconRefresh,
  IconDownload,
  IconEye,
  IconFilter,
  IconChartBar,
  IconBrain,
  IconAlertCircle,
} from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';

interface Lesson {
  id: string;
  title: string;
  category: string;
  project_id: string;
  project_name: string;
  insights: string[];
  summary: string;
  confidence: number;
  created_at: string;
  tags: string[];
}

interface LessonsStats {
  total_lessons: number;
  categories: Record<string, number>;
  projects_with_lessons: number;
  average_confidence: number;
  recent_lessons: number;
}

export const LessonsLearnedView: React.FC = () => {
  const [activeTab, setActiveTab] = useState<string>('overview');
  const [lessons, setLessons] = useState<Lesson[]>([]);
  const [stats, setStats] = useState<LessonsStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null);
  const [projectFilter, setProjectFilter] = useState<string | null>(null);
  const [projects, setProjects] = useState<any[]>([]);

  // Load initial data
  useEffect(() => {
    loadLessonsStats();
    loadProjects();
  }, []);

  // Load lessons when filters change
  useEffect(() => {
    loadLessons();
  }, [searchQuery, categoryFilter, projectFilter]);

  const loadLessonsStats = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/agents/lessons/stats');
      if (response.ok) {
        const data = await response.json();
        setStats(data);
      }
    } catch (error) {
      console.error('Failed to load lessons stats:', error);
    }
  };

  const loadProjects = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/projects');
      if (response.ok) {
        const data = await response.json();
        setProjects(Array.isArray(data) ? data : []);
      }
    } catch (error) {
      console.error('Failed to load projects:', error);
    }
  };

  const loadLessons = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (searchQuery) params.append('query', searchQuery);
      if (categoryFilter) params.append('category', categoryFilter);
      if (projectFilter) params.append('project_id', projectFilter);

      const response = await fetch(`http://localhost:8000/api/agents/lessons/search?${params}`);
      if (response.ok) {
        const data = await response.json();
        setLessons(Array.isArray(data) ? data : []);
      }
    } catch (error) {
      console.error('Failed to load lessons:', error);
      notifications.show({
        title: 'Error',
        message: 'Failed to load lessons learned',
        color: 'red',
      });
    } finally {
      setLoading(false);
    }
  };

  const generateLessonsForProject = async (projectId: string) => {
    try {
      const response = await fetch(`http://localhost:8000/api/agents/lessons/generate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ project_id: projectId }),
      });

      if (response.ok) {
        notifications.show({
          title: 'Success',
          message: 'Lessons learned generation started for this project',
          color: 'green',
        });
        // Refresh data after a delay
        setTimeout(() => {
          loadLessonsStats();
          loadLessons();
        }, 2000);
      } else {
        throw new Error('Failed to generate lessons');
      }
    } catch (error) {
      notifications.show({
        title: 'Error',
        message: 'Failed to generate lessons for this project',
        color: 'red',
      });
    }
  };

  const getCategoryColor = (category: string) => {
    const colors: Record<string, string> = {
      'technical': 'blue',
      'process': 'green',
      'business': 'orange',
      'security': 'red',
      'performance': 'purple',
      'architecture': 'cyan',
    };
    return colors[category.toLowerCase()] || 'gray';
  };

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.8) return 'green';
    if (confidence >= 0.6) return 'yellow';
    return 'red';
  };

  return (
    <Stack gap="md">
      {/* Header */}
      <Group justify="space-between" align="center">
        <Group gap="sm">
          <ThemeIcon size={40} radius="md" variant="light" color="blue">
            <IconBook size={24} />
          </ThemeIcon>
          <div>
            <Title order={2}>Lessons Learned</Title>
            <Text size="sm" c="dimmed">
              Access project insights and best practices from completed migrations
            </Text>
          </div>
        </Group>
        <Group gap="sm">
          <Button
            variant="light"
            leftSection={<IconRefresh size={16} />}
            onClick={() => {
              loadLessonsStats();
              loadLessons();
            }}
          >
            Refresh
          </Button>
        </Group>
      </Group>

      {/* Statistics Overview */}
      {stats && (
        <Grid>
          <Grid.Col span={3}>
            <Card p="md" radius="md" withBorder>
              <Group gap="sm">
                <ThemeIcon size={32} radius="md" variant="light" color="blue">
                  <IconBook size={18} />
                </ThemeIcon>
                <div>
                  <Text size="lg" fw={700}>{stats.total_lessons}</Text>
                  <Text size="sm" c="dimmed">Total Lessons</Text>
                </div>
              </Group>
            </Card>
          </Grid.Col>
          <Grid.Col span={3}>
            <Card p="md" radius="md" withBorder>
              <Group gap="sm">
                <ThemeIcon size={32} radius="md" variant="light" color="green">
                  <IconTarget size={18} />
                </ThemeIcon>
                <div>
                  <Text size="lg" fw={700}>{stats.projects_with_lessons}</Text>
                  <Text size="sm" c="dimmed">Projects with Lessons</Text>
                </div>
              </Group>
            </Card>
          </Grid.Col>
          <Grid.Col span={3}>
            <Card p="md" radius="md" withBorder>
              <Group gap="sm">
                <ThemeIcon size={32} radius="md" variant="light" color="orange">
                  <IconTrendingUp size={18} />
                </ThemeIcon>
                <div>
                  <Text size="lg" fw={700}>{Math.round(stats.average_confidence * 100)}%</Text>
                  <Text size="sm" c="dimmed">Avg Confidence</Text>
                </div>
              </Group>
            </Card>
          </Grid.Col>
          <Grid.Col span={3}>
            <Card p="md" radius="md" withBorder>
              <Group gap="sm">
                <ThemeIcon size={32} radius="md" variant="light" color="purple">
                  <IconBulb size={18} />
                </ThemeIcon>
                <div>
                  <Text size="lg" fw={700}>{stats.recent_lessons}</Text>
                  <Text size="sm" c="dimmed">Recent Lessons</Text>
                </div>
              </Group>
            </Card>
          </Grid.Col>
        </Grid>
      )}

      {/* Main Content Tabs */}
      <Tabs value={activeTab} onChange={(value) => value && setActiveTab(value)}>
        <Tabs.List>
          <Tabs.Tab value="overview" leftSection={<IconChartBar size={16} />}>
            Overview
          </Tabs.Tab>
          <Tabs.Tab value="search" leftSection={<IconSearch size={16} />}>
            Search Lessons
          </Tabs.Tab>
          <Tabs.Tab value="generate" leftSection={<IconBrain size={16} />}>
            Generate Lessons
          </Tabs.Tab>
        </Tabs.List>

        {/* Overview Tab */}
        <Tabs.Panel value="overview" pt="md">
          <Grid>
            <Grid.Col span={8}>
              <Card p="md" radius="md" withBorder>
                <Title order={4} mb="md">Recent Lessons</Title>
                {loading ? (
                  <Group justify="center" p="xl">
                    <Loader size="lg" />
                  </Group>
                ) : lessons.length > 0 ? (
                  <Stack gap="sm">
                    {lessons.slice(0, 5).map((lesson) => (
                      <Paper key={lesson.id} p="sm" withBorder radius="sm">
                        <Group justify="space-between" align="flex-start">
                          <div style={{ flex: 1 }}>
                            <Group gap="xs" mb="xs">
                              <Text size="sm" fw={600}>{lesson.title}</Text>
                              <Badge size="xs" color={getCategoryColor(lesson.category)}>
                                {lesson.category}
                              </Badge>
                              <Badge size="xs" color={getConfidenceColor(lesson.confidence)}>
                                {Math.round(lesson.confidence * 100)}%
                              </Badge>
                            </Group>
                            <Text size="xs" c="dimmed" lineClamp={2}>
                              {lesson.summary}
                            </Text>
                            <Text size="xs" c="dimmed" mt="xs">
                              From: {lesson.project_name}
                            </Text>
                          </div>
                        </Group>
                      </Paper>
                    ))}
                  </Stack>
                ) : (
                  <Text size="sm" c="dimmed" ta="center" py="xl">
                    No lessons learned available yet. Complete some projects to generate insights.
                  </Text>
                )}
              </Card>
            </Grid.Col>
            <Grid.Col span={4}>
              <Card p="md" radius="md" withBorder>
                <Title order={4} mb="md">Category Distribution</Title>
                {stats?.categories && Object.keys(stats.categories).length > 0 ? (
                  <Stack gap="sm">
                    {Object.entries(stats.categories).map(([category, count]) => (
                      <Group key={category} justify="space-between">
                        <Badge color={getCategoryColor(category)} variant="light">
                          {category}
                        </Badge>
                        <Text size="sm" fw={600}>{count}</Text>
                      </Group>
                    ))}
                  </Stack>
                ) : (
                  <Text size="sm" c="dimmed" ta="center">
                    No category data available
                  </Text>
                )}
              </Card>
            </Grid.Col>
          </Grid>
        </Tabs.Panel>

        {/* Search Tab */}
        <Tabs.Panel value="search" pt="md">
          <Card p="md" radius="md" withBorder>
            {/* Search Filters */}
            <Stack gap="md" mb="lg">
              <Group gap="md" align="flex-end">
                <TextInput
                  placeholder="Search lessons..."
                  leftSection={<IconSearch size={16} />}
                  value={searchQuery}
                  onChange={(event) => setSearchQuery(event.currentTarget.value)}
                  style={{ flex: 1 }}
                />
                <Select
                  placeholder="Filter by category"
                  leftSection={<IconFilter size={16} />}
                  data={[
                    { value: '', label: 'All Categories' },
                    { value: 'technical', label: 'Technical' },
                    { value: 'process', label: 'Process' },
                    { value: 'business', label: 'Business' },
                    { value: 'security', label: 'Security' },
                    { value: 'performance', label: 'Performance' },
                    { value: 'architecture', label: 'Architecture' },
                  ]}
                  value={categoryFilter || ''}
                  onChange={(value) => setCategoryFilter(value || null)}
                  clearable
                />
                <Select
                  placeholder="Filter by project"
                  data={[
                    { value: '', label: 'All Projects' },
                    ...projects.map(project => ({
                      value: project.id,
                      label: project.name
                    }))
                  ]}
                  value={projectFilter || ''}
                  onChange={(value) => setProjectFilter(value || null)}
                  clearable
                />
              </Group>
            </Stack>

            {/* Search Results */}
            {loading ? (
              <Group justify="center" p="xl">
                <Loader size="lg" />
              </Group>
            ) : lessons.length > 0 ? (
              <Stack gap="md">
                {lessons.map((lesson) => (
                  <Card key={lesson.id} p="md" radius="md" withBorder>
                    <Group justify="space-between" align="flex-start" mb="sm">
                      <div style={{ flex: 1 }}>
                        <Group gap="xs" mb="xs">
                          <Text size="lg" fw={600}>{lesson.title}</Text>
                          <Badge color={getCategoryColor(lesson.category)}>
                            {lesson.category}
                          </Badge>
                          <Badge color={getConfidenceColor(lesson.confidence)}>
                            {Math.round(lesson.confidence * 100)}% confidence
                          </Badge>
                        </Group>
                        <Text size="sm" c="dimmed" mb="sm">
                          From project: {lesson.project_name}
                        </Text>
                        <Text size="sm" mb="sm">
                          {lesson.summary}
                        </Text>
                        {lesson.insights && lesson.insights.length > 0 && (
                          <div>
                            <Text size="sm" fw={600} mb="xs">Key Insights:</Text>
                            <ul style={{ margin: 0, paddingLeft: '20px' }}>
                              {lesson.insights.slice(0, 3).map((insight, index) => (
                                <li key={index}>
                                  <Text size="sm">{insight}</Text>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    </Group>
                    <Group gap="xs">
                      {lesson.tags && lesson.tags.map((tag) => (
                        <Badge key={tag} size="xs" variant="light">
                          {tag}
                        </Badge>
                      ))}
                    </Group>
                  </Card>
                ))}
              </Stack>
            ) : (
              <Text size="sm" c="dimmed" ta="center" py="xl">
                {searchQuery || categoryFilter || projectFilter
                  ? 'No lessons match your search criteria'
                  : 'No lessons learned available yet'
                }
              </Text>
            )}
          </Card>
        </Tabs.Panel>

        {/* Generate Tab */}
        <Tabs.Panel value="generate" pt="md">
          <Card p="md" radius="md" withBorder>
            <Title order={4} mb="md">Generate Lessons from Projects</Title>
            <Text size="sm" c="dimmed" mb="lg">
              Select a completed project to generate lessons learned and best practices.
              The AI will analyze the project data and extract valuable insights.
            </Text>

            <Stack gap="md">
              {projects
                .filter(project => project.status === 'completed')
                .map((project) => (
                  <Card key={project.id} p="md" radius="sm" withBorder>
                    <Group justify="space-between" align="center">
                      <div>
                        <Text size="sm" fw={600}>{project.name}</Text>
                        <Text size="xs" c="dimmed">
                          Completed: {new Date(project.updated_at || project.created_at).toLocaleDateString()}
                        </Text>
                        <Text size="xs" c="dimmed">
                          Client: {project.client_name}
                        </Text>
                      </div>
                      <Button
                        size="sm"
                        variant="light"
                        leftSection={<IconBrain size={16} />}
                        onClick={() => generateLessonsForProject(project.id)}
                      >
                        Generate Lessons
                      </Button>
                    </Group>
                  </Card>
                ))}
            </Stack>

            {projects.filter(project => project.status === 'completed').length === 0 && (
              <Text size="sm" c="dimmed" ta="center" py="xl">
                No completed projects available for lessons generation.
                Complete some projects first to generate insights.
              </Text>
            )}
          </Card>
        </Tabs.Panel>
      </Tabs>
    </Stack>
  );
};