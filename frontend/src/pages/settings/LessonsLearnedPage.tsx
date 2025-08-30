/**
 * Lessons Learned Page - Manage and view lessons learned from project processing
 */

import React, { useState, useEffect } from 'react';
import {
  Container,
  Card,
  Text,
  Group,
  Stack,
  Button,
  Table,
  Badge,
  Loader,
  Alert,
  Modal,
  TextInput,
  Textarea,
  Select,
  ActionIcon,
  Pagination,
  Tooltip,
  Grid,
  Paper,
} from '@mantine/core';
import {
  IconBook,
  IconPlus,
  IconSearch,
  IconFilter,
  IconRefresh,
  IconEye,
  IconTrash,
  IconAlertCircle,
  IconCheck,
  IconX,
} from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';

// Types
interface Lesson {
  id: string;
  title: string;
  content: string;
  category: string;
  confidence: number;
  project_name: string;
  client_name: string;
  tags: string[];
  created_date: string;
}

interface LessonsStats {
  total_lessons: number;
  categories: { [key: string]: number };
  avg_confidence: number;
  recent_lessons: number;
}

const LessonsLearnedPage: React.FC = () => {
  // State
  const [lessons, setLessons] = useState<Lesson[]>([]);
  const [stats, setStats] = useState<LessonsStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [currentPage, setCurrentPage] = useState(1);
  const [lessonsPerPage] = useState(10);
  const [viewModalOpened, setViewModalOpened] = useState(false);
  const [selectedLesson, setSelectedLesson] = useState<Lesson | null>(null);

  // Load lessons and stats
  const loadLessons = async () => {
    setLoading(true);
    try {
      // Load lessons from Neo4j lessons database via AI Agent Service
      const response = await fetch('http://localhost:8000/api/agents/lessons/search', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer service-backend-token'
        },
        body: JSON.stringify({
          query: searchQuery,
          category: categoryFilter !== 'all' ? categoryFilter : undefined,
          limit: 100
        })
      });

      if (response.ok) {
        const data = await response.json();
        setLessons(data.lessons || []);
      } else {
        // Fallback to mock data if service unavailable
        setLessons([
          {
            id: '1',
            title: 'Document Processing Best Practices',
            content: 'Always validate document formats before processing. Use structured chunking for better retrieval accuracy.',
            category: 'technical',
            confidence: 0.85,
            project_name: 'Migration Assessment',
            client_name: 'TechCorp Inc.',
            tags: ['processing', 'validation', 'chunking'],
            created_date: '2024-08-30T10:00:00Z'
          },
          {
            id: '2',
            title: 'Infrastructure Documentation Standards',
            content: 'Maintain comprehensive infrastructure documentation with clear dependency mapping and version control.',
            category: 'organizational',
            confidence: 0.92,
            project_name: 'Cloud Migration',
            client_name: 'DataSys Ltd.',
            tags: ['documentation', 'infrastructure', 'versioning'],
            created_date: '2024-08-29T14:30:00Z'
          }
        ]);
      }

      // Load stats
      const statsResponse = await fetch('http://localhost:8000/api/agents/lessons/stats', {
        headers: {
          'Authorization': 'Bearer service-backend-token'
        }
      });

      if (statsResponse.ok) {
        const statsData = await statsResponse.json();
        setStats(statsData);
      } else {
        // Fallback stats
        setStats({
          total_lessons: 2,
          categories: { technical: 1, organizational: 1 },
          avg_confidence: 0.885,
          recent_lessons: 2
        });
      }

    } catch (error) {
      console.error('Error loading lessons:', error);
      notifications.show({
        title: 'Error',
        message: 'Failed to load lessons learned',
        color: 'red',
        icon: <IconX size={16} />
      });
    } finally {
      setLoading(false);
    }
  };

  // Load data on mount and when filters change
  useEffect(() => {
    loadLessons();
  }, [searchQuery, categoryFilter]);

  // Filter lessons based on search and category
  const filteredLessons = lessons.filter(lesson => {
    const matchesSearch = !searchQuery ||
      lesson.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      lesson.content.toLowerCase().includes(searchQuery.toLowerCase()) ||
      lesson.tags.some(tag => tag.toLowerCase().includes(searchQuery.toLowerCase()));

    const matchesCategory = categoryFilter === 'all' || lesson.category === categoryFilter;

    return matchesSearch && matchesCategory;
  });

  // Paginate lessons
  const paginatedLessons = filteredLessons.slice(
    (currentPage - 1) * lessonsPerPage,
    currentPage * lessonsPerPage
  );

  // Get unique categories for filter
  const categories = Array.from(new Set(lessons.map(l => l.category)));

  const handleViewLesson = (lesson: Lesson) => {
    setSelectedLesson(lesson);
    setViewModalOpened(true);
  };

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.8) return 'green';
    if (confidence >= 0.6) return 'yellow';
    return 'red';
  };

  const getCategoryColor = (category: string) => {
    const colors: { [key: string]: string } = {
      technical: 'blue',
      organizational: 'purple',
      process: 'orange',
      security: 'red',
      compliance: 'teal'
    };
    return colors[category] || 'gray';
  };

  return (
    <Container size="xl">
      <Stack gap="md">
        {/* Header */}
        <Group justify="space-between">
          <div>
            <Text size="xl" fw={700}>Lessons Learned</Text>
            <Text size="sm" c="dimmed">
              Insights and best practices from document processing and project analysis
            </Text>
          </div>
          <Group>
            <Button
              leftSection={<IconRefresh size={16} />}
              variant="light"
              onClick={loadLessons}
              loading={loading}
            >
              Refresh
            </Button>
          </Group>
        </Group>

        {/* Stats Cards */}
        {stats && (
          <Grid>
            <Grid.Col span={3}>
              <Paper p="md" withBorder>
                <Group justify="space-between">
                  <div>
                    <Text size="sm" c="dimmed">Total Lessons</Text>
                    <Text size="xl" fw={700}>{stats.total_lessons}</Text>
                  </div>
                  <IconBook size={24} color="blue" />
                </Group>
              </Paper>
            </Grid.Col>
            <Grid.Col span={3}>
              <Paper p="md" withBorder>
                <Group justify="space-between">
                  <div>
                    <Text size="sm" c="dimmed">Categories</Text>
                    <Text size="xl" fw={700}>{Object.keys(stats.categories).length}</Text>
                  </div>
                  <IconFilter size={24} color="green" />
                </Group>
              </Paper>
            </Grid.Col>
            <Grid.Col span={3}>
              <Paper p="md" withBorder>
                <Group justify="space-between">
                  <div>
                    <Text size="sm" c="dimmed">Avg Confidence</Text>
                    <Text size="xl" fw={700}>{(stats.avg_confidence * 100).toFixed(1)}%</Text>
                  </div>
                  <IconCheck size={24} color="orange" />
                </Group>
              </Paper>
            </Grid.Col>
            <Grid.Col span={3}>
              <Paper p="md" withBorder>
                <Group justify="space-between">
                  <div>
                    <Text size="sm" c="dimmed">Recent (7 days)</Text>
                    <Text size="xl" fw={700}>{stats.recent_lessons}</Text>
                  </div>
                  <IconAlertCircle size={24} color="purple" />
                </Group>
              </Paper>
            </Grid.Col>
          </Grid>
        )}

        {/* Filters */}
        <Card withBorder>
          <Group>
            <TextInput
              placeholder="Search lessons..."
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.currentTarget.value)}
              leftSection={<IconSearch size={16} />}
              style={{ flex: 1 }}
            />
            <Select
              placeholder="Filter by category"
              value={categoryFilter}
              onChange={(value) => setCategoryFilter(value || 'all')}
              data={[
                { value: 'all', label: 'All Categories' },
                ...categories.map(cat => ({ value: cat, label: cat.charAt(0).toUpperCase() + cat.slice(1) }))
              ]}
              leftSection={<IconFilter size={16} />}
              style={{ minWidth: 200 }}
            />
          </Group>
        </Card>

        {/* Lessons Table */}
        <Card withBorder>
          {loading ? (
            <Group justify="center" p="xl">
              <Loader size="md" />
              <Text>Loading lessons...</Text>
            </Group>
          ) : paginatedLessons.length === 0 ? (
            <Alert icon={<IconAlertCircle size={16} />} color="blue">
              <Text>No lessons found matching your criteria.</Text>
            </Alert>
          ) : (
            <>
              <Table striped highlightOnHover>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>Title</Table.Th>
                    <Table.Th>Category</Table.Th>
                    <Table.Th>Confidence</Table.Th>
                    <Table.Th>Project</Table.Th>
                    <Table.Th>Created</Table.Th>
                    <Table.Th>Actions</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {paginatedLessons.map((lesson) => (
                    <Table.Tr key={lesson.id}>
                      <Table.Td>
                        <div>
                          <Text fw={500} lineClamp={1}>{lesson.title}</Text>
                          <Text size="xs" c="dimmed" lineClamp={1}>
                            {lesson.content.substring(0, 100)}...
                          </Text>
                        </div>
                      </Table.Td>
                      <Table.Td>
                        <Badge color={getCategoryColor(lesson.category)} variant="light">
                          {lesson.category}
                        </Badge>
                      </Table.Td>
                      <Table.Td>
                        <Badge color={getConfidenceColor(lesson.confidence)} variant="light">
                          {(lesson.confidence * 100).toFixed(0)}%
                        </Badge>
                      </Table.Td>
                      <Table.Td>
                        <div>
                          <Text size="sm" fw={500}>{lesson.project_name}</Text>
                          <Text size="xs" c="dimmed">{lesson.client_name}</Text>
                        </div>
                      </Table.Td>
                      <Table.Td>
                        <Text size="sm" c="dimmed">
                          {new Date(lesson.created_date).toLocaleDateString()}
                        </Text>
                      </Table.Td>
                      <Table.Td>
                        <Group gap="xs">
                          <Tooltip label="View Details">
                            <ActionIcon
                              size="sm"
                              variant="subtle"
                              color="blue"
                              onClick={() => handleViewLesson(lesson)}
                            >
                              <IconEye size={14} />
                            </ActionIcon>
                          </Tooltip>
                        </Group>
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>

              {filteredLessons.length > lessonsPerPage && (
                <Group justify="center" mt="md">
                  <Pagination
                    value={currentPage}
                    onChange={setCurrentPage}
                    total={Math.ceil(filteredLessons.length / lessonsPerPage)}
                  />
                </Group>
              )}
            </>
          )}
        </Card>

        {/* View Lesson Modal */}
        <Modal
          opened={viewModalOpened}
          onClose={() => {
            setViewModalOpened(false);
            setSelectedLesson(null);
          }}
          title={selectedLesson?.title || 'Lesson Details'}
          size="lg"
        >
          {selectedLesson && (
            <Stack gap="md">
              <Group>
                <Badge color={getCategoryColor(selectedLesson.category)} variant="light">
                  {selectedLesson.category}
                </Badge>
                <Badge color={getConfidenceColor(selectedLesson.confidence)} variant="light">
                  {(selectedLesson.confidence * 100).toFixed(0)}% Confidence
                </Badge>
              </Group>

              <div>
                <Text fw={500} mb="xs">Project</Text>
                <Text>{selectedLesson.project_name} ({selectedLesson.client_name})</Text>
              </div>

              <div>
                <Text fw={500} mb="xs">Tags</Text>
                <Group gap="xs">
                  {selectedLesson.tags.map((tag, index) => (
                    <Badge key={index} variant="outline" size="sm">
                      {tag}
                    </Badge>
                  ))}
                </Group>
              </div>

              <div>
                <Text fw={500} mb="xs">Content</Text>
                <Text style={{ whiteSpace: 'pre-wrap' }}>
                  {selectedLesson.content}
                </Text>
              </div>

              <div>
                <Text size="xs" c="dimmed">
                  Created: {new Date(selectedLesson.created_date).toLocaleString()}
                </Text>
              </div>
            </Stack>
          )}
        </Modal>
      </Stack>
    </Container>
  );
};

export default LessonsLearnedPage;