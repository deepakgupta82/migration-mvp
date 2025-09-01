/**
 * Document Analysis Dashboard - PHASE 3
 * Comprehensive content analysis capabilities for large projects
 */

import React, { useState, useEffect, useMemo } from 'react';
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
  Progress,
  RingProgress,
  SimpleGrid,
  Title,
  Box,
  ScrollArea,
  Pagination,
  Modal,
  Code,
  Accordion,
  ThemeIcon,
  Tooltip,
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
  IconChevronDown,
  IconChevronRight,
  IconRobot,
  IconFile,
  IconInfoCircle,
  IconX,
  IconChartBar,
  IconChartPie,
  IconChartLine,
  IconDatabase,
  IconTrendingUp,
  IconFilter,
  IconDownload,
  IconZoomIn,
  IconList,
  IconGrid3x3,
  IconAlertCircle,
} from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';
import { apiService } from '../../services/api';

// Types
interface DocumentAnalysis {
  project_id: string;
  filename: string;
  analysis_id: string;
  analysis_type: string;
  summary?: string;
  categories: string[];
  key_insights: string[];
  structure_analysis?: Record<string, any>;
  content_preview?: string;
  processing_time: number;
  analysis_timestamp: string;
}

interface ProjectInsights {
  project_id: string;
  total_documents: number;
  analyzed_documents: number;
  top_categories: Array<{
    category: string;
    count: number;
  }>;
  content_summary?: string;
  document_types: Record<string, number>;
  insights: string[];
  last_updated?: string;
}

interface DocumentMetadata {
  filename: string;
  content_length: number;
  processing_status: string;
  last_updated?: string;
  has_structured_data: boolean;
  categories?: string[];
  analysis_summary?: string;
}

interface DocumentAnalysisDashboardProps {
  projectId: string;
}

