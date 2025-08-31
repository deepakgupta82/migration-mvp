/**
 * Project Detail View - Multi-tabbed workspace for individual projects
 */

import React, { useState, useEffect, useRef } from 'react';
import {
  Card,
  Text,
  Group,
  Badge,
  Tabs,
  Button,
  Grid,
  Paper,
  Loader,
  Alert,
  Table,
  ActionIcon,
  Divider,
  Modal,
  Select,
  Stack,
  Textarea,
  Collapse,
} from '@mantine/core';
import {
  IconFolder,
  IconFile,
  IconUpload,
  IconGraph,
  IconMessageCircle,
  IconFileText,
  IconDownload,
  IconAlertCircle,
  IconCalendar,
  IconUser,
  IconRefresh,
  IconRobot,
  IconHistory,
  IconTemplate,
  IconDatabase,
  IconClock,
  IconCheck,
  IconWifi,
  IconWifiOff,
  IconSettings,
  IconEdit,
  IconEye,
  IconEyeOff,
  IconTrash,
  IconBrain,
  IconBulb,
  IconSearch,
} from '@tabler/icons-react';
import { useParams, useNavigate } from 'react-router-dom';
import { notifications } from '@mantine/notifications';
// import ReactMarkdown from 'react-markdown';
// import remarkGfm from 'remark-gfm';
// import rehypeHighlight from 'rehype-highlight';
import { useProject } from '../hooks/useProjects';
import { ProjectOverviewPage } from './project/ProjectOverviewPage';
import { ProjectPlaceholderPage } from './project/ProjectPlaceholderPage';
import { GraphVisualizer } from '../components/project-detail/GraphVisualizer';
import InteractiveGraphVisualizer from '../components/project-detail/InteractiveGraphVisualizer';
import { ChatInterface } from '../components/project-detail/ChatInterface';
import AgentActivityLog from '../components/project-detail/AgentActivityLog';
import ProjectHistory from '../components/project-detail/ProjectHistory';
import DocumentTemplates from '../components/project-detail/DocumentTemplates';
import CrewInteractionViewer from '../components/project-detail/CrewInteractionViewer';
import FloatingChatWidget from '../components/FloatingChatWidget';
import FileUpload, { FileUploadHandle } from '../components/FileUpload';
import ProcessLLMConfiguration from '../components/ProcessLLMConfiguration';
import ProcessingProgressView from '../components/ProcessingProgressView';
import MinIODirectoryBrowser from '../components/MinIODirectoryBrowser';
import { KnowledgeTab } from '../components/project-detail/KnowledgeTab';
import { apiService } from '../services/api';
import { useProjectStats } from '../hooks/useStatsWebSocket';
import { useAssessment } from '../contexts/AssessmentContext';

// Helper function for status colors
const getStatusColor = (status: string) => {
  switch (status?.toLowerCase()) {
    case 'completed':
      return 'green';
    case 'running':
      return 'blue';
    case 'failed':
      return 'red';
    case 'initiated':
      return 'orange';
    default:
      return 'gray';
  }
};

