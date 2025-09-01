/**
 * Document Search Tab - PHASE 4
 * Advanced search within document content, summaries, categories, and metadata
 */

import React, { useState, useEffect } from 'react';
import {
  Card,
  Text,
  Group,
  Badge,
  Tabs,
  Loader,
  Alert,
  TextInput,
  Select,
  Button,
  Stack,
  Paper,
  Grid,
  Divider,
  ScrollArea,
  Pagination,
  ActionIcon,
  Tooltip,
  Switch,
  Box,
  RingProgress,
  Progress,
  ThemeIcon,
  Accordion,
  Code,
} from '@mantine/core';
import {
  IconSearch,
  IconBrain,
  IconFileText,
  IconTag,
  IconCalendar,
  IconFilter,
  IconRefresh,
  IconEye,
  IconDownload,
  IconZoomIn,
  IconChevronDown,
  IconChevronRight,
  IconInfoCircle,
  IconX,
  IconCheck,
  IconClock,
  IconDatabase,
} from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';
import { apiService } from '../../services/api';

interface SearchResult {
  filename: string;
  relevance_score: number;
  search_type: string;
  matched_content?: string;
  summary?: string;
  categories: string[];
  document_type?: string;
  content_length: number;
  last_updated?: string;
  metadata?: Record<string, any>;
}

interface SearchResponse {
  project_id: string;
  query: string;
  search_type: string;
  total_results: number;
  results: SearchResult[];
  search_timestamp: string;
  processing_time: number;
  filters_applied?: Record<string, any>;
}

interface DocumentSearchTabProps {
  projectId: string;
}