export const DocumentAnalysisDashboard: React.FC<DocumentAnalysisDashboardProps> = ({ projectId }) => {
  // State management
  const [activeTab, setActiveTab] = useState<string>('overview');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [projectInsights, setProjectInsights] = useState<ProjectInsights | null>(null);
  const [documents, setDocuments] = useState<DocumentMetadata[]>([]);
  const [selectedDocument, setSelectedDocument] = useState<DocumentMetadata | null>(null);
  const [documentAnalysis, setDocumentAnalysis] = useState<DocumentAnalysis | null>(null);
  const [analysisModalOpen, setAnalysisModalOpen] = useState(false);
  const [analyzingDocument, setAnalyzingDocument] = useState<string | null>(null);

  // Pagination and filtering
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize] = useState(20);
  const [searchQuery, setSearchQuery] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('');

  // View mode
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('list');

  // Load project insights
  const loadProjectInsights = async () => {
    try {
      setLoading(true);
      setError(null);
      const insights = await apiService.getProjectContentInsights(projectId);
      setProjectInsights(insights);

      // Load document metadata
      await loadDocumentMetadata();

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to load project insights';
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

  // Load document metadata
  const loadDocumentMetadata = async () => {
    try {
      // Get project files to build metadata
      const files = await apiService.getProjectUploads(projectId);

      const metadataPromises = files.map(async (file) => {
        try {
          const details = await apiService.getDocumentContentDetails(projectId, file.filename);
          return {
            filename: file.filename,
            content_length: details.content_length,
            processing_status: details.processing_status,
            last_updated: details.last_updated,
            has_structured_data: details.has_structured_data,
            categories: details.categories,
            analysis_summary: details.summary,
          } as DocumentMetadata;
        } catch (err) {
          // Return basic metadata if detailed analysis fails
          return {
            filename: file.filename,
            content_length: file.file_size || 0,
            processing_status: 'unknown',
            last_updated: file.uploaded_at,
            has_structured_data: false,
          } as DocumentMetadata;
        }
      });

      const metadata = await Promise.all(metadataPromises);
      setDocuments(metadata);

    } catch (err) {
      console.error('Failed to load document metadata:', err);
    }
  };

  // Analyze document
  const analyzeDocument = async (filename: string, useLLM: boolean = false) => {
    try {
      setAnalyzingDocument(filename);

      const analysis = useLLM
        ? await apiService.analyzeDocumentWithLLM(projectId, filename, 'comprehensive')
        : await apiService.analyzeDocument(projectId, filename, 'comprehensive', false);

      // Type-safe property access for union types
      const getAnalysisId = (analysis: any): string => {
        return analysis.analysis_id || analysis.id || `analysis_${Date.now()}`;
      };

      const getSummary = (analysis: any): string | undefined => {
        return analysis.final_summary || analysis.summary || analysis.content_summary;
      };

      const getCategories = (analysis: any): string[] => {
        return analysis.final_categories || analysis.categories || analysis.tags || [];
      };

      const getKeyInsights = (analysis: any): string[] => {
        return analysis.key_insights || analysis.insights || [];
      };

      const getStructureAnalysis = (analysis: any): Record<string, any> | undefined => {
        return analysis.structure_analysis || analysis.structure;
      };

      const getContentPreview = (analysis: any): string | undefined => {
        return analysis.content_preview || analysis.preview;
      };

      const getProcessingTime = (analysis: any): number => {
        return analysis.processing_time || analysis.duration || 0;
      };

      const getTimestamp = (analysis: any): string => {
        return analysis.timestamp || analysis.analysis_timestamp || analysis.created_at || new Date().toISOString();
      };

      setDocumentAnalysis({
        project_id: projectId,
        filename,
        analysis_id: getAnalysisId(analysis),
        analysis_type: analysis.analysis_type || 'comprehensive',
        summary: getSummary(analysis),
        categories: getCategories(analysis),
        key_insights: getKeyInsights(analysis),
        structure_analysis: getStructureAnalysis(analysis),
        content_preview: getContentPreview(analysis),
        processing_time: getProcessingTime(analysis),
        analysis_timestamp: getTimestamp(analysis),
      });

      setSelectedDocument(documents.find(d => d.filename === filename) || null);
      setAnalysisModalOpen(true);

      notifications.show({
        title: 'Analysis Complete',
        message: `Document analysis completed for ${filename}`,
        color: 'green',
      });

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to analyze document';
      notifications.show({
        title: 'Analysis Failed',
        message: errorMessage,
        color: 'red',
      });
    } finally {
      setAnalyzingDocument(null);
    }
  };

  // Filtered and paginated documents
  const filteredDocuments = useMemo(() => {
    return documents.filter(doc => {
      const matchesSearch = !searchQuery ||
        doc.filename.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (doc.analysis_summary && doc.analysis_summary.toLowerCase().includes(searchQuery.toLowerCase()));

      const matchesCategory = !categoryFilter ||
        (doc.categories && doc.categories.includes(categoryFilter));

      const matchesStatus = !statusFilter ||
        doc.processing_status === statusFilter;

      return matchesSearch && matchesCategory && matchesStatus;
    });
  }, [documents, searchQuery, categoryFilter, statusFilter]);

  const paginatedDocuments = useMemo(() => {
    const startIndex = (currentPage - 1) * pageSize;
    return filteredDocuments.slice(startIndex, startIndex + pageSize);
  }, [filteredDocuments, currentPage, pageSize]);

  const totalPages = Math.ceil(filteredDocuments.length / pageSize);

  // Get unique categories for filter
  const availableCategories = useMemo(() => {
    const categories = new Set<string>();
    documents.forEach(doc => {
      if (doc.categories) {
        doc.categories.forEach(cat => categories.add(cat));
      }
    });
    return Array.from(categories);
  }, [documents]);

  // Load data on mount
  useEffect(() => {
    loadProjectInsights();
  }, [projectId]);

  // Reset pagination when filters change
  useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery, categoryFilter, statusFilter]);

  if (loading && !projectInsights) {
    return (
      <Group justify="center" p="xl">
        <Loader size="lg" />
      </Group>
    );
  }

  if (error && !projectInsights) {
    return (
      <Alert icon={<IconAlertCircle size={16} />} title="Error" color="red">
        {error}
      </Alert>
    );
  }

  return (
    <div>
      {/* Header */}
      <Group justify="space-between" mb="md">
        <Group gap="sm">
          <IconDatabase size={24} />
          <Title order={2}>Document Analysis Dashboard</Title>
          {projectInsights && (
            <Badge variant="light" color="blue">
              {projectInsights.analyzed_documents}/{projectInsights.total_documents} Analyzed
            </Badge>
          )}
        </Group>
        <Group gap="xs">
          <Button
            size="sm"
            variant="light"
            leftSection={<IconRefresh size={14} />}
            onClick={loadProjectInsights}
            loading={loading}
          >
            Refresh
          </Button>
        </Group>
      </Group>

      {/* Main Content Tabs */}
      <Tabs value={activeTab} onChange={(value) => value && setActiveTab(value)} mb="md">
        <Tabs.List>
          <Tabs.Tab value="overview" leftSection={<IconChartBar size={14} />}>
            Overview
          </Tabs.Tab>
          <Tabs.Tab value="documents" leftSection={<IconFileText size={14} />}>
            Documents ({filteredDocuments.length})
          </Tabs.Tab>
          <Tabs.Tab value="analytics" leftSection={<IconChartPie size={14} />}>
            Analytics
          </Tabs.Tab>
          <Tabs.Tab value="insights" leftSection={<IconBulb size={14} />}>
            Insights
          </Tabs.Tab>
        </Tabs.List>

        {/* Overview Tab */}
        <Tabs.Panel value="overview" pt="md">
          <Grid>
            <Grid.Col span={12}>
              <SimpleGrid cols={4} spacing="lg">
                {/* Total Documents */}
                <Card p="md" radius="md" withBorder>
                  <Group justify="space-between" align="center">
                    <div>
                      <Text size="sm" c="dimmed" tt="uppercase" fw={600}>
                        Total Documents
                      </Text>
                      <Text size="xl" fw={700} c="dark.8">
                        {projectInsights?.total_documents || 0}
                      </Text>
                    </div>
                    <ThemeIcon size={48} radius="md" variant="light" color="blue">
                      <IconFile size={24} />
                    </ThemeIcon>
                  </Group>
                </Card>

                {/* Analyzed Documents */}
                <Card p="md" radius="md" withBorder>
                  <Group justify="space-between" align="center">
                    <div>
                      <Text size="sm" c="dimmed" tt="uppercase" fw={600}>
                        Analyzed
                      </Text>
                      <Text size="xl" fw={700} c="dark.8">
                        {projectInsights?.analyzed_documents || 0}
                      </Text>
                    </div>
                    <RingProgress
                      size={48}
                      thickness={4}
                      sections={[
                        {
                          value: projectInsights ?
                            (projectInsights.analyzed_documents / projectInsights.total_documents) * 100 : 0,
                          color: 'green'
                        }
                      ]}
                      label={
                        <Text size="xs" ta="center">
                          {projectInsights ?
                            Math.round((projectInsights.analyzed_documents / projectInsights.total_documents) * 100) : 0}%
                        </Text>
                      }
                    />
                  </Group>
                </Card>

                {/* Categories Found */}
                <Card p="md" radius="md" withBorder>
                  <Group justify="space-between" align="center">
                    <div>
                      <Text size="sm" c="dimmed" tt="uppercase" fw={600}>
                        Categories
                      </Text>
                      <Text size="xl" fw={700} c="dark.8">
                        {projectInsights?.top_categories?.length || 0}
                      </Text>
                    </div>
                    <ThemeIcon size={48} radius="md" variant="light" color="orange">
                      <IconTag size={24} />
                    </ThemeIcon>
                  </Group>
                </Card>

                {/* Processing Status */}
                <Card p="md" radius="md" withBorder>
                  <Group justify="space-between" align="center">
                    <div>
                      <Text size="sm" c="dimmed" tt="uppercase" fw={600}>
                        Processing
                      </Text>
                      <Text size="xl" fw={700} c="dark.8">
                        {documents.filter(d => d.processing_status === 'completed').length}
                      </Text>
                    </div>
                    <ThemeIcon size={48} radius="md" variant="light" color="green">
                      <IconTrendingUp size={24} />
                    </ThemeIcon>
                  </Group>
                </Card>
              </SimpleGrid>
            </Grid.Col>

            {/* Content Summary */}
            {projectInsights?.content_summary && (
              <Grid.Col span={12}>
                <Card withBorder p="md">
                  <Text size="md" fw={600} mb="sm">Content Summary</Text>
                  <Text size="sm" c="dimmed">
                    {projectInsights.content_summary}
                  </Text>
                </Card>
              </Grid.Col>
            )}

            {/* Top Categories */}
            {projectInsights?.top_categories && projectInsights.top_categories.length > 0 && (
              <Grid.Col span={6}>
                <Card withBorder p="md">
                  <Text size="md" fw={600} mb="sm">Top Categories</Text>
                  <Stack gap="xs">
                    {projectInsights.top_categories.slice(0, 10).map((cat, index) => (
                      <Group key={cat.category} justify="space-between">
                        <Badge variant="light" color="orange">
                          {cat.category}
                        </Badge>
                        <Text size="sm" c="dimmed">{cat.count} documents</Text>
                      </Group>
                    ))}
                  </Stack>
                </Card>
              </Grid.Col>
            )}

            {/* Document Types */}
            {projectInsights?.document_types && (
              <Grid.Col span={6}>
                <Card withBorder p="md">
                  <Text size="md" fw={600} mb="sm">Document Types</Text>
                  <Stack gap="xs">
                    {Object.entries(projectInsights.document_types).map(([type, count]) => (
                      <Group key={type} justify="space-between">
                        <Text size="sm">{type.toUpperCase()}</Text>
                        <Badge variant="light" color="blue">{count as number}</Badge>
                      </Group>
                    ))}
                  </Stack>
                </Card>
              </Grid.Col>
            )}
          </Grid>
        </Tabs.Panel>

        {/* Documents Tab */}
        <Tabs.Panel value="documents" pt="md">
          <Stack gap="md">
            {/* Filters */}
            <Card withBorder p="md">
              <Group gap="md">
                <TextInput
                  placeholder="Search documents..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  leftSection={<IconSearch size={16} />}
                  style={{ flex: 1 }}
                />
                <Select
                  placeholder="Filter by category"
                  value={categoryFilter}
                  onChange={(value) => setCategoryFilter(value || '')}
                  data={[
                    { value: '', label: 'All Categories' },
                    ...availableCategories.map(cat => ({ value: cat, label: cat }))
                  ]}
                  clearable
                  style={{ minWidth: 200 }}
                />
                <Select
                  placeholder="Filter by status"
                  value={statusFilter}
                  onChange={(value) => setStatusFilter(value || '')}
                  data={[
                    { value: '', label: 'All Statuses' },
                    { value: 'completed', label: 'Completed' },
                    { value: 'processing', label: 'Processing' },
                    { value: 'pending', label: 'Pending' },
                    { value: 'failed', label: 'Failed' },
                  ]}
                  clearable
                  style={{ minWidth: 150 }}
                />
                <Group gap="xs">
                  <ActionIcon
                    variant={viewMode === 'list' ? 'filled' : 'light'}
                    onClick={() => setViewMode('list')}
                    color="blue"
                  >
                    <IconList size={16} />
                  </ActionIcon>
                  <ActionIcon
                    variant={viewMode === 'grid' ? 'filled' : 'light'}
                    onClick={() => setViewMode('grid')}
                    color="blue"
                  >
                    <IconGrid3x3 size={16} />
                  </ActionIcon>
                </Group>
              </Group>
            </Card>

            {/* Documents Display */}
            {viewMode === 'list' ? (
              <Card withBorder>
                <ScrollArea h={600}>
                  <Table striped highlightOnHover>
                    <Table.Thead>
                      <Table.Tr>
                        <Table.Th>Document</Table.Th>
                        <Table.Th>Status</Table.Th>
                        <Table.Th>Categories</Table.Th>
                        <Table.Th>Size</Table.Th>
                        <Table.Th>Last Updated</Table.Th>
                        <Table.Th>Actions</Table.Th>
                      </Table.Tr>
                    </Table.Thead>
                    <Table.Tbody>
                      {paginatedDocuments.map((doc) => (
                        <Table.Tr key={doc.filename}>
                          <Table.Td>
                            <Group gap="xs">
                              <IconFile size={16} />
                              <div>
                                <Text size="sm" fw={500} lineClamp={1}>
                                  {doc.filename}
                                </Text>
                                {doc.analysis_summary && (
                                  <Text size="xs" c="dimmed" lineClamp={1}>
                                    {doc.analysis_summary}
                                  </Text>
                                )}
                              </div>
                            </Group>
                          </Table.Td>
                          <Table.Td>
                            <Badge
                              color={
                                doc.processing_status === 'completed' ? 'green' :
                                doc.processing_status === 'processing' ? 'blue' :
                                doc.processing_status === 'failed' ? 'red' : 'gray'
                              }
                              variant="light"
                            >
                              {doc.processing_status}
                            </Badge>
                          </Table.Td>
                          <Table.Td>
                            <Group gap="xs">
                              {doc.categories?.slice(0, 2).map((cat) => (
                                <Badge key={cat} size="xs" variant="light" color="orange">
                                  {cat}
                                </Badge>
                              ))}
                              {doc.categories && doc.categories.length > 2 && (
                                <Badge size="xs" variant="light" color="gray">
                                  +{doc.categories.length - 2}
                                </Badge>
                              )}
                            </Group>
                          </Table.Td>
                          <Table.Td>
                            <Text size="sm">
                              {(doc.content_length / 1024).toFixed(1)} KB
                            </Text>
                          </Table.Td>
                          <Table.Td>
                            <Text size="sm" c="dimmed">
                              {doc.last_updated ?
                                new Date(doc.last_updated).toLocaleDateString() :
                                'Unknown'
                              }
                            </Text>
                          </Table.Td>
                          <Table.Td>
                            <Group gap="xs">
                              <Tooltip label="Analyze Document">
                                <ActionIcon
                                  size="sm"
                                  variant="light"
                                  color="blue"
                                  onClick={() => analyzeDocument(doc.filename)}
                                  loading={analyzingDocument === doc.filename}
                                >
                                  <IconSearch size={14} />
                                </ActionIcon>
                              </Tooltip>
                              <Tooltip label="LLM Analysis">
                                <ActionIcon
                                  size="sm"
                                  variant="light"
                                  color="purple"
                                  onClick={() => analyzeDocument(doc.filename, true)}
                                  loading={analyzingDocument === doc.filename}
                                >
                                  <IconRobot size={14} />
                                </ActionIcon>
                              </Tooltip>
                            </Group>
                          </Table.Td>
                        </Table.Tr>
                      ))}
                    </Table.Tbody>
                  </Table>
                </ScrollArea>

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
              </Card>
            ) : (
              // Grid View
              <SimpleGrid cols={3} spacing="md">
                {paginatedDocuments.map((doc) => (
                  <Card key={doc.filename} withBorder p="md">
                    <Group justify="space-between" mb="xs">
                      <Badge
                        color={
                          doc.processing_status === 'completed' ? 'green' :
                          doc.processing_status === 'processing' ? 'blue' :
                          doc.processing_status === 'failed' ? 'red' : 'gray'
                        }
                        variant="light"
                      >
                        {doc.processing_status}
                      </Badge>
                      <Group gap="xs">
                        <ActionIcon
                          size="sm"
                          variant="light"
                          color="blue"
                          onClick={() => analyzeDocument(doc.filename)}
                          loading={analyzingDocument === doc.filename}
                        >
                          <IconSearch size={12} />
                        </ActionIcon>
                        <ActionIcon
                          size="sm"
                          variant="light"
                          color="purple"
                          onClick={() => analyzeDocument(doc.filename, true)}
                          loading={analyzingDocument === doc.filename}
                        >
                          <IconRobot size={12} />
                        </ActionIcon>
                      </Group>
                    </Group>

                    <Text size="sm" fw={500} mb="xs" lineClamp={2}>
                      {doc.filename}
                    </Text>

                    {doc.analysis_summary && (
                      <Text size="xs" c="dimmed" mb="sm" lineClamp={3}>
                        {doc.analysis_summary}
                      </Text>
                    )}

                    <Group gap="xs" mb="sm">
                      {doc.categories?.slice(0, 3).map((cat) => (
                        <Badge key={cat} size="xs" variant="light" color="orange">
                          {cat}
                        </Badge>
                      ))}
                    </Group>

                    <Group justify="space-between">
                      <Text size="xs" c="dimmed">
                        {(doc.content_length / 1024).toFixed(1)} KB
                      </Text>
                      <Text size="xs" c="dimmed">
                        {doc.last_updated ?
                          new Date(doc.last_updated).toLocaleDateString() :
                          'Unknown'
                        }
                      </Text>
                    </Group>
                  </Card>
                ))}
              </SimpleGrid>
            )}
          </Stack>
        </Tabs.Panel>

        {/* Analytics Tab */}
        <Tabs.Panel value="analytics" pt="md">
          <Grid>
            <Grid.Col span={6}>
              <Card withBorder p="md">
                <Text size="md" fw={600} mb="sm">Document Status Distribution</Text>
                <RingProgress
                  size={200}
                  thickness={20}
                  sections={[
                    {
                      value: (documents.filter(d => d.processing_status === 'completed').length / documents.length) * 100,
                      color: 'green',
                      tooltip: 'Completed'
                    },
                    {
                      value: (documents.filter(d => d.processing_status === 'processing').length / documents.length) * 100,
                      color: 'blue',
                      tooltip: 'Processing'
                    },
                    {
                      value: (documents.filter(d => d.processing_status === 'pending').length / documents.length) * 100,
                      color: 'yellow',
                      tooltip: 'Pending'
                    },
                    {
                      value: (documents.filter(d => d.processing_status === 'failed').length / documents.length) * 100,
                      color: 'red',
                      tooltip: 'Failed'
                    },
                  ]}
                  label={
                    <Text size="xs" ta="center">
                      {documents.filter(d => d.processing_status === 'completed').length}/{documents.length}
                    </Text>
                  }
                />
              </Card>
            </Grid.Col>

            <Grid.Col span={6}>
              <Card withBorder p="md">
                <Text size="md" fw={600} mb="sm">Category Distribution</Text>
                {projectInsights?.top_categories && (
                  <Stack gap="sm">
                    {projectInsights.top_categories.slice(0, 8).map((cat) => (
                      <Group key={cat.category} justify="space-between">
                        <Text size="sm">{cat.category}</Text>
                        <Group gap="xs">
                          <Progress
                            value={(cat.count / projectInsights.total_documents) * 100}
                            size="sm"
                            style={{ flex: 1, maxWidth: 100 }}
                          />
                          <Text size="xs" c="dimmed" style={{ minWidth: 30 }}>
                            {cat.count}
                          </Text>
                        </Group>
                      </Group>
                    ))}
                  </Stack>
                )}
              </Card>
            </Grid.Col>
          </Grid>
        </Tabs.Panel>

        {/* Insights Tab */}
        <Tabs.Panel value="insights" pt="md">
          {projectInsights?.insights && projectInsights.insights.length > 0 ? (
            <Stack gap="md">
              {projectInsights.insights.map((insight, index) => (
                <Card key={index} withBorder p="md">
                  <Group gap="sm">
                    <ThemeIcon size={32} radius="md" variant="light" color="blue">
                      <IconBulb size={16} />
                    </ThemeIcon>
                    <Text size="sm">{insight}</Text>
                  </Group>
                </Card>
              ))}
            </Stack>
          ) : (
            <Alert icon={<IconInfoCircle size={16} />} color="blue">
              No insights available yet. Process and analyze more documents to generate insights.
            </Alert>
          )}
        </Tabs.Panel>
      </Tabs>

      {/* Document Analysis Modal */}
      <Modal
        opened={analysisModalOpen}
        onClose={() => {
          setAnalysisModalOpen(false);
          setSelectedDocument(null);
          setDocumentAnalysis(null);
        }}
        title="Document Analysis Results"
        size="lg"
      >
        {documentAnalysis && selectedDocument && (
          <Stack gap="md">
            <Group justify="space-between">
              <Text fw={600} size="lg">{documentAnalysis.filename}</Text>
              <Badge color="blue" variant="light">
                {documentAnalysis.analysis_type}
              </Badge>
            </Group>

            <Divider />

            {/* Summary */}
            {documentAnalysis.summary && (
              <Card withBorder p="md">
                <Text size="md" fw={600} mb="sm">Summary</Text>
                <Text size="sm" c="dimmed">{documentAnalysis.summary}</Text>
              </Card>
            )}

            {/* Categories */}
            {documentAnalysis.categories && documentAnalysis.categories.length > 0 && (
              <Card withBorder p="md">
                <Text size="md" fw={600} mb="sm">Categories</Text>
                <Group gap="xs">
                  {documentAnalysis.categories.map((category) => (
                    <Badge key={category} color="orange" variant="light">
                      {category}
                    </Badge>
                  ))}
                </Group>
              </Card>
            )}

            {/* Key Insights */}
            {documentAnalysis.key_insights && documentAnalysis.key_insights.length > 0 && (
              <Card withBorder p="md">
                <Text size="md" fw={600} mb="sm">Key Insights</Text>
                <Stack gap="xs">
                  {documentAnalysis.key_insights.map((insight, index) => (
                    <Group key={index} gap="xs">
                      <IconBulb size={14} color="#228be6" />
                      <Text size="sm">{insight}</Text>
                    </Group>
                  ))}
                </Stack>
              </Card>
            )}

            {/* Structure Analysis */}
            {documentAnalysis.structure_analysis && (
              <Card withBorder p="md">
                <Text size="md" fw={600} mb="sm">Structure Analysis</Text>
                <Code block style={{ fontSize: '12px' }}>
                  {JSON.stringify(documentAnalysis.structure_analysis, null, 2)}
                </Code>
              </Card>
            )}

            {/* Metadata */}
            <Card withBorder p="md">
              <Text size="sm" fw={500} mb="xs">Analysis Metadata:</Text>
              <Group gap="md">
                <div>
                  <Text size="xs" c="dimmed">Processing Time</Text>
                  <Text size="sm" fw={500}>{documentAnalysis.processing_time.toFixed(2)}s</Text>
                </div>
                <div>
                  <Text size="xs" c="dimmed">Analysis Timestamp</Text>
                  <Text size="sm" fw={500}>
                    {new Date(documentAnalysis.analysis_timestamp).toLocaleString()}
                  </Text>
                </div>
                <div>
                  <Text size="xs" c="dimmed">Document Size</Text>
                  <Text size="sm" fw={500}>
                    {(selectedDocument.content_length / 1024).toFixed(1)} KB
                  </Text>
                </div>
              </Group>
            </Card>
          </Stack>
        )}
      </Modal>
    </div>
  );
};