export const ProjectDetailView: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const { project, loading, error, fetchProject } = useProject(projectId || null);
  const [activeTab, setActiveTab] = useState<string>('overview');
  const [discoveryTab, setDiscoveryTab] = useState<string>('knowledge-graph');
  const [reportContent, setReportContent] = useState<string>('');
  const [reportLoading, setReportLoading] = useState(false);
  const fileUploadRef = useRef<FileUploadHandle | null>(null);
  const [showProgressHeader, setShowProgressHeader] = useState(false);

  // Use WebSocket-based project stats
  const { stats: wsProjectStats, loading: statsLoading, error: statsError, lastEvent, refreshStats } = useProjectStats(projectId || '');

  // Convert WebSocket stats to legacy format for compatibility
  const projectStats = {
    fileCount: wsProjectStats?.files_count || 0,
    embeddings: wsProjectStats?.embeddings_count || 0,
    graphNodes: wsProjectStats?.graph_nodes || 0,
    agentInteractions: wsProjectStats?.agent_interactions || 0,
    deliverables: wsProjectStats?.deliverables || 0
  };
  const [llmConfigModalOpen, setLlmConfigModalOpen] = useState(false);
  const [llmConfigs, setLlmConfigs] = useState<any[]>([]);
  const [selectedLlmConfig, setSelectedLlmConfig] = useState('');
  const [testingLLM, setTestingLLM] = useState(false);
  const [testResult, setTestResult] = useState<any>(null);
  const [testQuery, setTestQuery] = useState('');
  const [selectedConfigName, setSelectedConfigName] = useState('');
  // Project Brief (description / RFP / timeline)
  const [showProjectBrief, setShowProjectBrief] = useState<boolean>(false);
  const [isEditingBrief, setIsEditingBrief] = useState<boolean>(false);
  const [briefDescription, setBriefDescription] = useState<string>('');
  const [briefRfp, setBriefRfp] = useState<string>('');
  const [briefTimeline, setBriefTimeline] = useState<string>('');
  
  // Processing Progress View state
  const [showProcessingProgress, setShowProcessingProgress] = useState(false);

  // Assessment state management from context
  const { assessmentState, startAssessment, setStatus, addLog, setProgress, stopAssessment } = useAssessment();

  // Load LLM configurations
  const loadLLMConfigurations = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/llm/configurations');
      if (response.ok) {
  const configs = await response.json();
  setLlmConfigs(Array.isArray(configs) ? configs : []);
        // Set current project's LLM config as selected only if we have project data
        if (project?.llm_api_key_id && configs.length > 0) {
          const configExists = configs.find((c: any) => c && c.id?.toString() === project.llm_api_key_id?.toString());
          if (configExists) {
            setSelectedLlmConfig(project.llm_api_key_id.toString());
          }
        }
      }
    } catch (error) {
      console.error('Failed to load LLM configurations:', error);
    }
  };

  // Test LLM configuration
  const testProjectLLM = async () => {
    if (!projectId || !project?.llm_api_key_id) return;

    setTestingLLM(true);
    setTestResult(null);

    try {
      const testQuery = "TEST REQUEST: Please respond with 'TEST SUCCESSFUL - LLM is working correctly' to confirm connectivity.";
      setTestQuery(testQuery);

      // Use unified GET test endpoint (server handles API key retrieval)
  const response = await fetch(`http://localhost:8000/api/llm/test-llm-config?config_id=${encodeURIComponent(project.llm_api_key_id.toString())}&test_query=${encodeURIComponent(testQuery)}`, {
        method: 'GET'
      });

      const result = await response.json();
      setTestResult({
        ...result,
        timestamp: new Date().toLocaleTimeString(),
        query: testQuery,
        configName: `${project.llm_provider}/${project.llm_model}`
      });

      if (response.ok && result.status === 'success') {
        notifications.show({
          title: 'LLM Test Successful',
          message: `${project?.llm_provider}/${project?.llm_model} is working correctly. Check details below.`,
          color: 'green',
        });
      } else {
        notifications.show({
          title: 'LLM Test Failed',
          message: result.message || 'Failed to connect to LLM. Check details below.',
          color: 'red',
        });
      }
    } catch (error) {
      setTestResult({
        status: 'error',
        message: `Test failed: ${error}`,
        timestamp: new Date().toLocaleTimeString(),
        query: "TEST REQUEST: Please respond with 'TEST SUCCESSFUL - LLM is working correctly' to confirm connectivity.",
        configName: `${project?.llm_provider || 'Unknown'}/${project?.llm_model || 'Unknown'}`
      });

      notifications.show({
        title: 'LLM Test Error',
        message: 'Failed to test LLM configuration. Check details below.',
        color: 'red',
      });
    } finally {
      setTestingLLM(false);
    }
  };

  // Test selected LLM configuration
  const testSelectedLLMConfig = async () => {
    if (!selectedLlmConfig || !projectId) return;

    setTestingLLM(true);
    setTestResult(null);

    try {
      const testQuery = "TEST REQUEST: Please respond with 'TEST SUCCESSFUL - LLM is working correctly' to confirm connectivity.";
      setTestQuery(testQuery);

      // Use unified GET test endpoint (server handles API key retrieval)
  const response = await fetch(`http://localhost:8000/api/llm/test-llm-config?config_id=${encodeURIComponent(selectedLlmConfig)}&test_query=${encodeURIComponent(testQuery)}`, {
        method: 'GET'
      });

      const result = await response.json();
      setTestResult({
        ...result,
        timestamp: new Date().toLocaleTimeString(),
        query: testQuery,
        configName: selectedConfigName
      });

      if (response.ok && result.status === 'success') {
        notifications.show({
          title: 'LLM Test Successful',
          message: `${selectedConfigName} is working correctly. You can now save this configuration.`,
          color: 'green',
        });
      } else {
        notifications.show({
          title: 'LLM Test Failed',
          message: result.message || 'Failed to connect to LLM. Check details below.',
          color: 'red',
        });
      }
    } catch (error) {
      setTestResult({
        status: 'error',
        message: `Test failed: ${error}`,
        timestamp: new Date().toLocaleTimeString(),
        query: testQuery,
        configName: selectedConfigName
      });

      notifications.show({
        title: 'LLM Test Error',
        message: 'Failed to test LLM configuration. Check details below.',
        color: 'red',
      });
    } finally {
      setTestingLLM(false);
    }
  };

  // Save project LLM configuration
  const saveProjectLLM = async () => {
    if (!projectId || !selectedLlmConfig) return;

    try {
  const selectedConfig = llmConfigs.find(c => c && c.id?.toString() === selectedLlmConfig);
      if (!selectedConfig) return;

      setSelectedConfigName(selectedConfig.name);

      // Update the project with selected LLM configuration
      const updateResponse = await fetch(`http://localhost:8000/api/projects/${projectId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          llm_provider: selectedConfig.provider,
          llm_model: selectedConfig.model,
          llm_api_key_id: selectedConfig.id,
          llm_temperature: selectedConfig.temperature?.toString() || '0.1',
          llm_max_tokens: selectedConfig.max_tokens?.toString() || '4000'
        }),
      });

      if (updateResponse.ok) {
        notifications.show({
          title: 'LLM Configuration Saved',
          message: `Project now uses ${selectedConfig.name}`,
          color: 'green',
        });

        setLlmConfigModalOpen(false);

        // Refresh project data instead of full page reload
        if (projectId) {
          await fetchProject(projectId);
        }
      } else {
        throw new Error('Failed to update project');
      }
    } catch (error) {
      notifications.show({
        title: 'Save Failed',
        message: 'Failed to save LLM configuration',
        color: 'red',
      });
    }
  };

  // Handle project deletion
  const handleDeleteProject = async () => {
    if (!projectId) return;

    const confirmed = window.confirm(`Are you sure you want to delete the project "${project?.name}"? This action cannot be undone.`);

    if (!confirmed) return;

    try {
      const response = await fetch(`http://localhost:8000/api/projects/${projectId}`, {
        method: 'DELETE',
      });

      if (response.ok) {
        notifications.show({
          title: 'Project Deleted',
          message: 'Project has been successfully deleted',
          color: 'green',
        });

        // Navigate back to projects list
        navigate('/projects');
      } else {
        throw new Error('Failed to delete project');
      }
    } catch (error) {
      notifications.show({
        title: 'Delete Failed',
        message: 'Failed to delete project. Please try again.',
        color: 'red',
      });
    }
  };

  // Load LLM configurations when component mounts and when modal opens
  useEffect(() => {
    if (project) {
      loadLLMConfigurations();
  // Initialize brief fields from project when loaded
  setBriefDescription(project.description || '');
  setBriefRfp((project as any).rfp || '');
  setBriefTimeline((project as any).timeline || '');
    }
  }, [project]);

  // Set selected config when both project and configs are available
  useEffect(() => {
    if (project?.llm_api_key_id && llmConfigs.length > 0 && !selectedLlmConfig) {
      const configExists = llmConfigs.find(c => c && c.id?.toString() === project.llm_api_key_id?.toString());
      if (configExists) {
        setSelectedLlmConfig(project.llm_api_key_id.toString());
      }
    }
  }, [project, llmConfigs, selectedLlmConfig]);

  useEffect(() => {
    if (llmConfigModalOpen) {
      loadLLMConfigurations();
    }
  }, [llmConfigModalOpen]);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'green';
      case 'running':
        return 'yellow';
      case 'initiated':
        return 'blue';
      default:
        return 'gray';
    }
  };

  const fetchReportContent = async () => {
    if (!projectId) return;

    try {
      setReportLoading(true);
      const response = await apiService.getProjectReport(projectId);
      setReportContent(response.report_content);
    } catch (err) {
      console.error('Failed to fetch report content:', err);
      setReportContent('Report content not available yet. Complete an assessment to generate the report.');
    } finally {
      setReportLoading(false);
    }
  };

  // Legacy function for compatibility - now just refreshes WebSocket stats
  const fetchProjectStats = () => {
    refreshStats();
    if (projectId) {
      // Kick off assessment UI flow when files uploaded
      if (!assessmentState.isRunning && assessmentState.status !== 'running') {
        startAssessment(projectId);
        notifications.show({ title: 'Processing started', message: 'Document processing initiated', color: 'blue' });
      }
    }
  };

  // React to WebSocket stats events to update notifications and progress pane
  useEffect(() => {
    if (!lastEvent) return;
    const evt = String(lastEvent).toLowerCase();
    const log = (m: string) => addLog(m);

    if (evt.includes('started')) {
      setStatus('running');
      log('Processing started');
      setProgress(5);
    }
    if (evt.includes('chunk') || evt.includes('ingest')) {
      log('Chunking completed');
      setProgress(30);
    }
    if (evt.includes('embedding')) {
      log('Embeddings updated');
      setProgress(60);
    }
    if (evt.includes('graph')) {
      log('Graph updated');
      setProgress(90);
    }
    if (evt.includes('complete') || evt.includes('done')) {
      setProgress(100);
      setStatus('completed');
      log('Processing completed');
      notifications.show({ title: 'Processing complete', message: 'All steps finished successfully', color: 'green' });
      stopAssessment();
    }
    if (evt.includes('fail') || evt.includes('error')) {
      setStatus('failed');
      log('Processing failed');
      notifications.show({ title: 'Processing failed', message: 'Check logs for details', color: 'red' });
    }
  }, [lastEvent, setStatus, addLog, setProgress, stopAssessment]);

  React.useEffect(() => {
    if (activeTab === 'report' && projectId) {
      fetchReportContent();
    }
  }, [activeTab, projectId]);

  // No longer need manual stats fetching - WebSocket handles it automatically

  if (loading) {
    return (
      <Group justify="center" p="xl">
        <Loader size="lg" />
      </Group>
    );
  }

  if (error || !project) {
    return (
      <Alert icon={<IconAlertCircle size={16} />} title="Error" color="red">
        {error || 'Project not found'}
      </Alert>
    );
  }

  return (
    <div style={{ paddingRight: 4 }}>
      {/* Project Details compact header with actions */}
      <Group justify="space-between" mb="xs">
        <Group gap="sm">
          <Text size="lg" fw={700}>Project Details</Text>
          {project?.name && (
            <Badge variant="light" color="gray">{project.name}</Badge>
          )}
        </Group>
        <Group gap="xs">
          <Button
            size="xs"
            variant="light"
            leftSection={<IconDatabase size={14} />}
            onClick={() => { fileUploadRef.current?.startProcessing(); setShowProgressHeader(true); }}
          >
            Start Processing
          </Button>
          <Button
            size="xs"
            variant="light"
            leftSection={showProgressHeader ? <IconEyeOff size={14} /> : <IconEye size={14} />}
            onClick={() => {
              fileUploadRef.current?.toggleProgress();
              setShowProgressHeader((prev) => !prev);
            }}
          >
            {showProgressHeader ? 'Hide' : 'Show'} Progress
          </Button>
          <Button
            size="xs"
            variant="light"
            leftSection={<IconRefresh size={14} />}
            onClick={async () => {
              if (projectId) {
                await fetchProject(projectId);
              }
              refreshStats();
            }}
          >
            Refresh
          </Button>
          <Button
            size="xs"
            variant="light"
            color="red"
            leftSection={<IconTrash size={14} />}
            onClick={handleDeleteProject}
          >
            Delete
          </Button>
        </Group>
      </Group>

      {/* Tabbed Interface */}
      <Tabs value={activeTab} onChange={(value) => value && setActiveTab(value)}>
        <Tabs.List style={{ flexWrap: 'nowrap', overflowX: 'auto' }}>
          <Tabs.Tab value="overview" leftSection={<IconFolder size={14} />} style={{ fontSize: '13px', padding: '8px 12px', minWidth: 'auto' }}>
            Overview
          </Tabs.Tab>
          <Tabs.Tab value="assessment" leftSection={<IconUpload size={14} />} style={{ fontSize: '13px', padding: '8px 12px', minWidth: 'auto' }}>
            Processing
          </Tabs.Tab>
          <Tabs.Tab value="files" leftSection={<IconFile size={14} />} style={{ fontSize: '13px', padding: '8px 12px', minWidth: 'auto' }}>
            Files
          </Tabs.Tab>
          <Tabs.Tab value="discovery" leftSection={<IconGraph size={14} />} style={{ fontSize: '13px', padding: '8px 12px', minWidth: 'auto' }}>
            Graph
          </Tabs.Tab>
          <Tabs.Tab value="agents" leftSection={<IconRobot size={14} />} style={{ fontSize: '13px', padding: '8px 12px', minWidth: 'auto' }}>
            Agents
          </Tabs.Tab>
          <Tabs.Tab value="templates" leftSection={<IconTemplate size={14} />} style={{ fontSize: '13px', padding: '8px 12px', minWidth: 'auto' }}>
            Templates
          </Tabs.Tab>
          <Tabs.Tab value="llm-config" leftSection={<IconSettings size={14} />} style={{ fontSize: '13px', padding: '8px 12px', minWidth: 'auto' }}>
            LLM
          </Tabs.Tab>
          <Tabs.Tab value="history" leftSection={<IconHistory size={14} />} style={{ fontSize: '13px', padding: '8px 12px', minWidth: 'auto' }}>
            History
          </Tabs.Tab>
          <Tabs.Tab value="knowledge" leftSection={<IconBrain size={14} />} style={{ fontSize: '13px', padding: '8px 12px', minWidth: 'auto' }}>
            Knowledge
          </Tabs.Tab>
        </Tabs.List>

  {/* Progress panel moved into FileUpload (above Uploaded Files) */}

        {/* Overview Tab - migrated to new Overview page component */}
        <Tabs.Panel value="overview" pt="xs">
          <ProjectOverviewPage />
        </Tabs.Panel>

        {/* Assessment Tab */}
        <Tabs.Panel value="assessment" pt="md">
          <FileUpload ref={fileUploadRef} projectId={project.id} onFilesUploaded={fetchProjectStats} />
        </Tabs.Panel>

        {/* Files Browser Tab */}
        <Tabs.Panel value="files" pt="md">
          <MinIODirectoryBrowser projectId={project.id} />
        </Tabs.Panel>

        {/* Interactive Discovery Tab */}
        <Tabs.Panel value="discovery" pt="md">
          <Tabs value={discoveryTab} onChange={(value) => setDiscoveryTab(value || 'knowledge-graph')} orientation="horizontal">
            <Tabs.List>
              <Tabs.Tab value="knowledge-graph">Knowledge Graph</Tabs.Tab>
              <Tabs.Tab value="infrastructure">Infrastructure Relationships</Tabs.Tab>
              <Tabs.Tab value="interactive">Interactive Graph (New)</Tabs.Tab>
            </Tabs.List>

            <Tabs.Panel value="knowledge-graph" pt="md">
              <Grid>
                <Grid.Col span={12} mb="md">
                  <GraphVisualizer projectId={project.id} />
                </Grid.Col>
                <Grid.Col span={12}>
                  <ChatInterface projectId={project.id} />
                </Grid.Col>
              </Grid>
            </Tabs.Panel>

            <Tabs.Panel value="infrastructure" pt="md">
              <Grid>
                <Grid.Col span={12} mb="md">
                  <GraphVisualizer projectId={project.id} viewType="infrastructure" />
                </Grid.Col>
                <Grid.Col span={12}>
                  <ChatInterface projectId={project.id} />
                </Grid.Col>
              </Grid>
            </Tabs.Panel>

            <Tabs.Panel value="interactive" pt="md">
              <Grid>
                <Grid.Col span={12} mb="md">
                  <InteractiveGraphVisualizer projectId={project.id} />
                </Grid.Col>
                <Grid.Col span={12}>
                  <ChatInterface projectId={project.id} />
                </Grid.Col>
              </Grid>
            </Tabs.Panel>
          </Tabs>
        </Tabs.Panel>

        {/* Crew/Agent/Tool Interaction Tab */}
        <Tabs.Panel value="agents" pt="md">
          <CrewInteractionViewer
            projectId={project.id}
          />
        </Tabs.Panel>

        {/* Document Templates Tab */}
        <Tabs.Panel value="templates" pt="md">
          <DocumentTemplates
            projectId={project.id}
            onNavigateToCrewInteraction={() => setActiveTab('agents')}
          />
        </Tabs.Panel>

        {/* LLM Configuration Tab */}
        <Tabs.Panel value="llm-config" pt="md">
          <ProcessLLMConfiguration
            projectId={project.id}
            project={project}
          />
        </Tabs.Panel>

        {/* History Tab */}
        <Tabs.Panel value="history" pt="md">
          <ProjectHistory projectId={project.id} />
        </Tabs.Panel>

        {/* Knowledge Tab - Stage 1 & 2: Facts & Insights */}
        <Tabs.Panel value="knowledge" pt="md">
          <KnowledgeTab projectId={project.id} />
        </Tabs.Panel>
      </Tabs>

  {/* Floating Chat Widget */}
      <FloatingChatWidget projectId={project.id} />

  {/* LLM Configuration Modal */}
      <Modal
        opened={llmConfigModalOpen}
        onClose={() => setLlmConfigModalOpen(false)}
        title="Change LLM Configuration"
        size="md"
      >
        <Stack gap="md">
          <Text size="sm" c="dimmed">
            Select a different LLM configuration for this project. The LLM will be tested immediately after selection.
          </Text>

          <Select
            label="LLM Configuration"
            placeholder={llmConfigs.length === 0 ? "Loading configurations..." : "Select an LLM configuration"}
            value={selectedLlmConfig || ''}
            onChange={(value) => setSelectedLlmConfig((value as string) || '')}
            data={Array.isArray(llmConfigs)
              ? llmConfigs
                  .filter((config: any) => config && (config.id != null) && config.name)
                  .map((config: any) => ({
                    value: String(config.id),
                    label: `${String(config.name)} (${config.provider || 'unknown'}/${config.model || 'unknown'}) - ${config.status === 'configured' ? 'Ready' : 'Needs API Key'}`
                  }))
              : []}
            searchable
            disabled={llmConfigs.length === 0}
            rightSection={llmConfigs.length === 0 ? <Loader size="xs" /> : undefined}
          />

          {selectedLlmConfig && (
            <Paper p="sm" withBorder radius="md" style={{ backgroundColor: '#f8f9fa' }}>
              {(() => {
                const selectedConfig = llmConfigs.find(c => c && c.id?.toString() === selectedLlmConfig);
                return selectedConfig ? (
                  <div>
                    <Text size="sm" fw={600} mb="xs">Selected Configuration:</Text>
                    <Group gap="xs" mb="xs">
                      <Text size="sm" c="dimmed">Name:</Text>
                      <Text size="sm">{selectedConfig.name}</Text>
                    </Group>
                    <Group gap="xs" mb="xs">
                      <Text size="sm" c="dimmed">Provider:</Text>
                      <Text size="sm">{selectedConfig.provider}</Text>
                    </Group>
                    <Group gap="xs">
                      <Text size="sm" c="dimmed">Model:</Text>
                      <Text size="sm">{selectedConfig.model}</Text>
                    </Group>
                  </div>
                ) : null;
              })()}
            </Paper>
          )}

          {/* Test Results Display */}
          {testResult && (
            <Paper p="md" withBorder radius="md" style={{
              backgroundColor: testResult.status === 'success' ? '#e8f5e8' : '#ffe8e8',
              marginLeft: '0px' // Fix left cutoff
            }}>
              <Stack gap="sm">
                <Group gap="xs">
                  <Text size="sm" fw={600}>
                    Test Result for {selectedConfigName}:
                  </Text>
                  <Badge color={testResult.status === 'success' ? 'green' : 'red'}>
                    {testResult.status === 'success' ? 'Success' : 'Failed'}
                  </Badge>
                </Group>

                <div>
                  <Text size="xs" c="dimmed" mb="xs">Query sent to LLM:</Text>
                  <Paper p="xs" style={{ backgroundColor: '#f0f0f0', fontFamily: 'monospace', fontSize: '12px' }}>
                    {testQuery}
                  </Paper>
                </div>

                <div>
                  <Text size="xs" c="dimmed" mb="xs">
                    {testResult.status === 'success' ? 'Response received:' : 'Error message:'}
                  </Text>
                  <Paper p="xs" style={{
                    backgroundColor: testResult.status === 'success' ? '#e8f5e8' : '#ffe8e8',
                    fontFamily: 'monospace',
                    fontSize: '12px',
                    marginLeft: '0px' // Fix left cutoff
                  }}>
                    {testResult.status === 'success'
                      ? (typeof testResult.response === 'string' ? testResult.response : JSON.stringify(testResult.response, null, 2))
                      : (typeof testResult.message === 'string' ? testResult.message : JSON.stringify(testResult.message, null, 2))}
                  </Paper>
                </div>

                {testResult.status === 'success' && (
                  <Text size="xs" c="green" fw={500}>
                    ✅ LLM configuration is working correctly. Project will be updated.
                  </Text>
                )}

                {testResult.status === 'error' && (
                  <Text size="xs" c="red" fw={500}>
                    ❌ LLM configuration failed. Project will not be updated.
                  </Text>
                )}
              </Stack>
            </Paper>
          )}

          <Group justify="flex-end" gap="sm">
            <Button
              variant="subtle"
              onClick={() => setLlmConfigModalOpen(false)}
            >
              Cancel
            </Button>
            <Button
              onClick={() => testSelectedLLMConfig()}
              disabled={!selectedLlmConfig}
              loading={testingLLM}
              variant="outline"
              color="blue"
            >
              {testingLLM ? 'Testing...' : 'Test LLM'}
            </Button>
            <Button
              onClick={saveProjectLLM}
              disabled={!selectedLlmConfig}
            >
              Save LLM Configuration
            </Button>
          </Group>
        </Stack>
      </Modal>
    </div>
  );
};
