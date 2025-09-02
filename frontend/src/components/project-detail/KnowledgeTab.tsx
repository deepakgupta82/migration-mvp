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
  Collapse,
  Accordion,
  Code,
  Progress,
  Modal,
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
} from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';
import { apiService } from '../../services/api';

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

  // Document content details state
  const [documentDetails, setDocumentDetails] = useState<any[]>([]);
  const [selectedDocument, setSelectedDocument] = useState<any>(null);
  const [documentModalOpen, setDocumentModalOpen] = useState(false);
  const [documentAnalysis, setDocumentAnalysis] = useState<any>(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [expandedDocuments, setExpandedDocuments] = useState<Set<string>>(new Set());
  const [projectInsights, setProjectInsights] = useState<any>(null);

  // Load discoveries from the graph service via API Gateway
  const loadDiscoveries = async (category?: string) => {
    try {
      setLoading(true);
      setError(null);

      // Use apiService instead of direct fetch to graph service
      const data = await apiService.getProjectDiscoveries(projectId, category && category !== 'all' ? category : undefined);
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

      // Use apiService instead of direct fetch
      const data = await apiService.searchProjectDiscoveries(projectId, searchQuery.trim());
      setDiscoveries(data.results);

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Search failed';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  // Load document content details
  const loadDocumentDetails = async () => {
    try {
      setLoading(true);
      setError(null);

      // Get project insights first
      const insights = await apiService.getProjectContentInsights(projectId);
      setProjectInsights(insights);

      // For now, we'll show a summary. In a full implementation, we'd load individual document details
      // This is a placeholder for the document details functionality
      setDocumentDetails([]);

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to load document details';
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

  // Analyze specific document using new database-backed API endpoints
  const analyzeDocument = async (filename: string) => {
    try {
      setAnalysisLoading(true);

      // First, try to get existing analysis results for this document
      const existingAnalyses = await apiService.listAnalysisResults(projectId, {
        filename: filename,
        limit: 1
      });

      let analysisResult;

      if (existingAnalyses.results && existingAnalyses.results.length > 0) {
        // Use existing analysis result
        const existingAnalysis = existingAnalyses.results[0];
        analysisResult = await apiService.getAnalysisResult(projectId, existingAnalysis.analysis_id);
      } else {
        // Create new analysis result using the new database-backed endpoint
        const analysisData = {
          filename,
          analysis_type: 'comprehensive',
          summary: '',
          categories: [],
          key_insights: [],
          structure_analysis: {},
          content_preview: '',
          quality_score: 0,
          processing_time: 0,
          metadata: {
            use_llm: false,
            created_via_knowledge_tab: true
          }
        };

        // Create the analysis result in the database
        const createResponse = await apiService.createAnalysisResult(projectId, analysisData);

        // Get the created analysis result
        analysisResult = await apiService.getAnalysisResult(projectId, createResponse.analysis_id);
      }

      setDocumentAnalysis(analysisResult);

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
      setAnalysisLoading(false);
    }
  };

  // LLM-enhanced analysis using new database-backed API endpoints
  const analyzeDocumentWithLLM = async (filename: string) => {
    try {
      setAnalysisLoading(true);

      // First, try to get existing analysis results for this document
      const existingAnalyses = await apiService.listAnalysisResults(projectId, {
        filename: filename,
        limit: 1
      });

      let analysisResult;

      if (existingAnalyses.results && existingAnalyses.results.length > 0) {
        // Use existing analysis result
        const existingAnalysis = existingAnalyses.results[0];
        analysisResult = await apiService.getAnalysisResult(projectId, existingAnalysis.analysis_id);
      } else {
        // Create new analysis result using the new database-backed endpoint
        const analysisData = {
          filename,
          analysis_type: 'llm-enhanced',
          summary: '',
          categories: [],
          key_insights: [],
          structure_analysis: {},
          content_preview: '',
          quality_score: 0,
          processing_time: 0,
          metadata: {
            use_llm: true,
            created_via_knowledge_tab: true
          }
        };

        // Create the analysis result in the database
        const createResponse = await apiService.createAnalysisResult(projectId, analysisData);

        // Get the created analysis result
        analysisResult = await apiService.getAnalysisResult(projectId, createResponse.analysis_id);
      }

      setDocumentAnalysis(analysisResult);

      notifications.show({
        title: 'LLM Analysis Complete',
        message: `LLM-enhanced analysis completed for ${filename}`,
        color: 'green',
      });

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to perform LLM analysis';
      notifications.show({
        title: 'LLM Analysis Failed',
        message: errorMessage,
        color: 'red',
      });
    } finally {
      setAnalysisLoading(false);
    }
  };

  // Toggle document expansion
  const toggleDocumentExpansion = (filename: string) => {
    const newExpanded = new Set(expandedDocuments);
    if (newExpanded.has(filename)) {
      newExpanded.delete(filename);
    } else {
      newExpanded.add(filename);
    }
    setExpandedDocuments(newExpanded);
  };

  // Load discoveries on mount and when category changes
  useEffect(() => {
    loadDiscoveries(categoryFilter || undefined);
    loadDocumentDetails();
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
          {projectInsights && (
            <Badge variant="light" color="green">
              {projectInsights.analyzed_documents}/{projectInsights.total_documents} Documents Analyzed
            </Badge>
          )}
        </Group>
        <Group gap="xs">
          <Button
            size="xs"
            variant="light"
            leftSection={<IconRefresh size={14} />}
            onClick={() => {
              loadDiscoveries(categoryFilter || undefined);
              loadDocumentDetails();
            }}
            loading={loading}
          >
            Refresh
          </Button>
        </Group>
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

      {/* Content Tabs */}
      <Tabs value={activeTab} onChange={(value) => value && setActiveTab(value)} mb="md">
        <Tabs.List>
          <Tabs.Tab value="discoveries" leftSection={<IconBrain size={14} />}>
            Knowledge Facts ({discoveries.length})
          </Tabs.Tab>
          <Tabs.Tab value="documents" leftSection={<IconFileText size={14} />}>
            Document Content
          </Tabs.Tab>
          <Tabs.Tab value="insights" leftSection={<IconBulb size={14} />}>
            Project Insights
          </Tabs.Tab>
        </Tabs.List>

        {/* Knowledge Facts Tab */}
        <Tabs.Panel value="discoveries" pt="md">
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
        </Tabs.Panel>

        {/* Document Content Tab */}
        <Tabs.Panel value="documents" pt="md">
          {loading ? (
            <Group justify="center" p="xl">
              <Loader size="lg" />
            </Group>
          ) : (
            <Stack gap="md">
              {/* Document Content Summary */}
              {projectInsights && (
                <Card withBorder p="md">
                  <Text size="md" fw={600} mb="sm">Document Analysis Summary</Text>
                  <Group gap="md" mb="sm">
                    <Badge color="blue" variant="light">
                      {projectInsights.total_documents} Total Documents
                    </Badge>
                    <Badge color="green" variant="light">
                      {projectInsights.analyzed_documents} Analyzed
                    </Badge>
                  </Group>

                  {projectInsights.top_categories && projectInsights.top_categories.length > 0 && (
                    <div>
                      <Text size="sm" fw={500} mb="xs">Top Categories:</Text>
                      <Group gap="xs">
                        {projectInsights.top_categories.slice(0, 5).map((cat: any) => (
                          <Badge key={cat.category} color="orange" variant="light">
                            {cat.category} ({cat.count})
                          </Badge>
                        ))}
                      </Group>
                    </div>
                  )}
                </Card>
              )}

              {/* Document List with Expandable Details */}
              <Card withBorder p="md">
                <Text size="md" fw={600} mb="sm">Document Details</Text>
                <Text size="sm" c="dimmed" mb="md">
                  Click on documents to view their content summaries, categories, and structure metadata.
                </Text>

                {projectInsights && projectInsights.document_types ? (
                  <Stack gap="sm">
                    {Object.entries(projectInsights.document_types).map(([type, count]) => (
                      <Paper key={type} p="sm" withBorder>
                        <Group justify="space-between">
                          <Group gap="xs">
                            <IconFile size={16} />
                            <Text size="sm" fw={500}>{type.toUpperCase()}</Text>
                            <Badge size="xs" color="gray">{count as number} files</Badge>
                          </Group>
                          <ActionIcon
                            size="sm"
                            variant="light"
                            color="blue"
                            onClick={() => {
                              // Placeholder for document type analysis
                              notifications.show({
                                title: 'Document Type Analysis',
                                message: `Analyzing ${count} ${type} documents...`,
                                color: 'blue',
                              });
                            }}
                          >
                            <IconEye size={14} />
                          </ActionIcon>
                        </Group>
                      </Paper>
                    ))}
                  </Stack>
                ) : (
                  <Alert icon={<IconInfoCircle size={16} />} color="blue">
                    No document details available yet. Process documents to generate content analysis.
                  </Alert>
                )}
              </Card>
            </Stack>
          )}
        </Tabs.Panel>

        {/* Project Insights Tab */}
        <Tabs.Panel value="insights" pt="md">
          {projectInsights ? (
            <Stack gap="md">
              <Card withBorder p="md">
                <Text size="md" fw={600} mb="sm">Project Content Insights</Text>

                <Grid>
                  <Grid.Col span={6}>
                    <Paper p="sm" withBorder bg="gray.0">
                      <Text size="sm" c="dimmed">Total Documents</Text>
                      <Text size="xl" fw={600}>{projectInsights.total_documents}</Text>
                    </Paper>
                  </Grid.Col>
                  <Grid.Col span={6}>
                    <Paper p="sm" withBorder bg="gray.0">
                      <Text size="sm" c="dimmed">Analyzed Documents</Text>
                      <Text size="xl" fw={600}>{projectInsights.analyzed_documents}</Text>
                    </Paper>
                  </Grid.Col>
                </Grid>

                {projectInsights.content_summary && (
                  <div>
                    <Text size="sm" fw={500} mt="md" mb="xs">Content Summary:</Text>
                    <Text size="sm" c="dimmed">{projectInsights.content_summary}</Text>
                  </div>
                )}

                {projectInsights.insights && projectInsights.insights.length > 0 && (
                  <div>
                    <Text size="sm" fw={500} mt="md" mb="xs">Key Insights:</Text>
                    <Stack gap="xs">
                      {projectInsights.insights.map((insight: string, index: number) => (
                        <Group key={index} gap="xs">
                          <IconBulb size={14} color="#228be6" />
                          <Text size="sm">{insight}</Text>
                        </Group>
                      ))}
                    </Stack>
                  </div>
                )}
              </Card>
            </Stack>
          ) : (
            <Alert icon={<IconInfoCircle size={16} />} color="blue">
              No project insights available yet. Process and analyze documents to generate insights.
            </Alert>
          )}
        </Tabs.Panel>
      </Tabs>

      {/* Footer Info */}
      <Paper p="sm" mt="md" withBorder style={{ backgroundColor: '#f8f9fa' }}>
        <Text size="xs" c="dimmed">
          <IconBulb size={12} style={{ marginRight: 4 }} />
          <strong>Knowledge Base:</strong> This tab shows foundational facts (Stage 1) extracted automatically from documents,
          plus synthesized insights (Stage 2) generated by AI agents. Facts provide the base knowledge layer that agents
          use to generate more sophisticated insights and recommendations.
        </Text>
      </Paper>

      {/* Document Analysis Modal */}
      <Modal
        opened={documentModalOpen}
        onClose={() => {
          setDocumentModalOpen(false);
          setSelectedDocument(null);
          setDocumentAnalysis(null);
        }}
        title="Document Content Analysis"
        size="lg"
      >
        {selectedDocument && (
          <Stack gap="md">
            <Group justify="space-between">
              <Text fw={600} size="lg">{selectedDocument.filename}</Text>
              <Badge color="blue" variant="light">
                {selectedDocument.processing_status || 'Available'}
              </Badge>
            </Group>

            <Divider />

            {/* Analysis Actions */}
            <Group gap="sm">
              <Button
                size="sm"
                variant="light"
                leftSection={<IconSearch size={14} />}
                onClick={() => analyzeDocument(selectedDocument.filename)}
                loading={analysisLoading}
              >
                Analyze Content
              </Button>
              <Button
                size="sm"
                variant="light"
                color="purple"
                leftSection={<IconRobot size={14} />}
                onClick={() => analyzeDocumentWithLLM(selectedDocument.filename)}
                loading={analysisLoading}
              >
                LLM Analysis
              </Button>
            </Group>

            {/* Analysis Results */}
            {documentAnalysis && (
              <Card withBorder p="md">
                <Text size="md" fw={600} mb="sm">Analysis Results</Text>

                {documentAnalysis.summary && (
                  <div>
                    <Text size="sm" fw={500} mb="xs">Summary:</Text>
                    <Text size="sm" c="dimmed" mb="md">{documentAnalysis.summary}</Text>
                  </div>
                )}

                {documentAnalysis.categories && documentAnalysis.categories.length > 0 && (
                  <div>
                    <Text size="sm" fw={500} mb="xs">Categories:</Text>
                    <Group gap="xs" mb="md">
                      {documentAnalysis.categories.map((category: string) => (
                        <Badge key={category} color="orange" variant="light">
                          {category}
                        </Badge>
                      ))}
                    </Group>
                  </div>
                )}

                {documentAnalysis.key_insights && documentAnalysis.key_insights.length > 0 && (
                  <div>
                    <Text size="sm" fw={500} mb="xs">Key Insights:</Text>
                    <Stack gap="xs" mb="md">
                      {documentAnalysis.key_insights.map((insight: string, index: number) => (
                        <Group key={index} gap="xs">
                          <IconBulb size={14} color="#228be6" />
                          <Text size="sm">{insight}</Text>
                        </Group>
                      ))}
                    </Stack>
                  </div>
                )}

                {documentAnalysis.structure_analysis && (
                  <div>
                    <Text size="sm" fw={500} mb="xs">Structure Analysis:</Text>
                    <Code block style={{ fontSize: '12px' }}>
                      {JSON.stringify(documentAnalysis.structure_analysis, null, 2)}
                    </Code>
                  </div>
                )}

                <Group gap="xs" mt="sm">
                  <Text size="xs" c="dimmed">Analysis completed in</Text>
                  <Badge size="xs" color="green">
                    {documentAnalysis.processing_time?.toFixed(2) || '0.00'}s
                  </Badge>
                </Group>
              </Card>
            )}

            {/* Document Metadata */}
            <Card withBorder p="md">
              <Text size="sm" fw={500} mb="xs">Document Metadata:</Text>
              <Group gap="md">
                <div>
                  <Text size="xs" c="dimmed">Content Length</Text>
                  <Text size="sm" fw={500}>{selectedDocument.content_length || 0} characters</Text>
                </div>
                <div>
                  <Text size="xs" c="dimmed">Last Updated</Text>
                  <Text size="sm" fw={500}>
                    {selectedDocument.last_updated
                      ? new Date(selectedDocument.last_updated).toLocaleDateString()
                      : 'Unknown'
                    }
                  </Text>
                </div>
                <div>
                  <Text size="xs" c="dimmed">Structured Data</Text>
                  <Badge size="xs" color={selectedDocument.has_structured_data ? 'green' : 'gray'}>
                    {selectedDocument.has_structured_data ? 'Available' : 'Not Available'}
                  </Badge>
                </div>
              </Group>
            </Card>
          </Stack>
        )}
      </Modal>
    </div>
  );
};