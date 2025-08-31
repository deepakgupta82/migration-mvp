import React, { useState, useEffect } from 'react';
import {
  Card,
  Text,
  Group,
  Badge,
  Tabs,
  Loader,
  Alert,
  Table,
  ActionIcon,
  TextInput,
  Select,
  Button,
  Stack,
  Paper,
  Grid,
  Divider,
} from '@mantine/core';
import {
  IconBrain,
  IconBulb,
  IconSearch,
  IconFileText,
  IconCalendar,
  IconTag,
  IconEye,
  IconRefresh,
} from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';

interface Discovery {
  id: string;
  text: string;
  category: string;
  confidence: number;
  source_document: string;
  extracted_at: string;
  project_id: string;
}

interface DiscoveryResponse {
  project_id: string;
  discoveries: Discovery[];
  total_count: number;
  categories: Record<string, number>;
  timestamp: string;
}

interface KnowledgeTabProps {
  projectId: string;
}

export const KnowledgeTab: React.FC<KnowledgeTabProps> = ({ projectId }) => {
  const [activeTab, setActiveTab] = useState<string>('discoveries');
  const [discoveries, setDiscoveries] = useState<Discovery[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<string>('');
  const [categories, setCategories] = useState<Record<string, number>>({});

  // Load discoveries from the graph service
  const loadDiscoveries = async (category?: string) => {
    try {
      setLoading(true);
      setError(null);

      const url = category && category !== 'all'
        ? `http://localhost:8005/api/graphs/projects/${projectId}/discoveries?category=${encodeURIComponent(category)}`
        : `http://localhost:8005/api/graphs/projects/${projectId}/discoveries`;

      const response = await fetch(url);

      if (!response.ok) {
        throw new Error(`Failed to load discoveries: ${response.statusText}`);
      }

      const data: DiscoveryResponse = await response.json();
      setDiscoveries(data.discoveries);
      setCategories(data.categories);

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to load discoveries';
      setError(errorMessage);
      notifications.show({
        title: 'Error',
        message: errorMessage,
        color: 'red',
      });
    } finally {
      setLoading(false);
    }
  };

  // Search discoveries
  const searchDiscoveries = async () => {
    if (!searchQuery.trim()) {
      loadDiscoveries(categoryFilter || undefined);
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const url = `http://localhost:8005/api/graphs/projects/${projectId}/discoveries/search?q=${encodeURIComponent(searchQuery.trim())}`;
      const response = await fetch(url);

      if (!response.ok) {
        throw new Error(`Search failed: ${response.statusText}`);
      }

      const data = await response.json();
      setDiscoveries(data.results);

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Search failed';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  // Load discoveries on mount and when category changes
  useEffect(() => {
    loadDiscoveries(categoryFilter || undefined);
  }, [projectId, categoryFilter]);

  // Get category color
  const getCategoryColor = (category: string) => {
    const colors: Record<string, string> = {
      infrastructure: 'blue',
      technology: 'green',
      business: 'orange',
      security: 'red',
      performance: 'purple',
      compliance: 'cyan',
    };
    return colors[category] || 'gray';
  };

  // Get confidence color
  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.8) return 'green';
    if (confidence >= 0.6) return 'yellow';
    return 'red';
  };

  const categoryOptions = [
    { value: 'all', label: 'All Categories' },
    ...Object.keys(categories).map(cat => ({ value: cat, label: `${cat} (${categories[cat]})` }))
  ];

  return (
    <div>
      {/* Header */}
      <Group justify="space-between" mb="md">
        <Group gap="sm">
          <IconBrain size={20} />
          <Text size="lg" fw={600}>Knowledge Base</Text>
          <Badge variant="light" color="blue">
            {discoveries.length} Facts
          </Badge>
        </Group>
        <Button
          size="xs"
          variant="light"
          leftSection={<IconRefresh size={14} />}
          onClick={() => loadDiscoveries(categoryFilter || undefined)}
          loading={loading}
        >
          Refresh
        </Button>
      </Group>

      {/* Category Summary */}
      {Object.keys(categories).length > 0 && (
        <Paper p="sm" mb="md" withBorder>
          <Text size="sm" fw={500} mb="xs">Knowledge Categories:</Text>
          <Group gap="xs">
            {Object.entries(categories).map(([category, count]) => (
              <Badge
                key={category}
                variant={categoryFilter === category ? "filled" : "light"}
                color={getCategoryColor(category)}
                style={{ cursor: 'pointer' }}
                onClick={() => setCategoryFilter(categoryFilter === category ? '' : category)}
              >
                {category}: {count}
              </Badge>
            ))}
          </Group>
        </Paper>
      )}

      {/* Search and Filters */}
      <Paper p="md" mb="md" withBorder>
        <Group gap="sm">
          <TextInput
            placeholder="Search discoveries..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            leftSection={<IconSearch size={16} />}
            style={{ flex: 1 }}
            onKeyPress={(e) => e.key === 'Enter' && searchDiscoveries()}
          />
          <Select
            placeholder="Filter by category"
            value={categoryFilter}
            onChange={(value) => setCategoryFilter(value || '')}
            data={categoryOptions}
            clearable
            style={{ minWidth: 200 }}
          />
          <Button
            onClick={searchDiscoveries}
            loading={loading}
            disabled={!searchQuery.trim()}
          >
            Search
          </Button>
          {(searchQuery || categoryFilter) && (
            <Button
              variant="subtle"
              onClick={() => {
                setSearchQuery('');
                setCategoryFilter('');
                loadDiscoveries();
              }}
            >
              Clear
            </Button>
          )}
        </Group>
      </Paper>

      {/* Content */}
      {error && (
        <Alert icon={<IconBulb size={16} />} title="Error" color="red" mb="md">
          {error}
        </Alert>
      )}

      {loading ? (
        <Group justify="center" p="xl">
          <Loader size="lg" />
        </Group>
      ) : discoveries.length === 0 ? (
        <Alert icon={<IconBrain size={16} />} title="No Knowledge Found" color="blue">
          No discoveries have been extracted yet. Upload and process documents to generate foundational facts.
        </Alert>
      ) : (
        <Grid>
          {discoveries.map((discovery) => (
            <Grid.Col key={discovery.id} span={12}>
              <Card withBorder radius="md" p="md">
                <Group justify="space-between" mb="xs">
                  <Group gap="xs">
                    <Badge color={getCategoryColor(discovery.category)} variant="light">
                      {discovery.category}
                    </Badge>
                    <Badge
                      color={getConfidenceColor(discovery.confidence)}
                      variant="light"
                    >
                      {Math.round(discovery.confidence * 100)}% confidence
                    </Badge>
                  </Group>
                  <Text size="xs" c="dimmed">
                    <IconCalendar size={12} style={{ marginRight: 4 }} />
                    {new Date(discovery.extracted_at).toLocaleDateString()}
                  </Text>
                </Group>

                <Text size="sm" mb="sm">
                  {discovery.text}
                </Text>

                <Group gap="xs">
                  <IconFileText size={14} />
                  <Text size="xs" c="dimmed">
                    Source: {discovery.source_document}
                  </Text>
                </Group>
              </Card>
            </Grid.Col>
          ))}
        </Grid>
      )}

      {/* Footer Info */}
      <Paper p="sm" mt="md" withBorder style={{ backgroundColor: '#f8f9fa' }}>
        <Text size="xs" c="dimmed">
          <IconBulb size={12} style={{ marginRight: 4 }} />
          <strong>Knowledge Base:</strong> This tab shows foundational facts (Stage 1) extracted automatically from documents,
          plus synthesized insights (Stage 2) generated by AI agents. Facts provide the base knowledge layer that agents
          use to generate more sophisticated insights and recommendations.
        </Text>
      </Paper>
    </div>
  );
};