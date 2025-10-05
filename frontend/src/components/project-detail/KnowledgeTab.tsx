import React, { useState, useEffect, useMemo } from 'react';
import {
  Card,
  Text,
  Group,
  Badge,
  Tabs,
  Loader,
  Alert,
  ActionIcon,
  TextInput,
  Select,
  Button,
  Stack,
  Paper,
  Grid,
  Divider,
  Accordion,
  Code,
  Modal,
  ThemeIcon,
} from '@mantine/core';
import {
  IconBrain,
  IconBulb,
  IconSearch,
  IconFileText,
  IconTag,
  IconEye,
  IconRefresh,
  IconRobot,
  IconFile,
  IconInfoCircle,
} from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';
import { apiService } from '../../services/api';

interface Discovery { id: string; text: string; category: string; confidence: number; source_document: string; extracted_at: string; project_id: string; }
interface AggregatedFactsResponse { project_id: string; total_facts: number; categories: Record<string,{count:number;items:string[]}>; limit: number|null; timestamp: string; }

interface KnowledgeTabProps {
  projectId: string;
}

export const KnowledgeTab: React.FC<KnowledgeTabProps> = ({ projectId }) => {
  const [activeTab, setActiveTab] = useState<string>('discoveries');
  const [discoveries, setDiscoveries] = useState<Discovery[]>([]); // search mode
  const [aggregated, setAggregated] = useState<AggregatedFactsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<string>('');
  const [categories, setCategories] = useState<Record<string, number>>({});
  const [viewMode, setViewMode] = useState<'aggregated'|'search'>('aggregated');
  const [copying, setCopying] = useState(false);
  const [exporting, setExporting] = useState(false);

  // Document content details state
  // Removed detailed per-document listing for now (placeholder state removed)
  const [selectedDocument, setSelectedDocument] = useState<any>(null);
  const [documentModalOpen, setDocumentModalOpen] = useState(false);
  const [documentAnalysis, setDocumentAnalysis] = useState<any>(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  // Removed expandedDocuments state (no longer used in aggregated view)
  const [projectInsights, setProjectInsights] = useState<any>(null);

  // Load discoveries from the graph service via API Gateway
  const loadDiscoveries = async (category?: string) => {
      // NOTE: Aggregated mode pulls a single bulk response containing all categories and items.
      // Search mode uses legacy per-discovery records for targeted queries.
    try {
      setLoading(true);
      setError(null);
      if (viewMode === 'aggregated') {
        const data = await apiService.getAggregatedDiscoveries(projectId, -1);
        setAggregated(data);
        const catCounts: Record<string, number> = {};
        Object.entries(data.categories).forEach(([c, info]) => { catCounts[c] = info.count; });
        setCategories(catCounts);
      } else {
        const data = await apiService.getProjectDiscoveries(projectId, category && category !== 'all' ? category : undefined);
        setDiscoveries(data.discoveries);
        setCategories(data.categories);
      }

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
    if (!searchQuery.trim()) { setViewMode('aggregated'); loadDiscoveries(categoryFilter || undefined); return; }

    try {
      setLoading(true);
      setError(null);

      // Use apiService instead of direct fetch
  setViewMode('search');
  const data = await apiService.searchProjectDiscoveries(projectId, searchQuery.trim());
  setDiscoveries(data.results as any);

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

  // Per-document detailed listing intentionally omitted in aggregated redesign.

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
  // NOTE: Document expansion feature removed in aggregated redesign; keeping state for potential future
  // granular document detail listing. If reintroduced, implement a memoized map of filename -> expanded.

  // Load discoveries on mount and when category changes
    useEffect(() => {
      // Intentionally not adding loadDiscoveries/loadDocumentDetails to deps to avoid refetch loops.
      // They don't change across renders.
      loadDiscoveries(categoryFilter || undefined);
      loadDocumentDetails();
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [projectId, categoryFilter, viewMode]);

    const filteredAggregated = useMemo(() => {
      if (viewMode !== 'aggregated' || !aggregated) return null;
      const out: AggregatedFactsResponse = { ...aggregated, categories: {} as any };
      Object.entries(aggregated.categories).forEach(([cat, info]) => {
        if (categoryFilter && categoryFilter !== 'all' && cat !== categoryFilter) return;
        const items = info.items.filter(t => !searchQuery || t.toLowerCase().includes(searchQuery.toLowerCase()));
        if (items.length) out.categories[cat] = { count: items.length, items };
      });
      return out;
    }, [aggregated, categoryFilter, searchQuery, viewMode]);

    const totalFactsDisplayed = useMemo(() => {
      if (viewMode === 'aggregated' && filteredAggregated) return Object.values(filteredAggregated.categories).reduce((s,v)=>s+v.count,0);
      if (viewMode === 'search') return discoveries.length;
      return 0;
    }, [filteredAggregated, viewMode, discoveries]);

    const copyAll = async () => {
      try { setCopying(true); let buf='';
        if (viewMode==='aggregated' && filteredAggregated) {
          Object.entries(filteredAggregated.categories).forEach(([cat, info]) => { buf += `# ${cat} (${info.count})\n` + info.items.map(i=>`- ${i}`).join('\n') + '\n\n'; });
        } else if (viewMode==='search') { buf = discoveries.map(d=>`- [${d.category}] ${d.text}`).join('\n'); }
        await navigator.clipboard.writeText(buf.trim()); notifications.show({title:'Copied', message:'Facts copied to clipboard', color:'green'});
      } catch(e:any){ notifications.show({title:'Copy failed', message:e.message || 'Failed to copy', color:'red'}); } finally { setCopying(false);} };

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

  const exportAll = async () => {
    try {
      setExporting(true);
      let content = '';
      if (viewMode === 'aggregated' && aggregated) {
        Object.entries(filteredAggregated?.categories || aggregated.categories).forEach(([cat, info]: any) => {
          content += `\n## ${cat} (${info.count})\n` + info.items.map((i: string)=>`- ${i}`).join('\n');
        });
      } else {
        content = discoveries.map(d=>`- [${d.category}] ${d.text}`).join('\n');
      }
      const blob = new Blob([`# Knowledge Facts Export\nProject: ${projectId}\nGenerated: ${new Date().toISOString()}\n${content}\n`], { type: 'text/markdown;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = `knowledge_facts_${projectId}.md`; a.click();
      URL.revokeObjectURL(url);
      notifications.show({ title:'Export Complete', message:'Markdown file downloaded', color:'green'});
    } catch (e:any) {
      notifications.show({ title:'Export Failed', message:e.message || 'Unable to export', color:'red'});
    } finally {
      setExporting(false);
    }
  };

  // Confidence color utility removed (confidence not displayed in aggregated view). Re-add if needed.

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
          <Badge variant="light" color="blue">{totalFactsDisplayed} Facts</Badge>
          {projectInsights && (
            <Badge variant="light" color="green">
              {projectInsights.analyzed_documents}/{projectInsights.total_documents} Documents Analyzed
            </Badge>
          )}
        </Group>
        <Group gap="xs">
          <Button size="xs" variant={viewMode==='aggregated'?'filled':'light'} onClick={()=>{setViewMode('aggregated'); setSearchQuery('');}}>Aggregated</Button>
          <Button size="xs" variant={viewMode==='search'?'filled':'light'} onClick={()=>setViewMode('search')}>Search</Button>
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
          <Button size="xs" variant="light" onClick={copyAll} loading={copying} disabled={totalFactsDisplayed===0}>Copy</Button>
          <Button size="xs" variant="light" onClick={exportAll} loading={exporting} disabled={totalFactsDisplayed===0}>Export</Button>
          {/* TODO: Add optional Export (.md / .txt) button if download of facts is desired */}
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
          <Tabs.Tab value="discoveries" leftSection={<IconBrain size={14} />}>Knowledge Facts ({totalFactsDisplayed})</Tabs.Tab>
          <Tabs.Tab value="documents" leftSection={<IconFileText size={14} />}>
            Document Content
          </Tabs.Tab>
          <Tabs.Tab value="insights" leftSection={<IconBulb size={14} />}>
            Project Insights
          </Tabs.Tab>
        </Tabs.List>

        {/* Knowledge Facts Tab - Consolidated View */}
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
          ) : ((viewMode==='aggregated' && (!filteredAggregated || Object.keys(filteredAggregated.categories).length===0)) || (viewMode==='search' && discoveries.length===0)) ? (
            <Alert icon={<IconBrain size={16} />} title="No Knowledge Found" color="blue">
              No discoveries have been extracted yet. Upload and process documents to generate foundational facts.
            </Alert>
          ) : (() => {
            const categoryEntries: Array<[string,{count:number;items:string[]}]> = viewMode==='aggregated' && filteredAggregated
              ? Object.entries(filteredAggregated.categories).sort((a,b)=>b[1].count - a[1].count)
              : Object.entries(discoveries.reduce((acc,d)=>{ (acc[d.category]=acc[d.category]||{count:0,items:[]}); acc[d.category].count++; acc[d.category].items.push(d.text); return acc; },{} as Record<string,{count:number;items:string[]}>)).sort((a,b)=>b[1].count - a[1].count);

            return (
              <Card withBorder radius="md" p="lg">
                {/* Summary Header */}
                <Group justify="space-between" mb="lg">
                  <Group gap="sm">
                    <IconBrain size={24} />
                    <div>
                      <Text size="lg" fw={600}>Knowledge Facts</Text>
                      <Text size="sm" c="dimmed">{totalFactsDisplayed} total facts from {categoryEntries.length} categories {viewMode==='search' && '(search mode)'}</Text>
                    </div>
                  </Group>
                  <Group gap="xs">
                    {Object.entries(categories).slice(0, 6).map(([category, count]) => (
                      <Badge
                        key={category}
                        color={getCategoryColor(category)}
                        variant="light"
                        size="sm"
                      >
                        {category}: {count}
                      </Badge>
                    ))}
                  </Group>
                </Group>

                <Divider mb="md" />

                {/* Accordion by Category */}
                <Accordion multiple defaultValue={categoryEntries.slice(0,2).map(([c])=>c)}>
                  {categoryEntries.map(([category, info]) => (
                    <Accordion.Item key={category} value={category}>
                      <Accordion.Control icon={
                        <ThemeIcon color={getCategoryColor(category)} variant="light" size="sm">
                          <IconTag size={14} />
                        </ThemeIcon>
                      }>
                        <Group justify="space-between" style={{ flex: 1, marginRight: '1rem' }}>
                          <Text fw={600} tt="capitalize">{category}</Text>
                          <Badge color={getCategoryColor(category)} variant="filled" size="sm">{info.count} facts</Badge>
                        </Group>
                      </Accordion.Control>
                      <Accordion.Panel>
                        <Stack gap="md">
                          {info.items.map((text, idx) => (
                            <Paper key={idx} p="sm" withBorder bg="gray.0">
                              <Text size="sm"><Text component="span" fw={500} mr="xs">{idx+1}.</Text>{text}</Text>
                            </Paper>
                          ))}
                        </Stack>
                      </Accordion.Panel>
                    </Accordion.Item>
                  ))}
                </Accordion>
              </Card>
            );
          })()}
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