export const DocumentSearchTab: React.FC<DocumentSearchTabProps> = ({ projectId }) => {
  // Search state
  const [searchQuery, setSearchQuery] = useState('');
  const [searchType, setSearchType] = useState<string>('comprehensive');
  const [includeContent, setIncludeContent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Results state
  const [searchResults, setSearchResults] = useState<SearchResponse | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize] = useState(10);

  // Filters
  const [categoryFilter, setCategoryFilter] = useState<string>('');
  const [documentTypeFilter, setDocumentTypeFilter] = useState<string>('');

  // Expanded results
  const [expandedResults, setExpandedResults] = useState<Set<number>>(new Set());

  // Search history
  const [searchHistory, setSearchHistory] = useState<string[]>([]);

  // Perform search
  const performSearch = async () => {
    if (!searchQuery.trim()) {
      notifications.show({
        title: 'Search Query Required',
        message: 'Please enter a search query',
        color: 'orange',
      });
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const filters: Record<string, any> = {};
      if (categoryFilter) filters.categories = [categoryFilter];
      if (documentTypeFilter) filters.document_type = documentTypeFilter;

      const response = await apiService.searchDocumentContent(
        projectId,
        searchQuery.trim(),
        searchType,
        50, // Get more results for pagination
        includeContent,
        Object.keys(filters).length > 0 ? filters : undefined
      );

      setSearchResults(response);

      // Add to search history
      if (!searchHistory.includes(searchQuery.trim())) {
        setSearchHistory(prev => [searchQuery.trim(), ...prev.slice(0, 9)]); // Keep last 10
      }

      notifications.show({
        title: 'Search Completed',
        message: `Found ${response.total_results} results in ${response.processing_time.toFixed(2)}s`,
        color: 'green',
      });

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Search failed';
      setError(errorMessage);
      notifications.show({
        title: 'Search Failed',
        message: errorMessage,
        color: 'red',
      });
    } finally {
      setLoading(false);
    }
  };

  // Clear search
  const clearSearch = () => {
    setSearchQuery('');
    setSearchResults(null);
    setCurrentPage(1);
    setCategoryFilter('');
    setDocumentTypeFilter('');
    setExpandedResults(new Set());
  };

  // Toggle result expansion
  const toggleResultExpansion = (index: number) => {
    const newExpanded = new Set(expandedResults);
    if (newExpanded.has(index)) {
      newExpanded.delete(index);
    } else {
      newExpanded.add(index);
    }
    setExpandedResults(newExpanded);
  };

  // Get paginated results
  const paginatedResults = searchResults ? searchResults.results.slice(
    (currentPage - 1) * pageSize,
    currentPage * pageSize
  ) : [];

  const totalPages = searchResults ? Math.ceil(searchResults.results.length / pageSize) : 0;

  // Get unique categories from results
  const availableCategories = searchResults ?
    Array.from(new Set(searchResults.results.flatMap(r => r.categories))) : [];

  // Get unique document types from results
  const availableDocumentTypes = searchResults ?
    Array.from(new Set(searchResults.results.map(r => r.document_type).filter(Boolean))) : [];

  // Get search type color
  const getSearchTypeColor = (type: string) => {
    switch (type) {
      case 'semantic': return 'blue';
      case 'keyword': return 'green';
      case 'metadata': return 'orange';
      case 'comprehensive': return 'purple';
      default: return 'gray';
    }
  };

  // Get relevance score color
  const getRelevanceColor = (score: number) => {
    if (score >= 0.8) return 'green';
    if (score >= 0.6) return 'yellow';
    if (score >= 0.4) return 'orange';
    return 'red';
  };

  return (
    <div>
      {/* Header */}
      <Group justify="space-between" mb="md">
        <Group gap="sm">
          <IconSearch size={24} />
          <div>
            <Text size="lg" fw={600}>Document Content Search</Text>
            <Text size="sm" c="dimmed">Search within document content, summaries, categories, and metadata</Text>
          </div>
        </Group>
        {searchResults && (
          <Badge variant="light" color="blue" size="lg">
            {searchResults.total_results} Results
          </Badge>
        )}
      </Group>

      {/* Search Interface */}
      <Card withBorder p="md" mb="md">
        <Stack gap="md">
          {/* Search Input */}
          <Group gap="sm" grow>
            <TextInput
              placeholder="Enter search query..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              leftSection={<IconSearch size={16} />}
              onKeyPress={(e) => e.key === 'Enter' && performSearch()}
              size="md"
            />
            <Select
              placeholder="Search Type"
              value={searchType}
              onChange={(value) => setSearchType(value || 'comprehensive')}
              data={[
                { value: 'comprehensive', label: 'Comprehensive' },
                { value: 'semantic', label: 'Semantic' },
                { value: 'keyword', label: 'Keyword' },
                { value: 'metadata', label: 'Metadata' },
              ]}
              style={{ minWidth: 150 }}
            />
            <Button
              onClick={performSearch}
              loading={loading}
              disabled={!searchQuery.trim()}
              size="md"
            >
              Search
            </Button>
          </Group>

          {/* Advanced Options */}
          <Accordion>
            <Accordion.Item value="advanced">
              <Accordion.Control icon={<IconFilter size={16} />}>
                Advanced Search Options
              </Accordion.Control>
              <Accordion.Panel>
                <Grid>
                  <Grid.Col span={6}>
                    <Select
                      placeholder="Filter by Category"
                      value={categoryFilter}
                      onChange={(value) => setCategoryFilter(value || '')}
                      data={[
                        { value: '', label: 'All Categories' },
                        ...availableCategories.map(cat => ({ value: cat, label: cat }))
                      ]}
                      clearable
                    />
                  </Grid.Col>
                  <Grid.Col span={6}>
                    <Select
                      placeholder="Filter by Document Type"
                      value={documentTypeFilter}
                      onChange={(value) => setDocumentTypeFilter(value || '')}
                      data={[
                        { value: '', label: 'All Types' },
                        ...availableDocumentTypes.map(type => ({ value: type!, label: type! }))
                      ]}
                      clearable
                    />
                  </Grid.Col>
                  <Grid.Col span={6}>
                    <Switch
                      label="Include full content in results"
                      checked={includeContent}
                      onChange={(e) => setIncludeContent(e.target.checked)}
                    />
                  </Grid.Col>
                  <Grid.Col span={6}>
                    <Group gap="xs">
                      <Button variant="light" onClick={clearSearch} leftSection={<IconX size={14} />}>
                        Clear All
                      </Button>
                      {searchHistory.length > 0 && (
                        <Select
                          placeholder="Recent searches"
                          data={searchHistory.map(query => ({ value: query, label: query }))}
                          onChange={(value) => value && setSearchQuery(value)}
                          style={{ minWidth: 150 }}
                        />
                      )}
                    </Group>
                  </Grid.Col>
                </Grid>
              </Accordion.Panel>
            </Accordion.Item>
          </Accordion>
        </Stack>
      </Card>

      {/* Search Results */}
      {error && (
        <Alert icon={<IconInfoCircle size={16} />} title="Search Error" color="red" mb="md">
          {error}
        </Alert>
      )}

      {loading && (
        <Group justify="center" p="xl">
          <Stack align="center" gap="sm">
            <Loader size="lg" />
            <Text size="sm" c="dimmed">Searching document content...</Text>
          </Stack>
        </Group>
      )}

      {searchResults && !loading && (
        <Stack gap="md">
          {/* Search Summary */}
          <Card withBorder p="md">
            <Group justify="space-between" align="center">
              <div>
                <Text size="md" fw={600}>
                  Search Results for "{searchResults.query}"
                </Text>
                <Group gap="sm" mt="xs">
                  <Badge color={getSearchTypeColor(searchResults.search_type)} variant="light">
                    {searchResults.search_type} search
                  </Badge>
                  <Badge variant="light" color="gray">
                    {searchResults.total_results} results
                  </Badge>
                  <Badge variant="light" color="blue">
                    {searchResults.processing_time.toFixed(2)}s
                  </Badge>
                </Group>
              </div>
              <Button
                variant="light"
                leftSection={<IconRefresh size={14} />}
                onClick={performSearch}
                loading={loading}
              >
                Refresh
              </Button>
            </Group>
          </Card>

          {/* Results List */}
          <Stack gap="sm">
            {paginatedResults.map((result, index) => {
              const globalIndex = (currentPage - 1) * pageSize + index;
              const isExpanded = expandedResults.has(globalIndex);

              return (
                <Card key={globalIndex} withBorder>
                  <Stack gap="sm">
                    {/* Result Header */}
                    <Group justify="space-between" align="flex-start">
                      <div style={{ flex: 1 }}>
                        <Group gap="xs" mb="xs">
                          <IconFileText size={16} />
                          <Text size="md" fw={600} lineClamp={1}>
                            {result.filename}
                          </Text>
                          <Badge
                            color={getRelevanceColor(result.relevance_score)}
                            variant="light"
                            size="sm"
                          >
                            {(result.relevance_score * 100).toFixed(1)}% relevant
                          </Badge>
                          <Badge
                            color={getSearchTypeColor(result.search_type)}
                            variant="light"
                            size="sm"
                          >
                            {result.search_type}
                          </Badge>
                        </Group>

                        {result.summary && (
                          <Text size="sm" c="dimmed" lineClamp={2}>
                            {result.summary}
                          </Text>
                        )}
                      </div>

                      <Group gap="xs">
                        <Tooltip label="View Details">
                          <ActionIcon
                            variant="light"
                            onClick={() => toggleResultExpansion(globalIndex)}
                          >
                            {isExpanded ? <IconChevronDown size={14} /> : <IconChevronRight size={14} />}
                          </ActionIcon>
                        </Tooltip>
                      </Group>
                    </Group>

                    {/* Categories */}
                    {result.categories.length > 0 && (
                      <Group gap="xs">
                        {result.categories.slice(0, 5).map((category) => (
                          <Badge key={category} variant="light" color="orange" size="xs">
                            {category}
                          </Badge>
                        ))}
                        {result.categories.length > 5 && (
                          <Badge variant="light" color="gray" size="xs">
                            +{result.categories.length - 5} more
                          </Badge>
                        )}
                      </Group>
                    )}

                    {/* Metadata */}
                    <Group gap="md">
                      {result.document_type && (
                        <Text size="xs" c="dimmed">
                          <IconDatabase size={12} style={{ marginRight: 4 }} />
                          {result.document_type.toUpperCase()}
                        </Text>
                      )}
                      <Text size="xs" c="dimmed">
                        <IconFileText size={12} style={{ marginRight: 4 }} />
                        {(result.content_length / 1024).toFixed(1)} KB
                      </Text>
                      {result.last_updated && (
                        <Text size="xs" c="dimmed">
                          <IconCalendar size={12} style={{ marginRight: 4 }} />
                          {new Date(result.last_updated).toLocaleDateString()}
                        </Text>
                      )}
                    </Group>

                    {/* Expanded Content */}
                    {isExpanded && (
                      <Card withBorder p="sm" bg="gray.0">
                        <Stack gap="sm">
                          {/* Matched Content */}
                          {result.matched_content && (
                            <div>
                              <Text size="sm" fw={500} mb="xs">Matched Content:</Text>
                              <Paper p="xs" bg="white" style={{ fontFamily: 'monospace', fontSize: '12px' }}>
                                <Text size="xs" style={{ whiteSpace: 'pre-wrap' }}>
                                  {result.matched_content}
                                </Text>
                              </Paper>
                            </div>
                          )}

                          {/* Metadata Details */}
                          {result.metadata && Object.keys(result.metadata).length > 0 && (
                            <div>
                              <Text size="sm" fw={500} mb="xs">Search Metadata:</Text>
                              <Code block style={{ fontSize: '11px' }}>
                                {JSON.stringify(result.metadata, null, 2)}
                              </Code>
                            </div>
                          )}
                        </Stack>
                      </Card>
                    )}
                  </Stack>
                </Card>
              );
            })}
          </Stack>

          {/* Pagination */}
          {totalPages > 1 && (
            <Group justify="center" mt="md">
              <Pagination
                total={totalPages}
                value={currentPage}
                onChange={setCurrentPage}
                size="sm"
              />
            </Group>
          )}

          {/* No Results */}
          {searchResults.total_results === 0 && (
            <Alert icon={<IconInfoCircle size={16} />} title="No Results Found" color="blue">
              No documents matched your search query. Try different keywords or search type.
            </Alert>
          )}
        </Stack>
      )}

      {/* Help Section */}
      {!searchResults && !loading && (
        <Card withBorder p="md" mt="md">
          <Text size="md" fw={600} mb="sm">Search Types</Text>
          <Grid>
            <Grid.Col span={6}>
              <Paper p="sm" withBorder>
                <Group gap="sm" mb="xs">
                  <ThemeIcon size={32} radius="md" variant="light" color="purple">
                    <IconBrain size={16} />
                  </ThemeIcon>
                  <div>
                    <Text size="sm" fw={500}>Comprehensive</Text>
                    <Text size="xs" c="dimmed">Combines all search methods</Text>
                  </div>
                </Group>
              </Paper>
            </Grid.Col>
            <Grid.Col span={6}>
              <Paper p="sm" withBorder>
                <Group gap="sm" mb="xs">
                  <ThemeIcon size={32} radius="md" variant="light" color="blue">
                    <IconSearch size={16} />
                  </ThemeIcon>
                  <div>
                    <Text size="sm" fw={500}>Semantic</Text>
                    <Text size="xs" c="dimmed">AI-powered meaning search</Text>
                  </div>
                </Group>
              </Paper>
            </Grid.Col>
            <Grid.Col span={6}>
              <Paper p="sm" withBorder>
                <Group gap="sm" mb="xs">
                  <ThemeIcon size={32} radius="md" variant="light" color="green">
                    <IconFileText size={16} />
                  </ThemeIcon>
                  <div>
                    <Text size="sm" fw={500}>Keyword</Text>
                    <Text size="xs" c="dimmed">Exact text matching</Text>
                  </div>
                </Group>
              </Paper>
            </Grid.Col>
            <Grid.Col span={6}>
              <Paper p="sm" withBorder>
                <Group gap="sm" mb="xs">
                  <ThemeIcon size={32} radius="md" variant="light" color="orange">
                    <IconTag size={16} />
                  </ThemeIcon>
                  <div>
                    <Text size="sm" fw={500}>Metadata</Text>
                    <Text size="xs" c="dimmed">Search in summaries & categories</Text>
                  </div>
                </Group>
              </Paper>
            </Grid.Col>
          </Grid>
        </Card>
      )}
    </div>
  );
};