/**
 * Project Detail View - Multi-tabbed workspace for individual projects
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Text,
  Group,
  Badge,
  Tabs,
  Button,
  Grid,
  Paper,
  Loader,
  Alert,
  Modal,
  Select,
  Stack,
  Menu,
  Divider,
} from '@mantine/core';
import {
  IconFolder,
  IconFile,
  IconUpload,
  IconGraph,
  IconMessageCircle,
  IconAlertCircle,
  IconRefresh,
  IconRobot,
  IconHistory,
  IconTemplate,
  IconDatabase,
  IconSettings,
  IconEye,
  IconEyeOff,
  IconTrash,
  IconBrain,
  IconSearch,
} from '@tabler/icons-react';
import { useParams, useNavigate } from 'react-router-dom';
import { useNotifications } from '../contexts/NotificationContext';
// import ReactMarkdown from 'react-markdown';
// import remarkGfm from 'remark-gfm';
// import rehypeHighlight from 'rehype-highlight';
import { useProject } from '../hooks/useProjects';
import { ProjectOverviewPage } from './project/ProjectOverviewPage';
import { GraphVisualizer } from '../components/project-detail/GraphVisualizer';
import InteractiveGraphVisualizer from '../components/project-detail/InteractiveGraphVisualizer';
import GraphViewSelector, { GraphViewType } from '../components/project-detail/GraphViewSelector';
import PlatformCentricGraph from '../components/project-detail/PlatformCentricGraph';
import DocumentSourceGraph from '../components/project-detail/DocumentSourceGraph';
import EnvironmentGraph from '../components/project-detail/EnvironmentGraph';
import { ChatInterface } from '../components/project-detail/ChatInterface';
import ProjectExplorerView from './project/ProjectExplorerView';
import ProjectCentralityView from './project/ProjectCentralityView';
import ProjectQueryConsoleView from './project/ProjectQueryConsoleView';
import { DiscussionsTab } from '../components/project-detail/DiscussionsTab';
import ProjectHistory from '../components/project-detail/ProjectHistory';
import DocumentTemplates from '../components/project-detail/DocumentTemplates';
import CrewInteractionViewer from '../components/project-detail/CrewInteractionViewer';
import FloatingChatWidget from '../components/FloatingChatWidget';
import FileUpload, { FileUploadHandle } from '../components/FileUpload';
import ProcessLLMConfiguration from '../components/ProcessLLMConfiguration';
import MinIODirectoryBrowser from '../components/MinIODirectoryBrowser';
import { KnowledgeTab } from '../components/project-detail/KnowledgeTab';
import { DocumentAnalysisDashboard } from '../components/project-detail/DocumentAnalysisDashboard';
import { DocumentSearchTab } from '../components/project-detail/DocumentSearchTab';
import { apiService } from '../services/api';
import { useProjectStats } from '../hooks/useStatsWebSocket';
import { useAssessment } from '../contexts/AssessmentContext';
import { LLMUsageTab } from '../pages/settings/LLMUsageTab';


export const ProjectDetailView: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const { project, loading, error, fetchProject } = useProject(projectId || null);
  const { addNotification } = useNotifications();
  const [activeTab, setActiveTab] = useState<string>('overview');
  const [discoveryTab, setDiscoveryTab] = useState<string>('knowledge-graph');
  const [graphViewType, setGraphViewType] = useState<GraphViewType>('knowledge-graph');
  // Compact state removed to avoid unused warnings in this view
  const fileUploadRef = useRef<FileUploadHandle | null>(null);
  const [showProgressHeader, setShowProgressHeader] = useState(false);

  // Use WebSocket-based project stats
  const { lastEvent, refreshStats } = useProjectStats(projectId || '');

  // Convert WebSocket stats to legacy format for compatibility
  const [llmConfigModalOpen, setLlmConfigModalOpen] = useState(false);
  const [llmConfigs, setLlmConfigs] = useState<any[]>([]);
  const [selectedLlmConfig, setSelectedLlmConfig] = useState('');
  const [testingLLM, setTestingLLM] = useState(false);
  const [testResult, setTestResult] = useState<any>(null);
  const [testQuery, setTestQuery] = useState('');
  const [selectedConfigName, setSelectedConfigName] = useState('');
  // Project Brief (description / RFP / timeline)
  // Reserved states removed to reduce unused warnings

  // Assessment state management from context
  const { assessmentState, startAssessment, setStatus, addLog, setProgress, stopAssessment } = useAssessment();

  // Load LLM configurations
  const loadLLMConfigurations = useCallback(async () => {
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
  }, [project]);

  // Test LLM configuration

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
        addNotification({
          title: 'LLM Test Successful',
          message: `${selectedConfigName} is working correctly. You can now save this configuration.`,
          type: 'success',
          projectId: projectId,
        });
      } else {
        addNotification({
          title: 'LLM Test Failed',
          message: result.message || 'Failed to connect to LLM. Check details below.',
          type: 'error',
          projectId: projectId,
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

      addNotification({
        title: 'LLM Test Error',
        message: 'Failed to test LLM configuration. Check details below.',
        type: 'error',
        projectId: projectId,
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
        addNotification({
          title: 'LLM Configuration Saved',
          message: `Project now uses ${selectedConfig.name}`,
          type: 'success',
          projectId: projectId,
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
      addNotification({
        title: 'Save Failed',
        message: 'Failed to save LLM configuration',
        type: 'error',
        projectId: projectId,
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
        addNotification({
          title: 'Project Deleted',
          message: 'Project has been successfully deleted',
          type: 'success',
          projectId: projectId,
        });

        // Navigate back to projects list
        navigate('/projects');
      } else {
        throw new Error('Failed to delete project');
      }
    } catch (error) {
      addNotification({
        title: 'Delete Failed',
        message: 'Failed to delete project. Please try again.',
        type: 'error',
        projectId: projectId,
      });
    }
  };

  // Load LLM configurations when component mounts and when modal opens
  useEffect(() => {
    if (project) {
      loadLLMConfigurations();
    }
  }, [project, loadLLMConfigurations]);

  // Set selected config when both project and configs are available
  useEffect(() => {
    if (project?.llm_api_key_id && llmConfigs.length > 0 && !selectedLlmConfig) {
      const configExists = llmConfigs.find(c => c && c.id?.toString() === project.llm_api_key_id?.toString());
      if (configExists) {
        setSelectedLlmConfig(project.llm_api_key_id.toString());
      }
    }
  }, [project?.llm_api_key_id, llmConfigs, selectedLlmConfig]);

  useEffect(() => {
    if (llmConfigModalOpen) {
      loadLLMConfigurations();
    }
  }, [llmConfigModalOpen, loadLLMConfigurations]);

  // getStatusColor removed (unused)

  const fetchReportContent = useCallback(async () => {
    if (!projectId) return;
    try {
      const response = await apiService.getProjectReport(projectId);
      // delegate display elsewhere; avoid unused state in this view
      console.debug('Report content size:', response?.report_content?.length || 0);
    } catch (err) {
      console.warn('Report content not available yet');
    }
  }, [projectId]);

  // Legacy function for compatibility - now just refreshes WebSocket stats
  const fetchProjectStats = () => {
    refreshStats();
    if (projectId) {
      // Kick off assessment UI flow when files uploaded
      if (!assessmentState.isRunning && assessmentState.status !== 'running') {
        startAssessment(projectId);
        addNotification({ title: 'Processing started', message: 'Document processing initiated', type: 'info', projectId: projectId });
      }
    }
  };

  // Guard against processing same event repeatedly causing state churn
  const processedEventRef = useRef<string | null>(null);
  useEffect(() => {
    if (!lastEvent) return;
    const evtRaw = String(lastEvent);
    // Skip duplicate events
    if (processedEventRef.current === evtRaw) return;
    processedEventRef.current = evtRaw;

    const evt = evtRaw.toLowerCase();
    const log = (m: string) => addLog(m);

    if (evt.includes('started')) {
      setStatus('running');
      log('Processing started');
      setProgress(5);
      return; // early exit to reduce multiple updates per tick
    }
    if (evt.includes('chunk') || evt.includes('ingest')) {
      log('Chunking completed');
      setProgress(30);
      return;
    }
    if (evt.includes('embedding')) {
      log('Embeddings updated');
      setProgress(60);
      return;
    }
    if (evt.includes('graph')) {
      log('Graph updated');
      setProgress(90);
      return;
    }
    if (evt.includes('complete') || evt.includes('done')) {
      setProgress(100);
      setStatus('completed');
      log('Processing completed');
      addNotification({ title: 'Processing complete', message: 'All steps finished successfully', type: 'success', projectId: projectId });
      stopAssessment();
      return;
    }
    if (evt.includes('fail') || evt.includes('error')) {
      setStatus('failed');
      log('Processing failed');
      addNotification({ title: 'Processing failed', message: 'Check logs for details', type: 'error', projectId: projectId });
      return;
    }
  }, [lastEvent, setStatus, addLog, setProgress, stopAssessment]);

  React.useEffect(() => {
    if (activeTab === 'report' && projectId) {
      fetchReportContent();
    }
  }, [activeTab, projectId, fetchReportContent]);

  // No longer need manual stats fetching - WebSocket handles it automatically
  
  // Clear Data Dropdown Handlers
  const [clearingAction, setClearingAction] = useState<string | null>(null);

  const withConfirm = async (message: string, action: () => Promise<void>) => {
    const ok = window.confirm(message);
    if (!ok) return;
    await action();
  };

  const handleClearEmbeddings = async () => {
    if (!projectId) return;
    setClearingAction('embeddings');
    try {
      await apiService.clearProjectEmbeddings(projectId);
      addNotification({ title: 'Embeddings cleared', message: 'Removed all embeddings for this project.', type: 'success', projectId: projectId });
      refreshStats();
    } catch (e: any) {
      addNotification({ title: 'Failed to clear embeddings', message: e?.message || String(e), type: 'error', projectId: projectId });
    } finally {
      setClearingAction(null);
    }
  };

  const handleClearGraph = async () => {
    if (!projectId) return;
    setClearingAction('graph');
    try {
      await apiService.clearProjectGraph(projectId);
      addNotification({ title: 'Knowledge graph cleared', message: 'Removed all nodes and relationships.', type: 'success', projectId: projectId });
      refreshStats();
    } catch (e: any) {
      addNotification({ title: 'Failed to clear graph', message: e?.message || String(e), type: 'error', projectId: projectId });
    } finally {
      setClearingAction(null);
    }
  };

  const handleCleanupStructured = async () => {
    if (!projectId) return;
    setClearingAction('structured');
    try {
      await apiService.cleanupStorageCategory(projectId, 'structured');
      addNotification({ title: 'Structured cleanup started', message: 'Structured files cleanup is running in background.', type: 'info', projectId: projectId });
    } catch (e: any) {
      addNotification({ title: 'Failed to cleanup structured', message: e?.message || String(e), type: 'error', projectId: projectId });
    } finally {
      setClearingAction(null);
    }
  };

  const handleCleanupProcessed = async () => {
    if (!projectId) return;
    setClearingAction('processed');
    try {
      await apiService.cleanupStorageCategory(projectId, 'uploads_parsed');
      await apiService.cleanupStorageCategory(projectId, 'uploads_canonical');
      addNotification({ title: 'Processed cleanup started', message: 'Parsed and canonical cleanup running in background.', type: 'info', projectId: projectId });
    } catch (e: any) {
      addNotification({ title: 'Failed to cleanup processed', message: e?.message || String(e), type: 'error', projectId: projectId });
    } finally {
      setClearingAction(null);
    }
  };

  const handleClearAllDerived = async () => {
    if (!projectId) return;
    setClearingAction('all');
    try {
      const res = await apiService.clearAllDerived(projectId);
      const errs = Array.isArray(res?.errors) ? res.errors : [];
      const hadErrors = errs.length > 0;
      addNotification({
        title: hadErrors ? 'Cleared with warnings' : 'All derived data cleared',
        message: hadErrors ? errs.join('; ') : 'Embeddings, graph, structured and processed files removed. Uploaded originals kept.',
        type: hadErrors ? 'warning' : 'success',
        projectId: projectId,
      });
      refreshStats();
    } catch (e: any) {
      addNotification({ title: 'Failed to clear all derived', message: e?.message || String(e), type: 'error', projectId: projectId });
    } finally {
      setClearingAction(null);
    }
  };

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
          {/* New Clear Data dropdown */}
          <Menu shadow="md" position="bottom-end" width={260}>
            <Menu.Target>
              <Button size="xs" variant="light" color="red" rightSection={<IconTrash size={14} />}
                disabled={!!clearingAction}
              >
                Clear Data
              </Button>
            </Menu.Target>
            <Menu.Dropdown>
              <Menu.Label>Derived data only</Menu.Label>
              <Menu.Item onClick={() => withConfirm('Clear ALL embeddings for this project?', handleClearEmbeddings)} disabled={!!clearingAction}>
                Clear Embeddings
              </Menu.Item>
              <Menu.Item onClick={() => withConfirm('Clear the entire knowledge graph for this project?', handleClearGraph)} disabled={!!clearingAction}>
                Clear Knowledge Graph
              </Menu.Item>
              <Divider />
              <Menu.Item onClick={() => withConfirm('Delete all Structured files (JSONL) for this project?', handleCleanupStructured)} disabled={!!clearingAction}>
                Delete Structured Files
              </Menu.Item>
              <Menu.Item onClick={() => withConfirm('Delete all Processed files (parsed + canonical) for this project?', handleCleanupProcessed)} disabled={!!clearingAction}>
                Delete Processed Files
              </Menu.Item>
              <Divider />
              <Menu.Item color="red" onClick={() => withConfirm('Clear ALL derived data (embeddings, graph, structured, processed)? Uploaded originals will be kept.', handleClearAllDerived)} disabled={!!clearingAction}>
                Clear All (Derived)
              </Menu.Item>
              <Menu.Divider />
              <Menu.Label>Note</Menu.Label>
              <Menu.Item disabled>
                Uploaded originals are preserved (uploads_raw).
              </Menu.Item>
            </Menu.Dropdown>
          </Menu>
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
          <Tabs.Tab value="knowledge" leftSection={<IconBrain size={14} />} style={{ fontSize: '13px', padding: '8px 12px', minWidth: 'auto' }}>
            Knowledge
          </Tabs.Tab>
          <Tabs.Tab value="document-analysis" leftSection={<IconDatabase size={14} />} style={{ fontSize: '13px', padding: '8px 12px', minWidth: 'auto' }}>
            Document Analysis
          </Tabs.Tab>
          <Tabs.Tab value="search" leftSection={<IconSearch size={14} />} style={{ fontSize: '13px', padding: '8px 12px', minWidth: 'auto' }}>
            Search
          </Tabs.Tab>
          <Tabs.Tab value="discussions" leftSection={<IconMessageCircle size={14} />} style={{ fontSize: '13px', padding: '8px 12px', minWidth: 'auto' }}>
            Discussions
          </Tabs.Tab>
          <Tabs.Tab value="history" leftSection={<IconHistory size={14} />} style={{ fontSize: '13px', padding: '8px 12px', minWidth: 'auto' }}>
            History
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

        {/* Interactive Discovery Tab with Multi-Viewpoint Graphs */}
        <Tabs.Panel value="discovery" pt="md">
          <Tabs value={discoveryTab} onChange={(value) => setDiscoveryTab(value || 'knowledge-graph')} orientation="horizontal">
            <Tabs.List>
              <Tabs.Tab value="multi-view">Multi-View Graphs (New)</Tabs.Tab>
              <Tabs.Tab value="knowledge-graph">Knowledge Graph</Tabs.Tab>
              <Tabs.Tab value="infrastructure">Infrastructure Relationships</Tabs.Tab>
              <Tabs.Tab value="interactive">Interactive Graph</Tabs.Tab>
              <Tabs.Tab value="explorer">Explorer</Tabs.Tab>
              <Tabs.Tab value="centrality">Centrality</Tabs.Tab>
              <Tabs.Tab value="query-console">Query Console</Tabs.Tab>
            </Tabs.List>

            {/* New Multi-Viewpoint Graph Tab */}
            <Tabs.Panel value="multi-view" pt="md">
              <Grid>
                <Grid.Col span={12} mb="md">
                  <GraphViewSelector
                    activeView={graphViewType}
                    onViewChange={setGraphViewType}
                    documentCount={0} // TODO: Fetch actual count
                    environmentCount={0} // TODO: Fetch actual count
                  />
                </Grid.Col>
                <Grid.Col span={12} mb="md">
                  {graphViewType === 'knowledge-graph' && <GraphVisualizer projectId={project.id} />}
                  {graphViewType === 'infrastructure' && <GraphVisualizer projectId={project.id} viewType="infrastructure" />}
                  {graphViewType === 'platform-centric' && <PlatformCentricGraph projectId={project.id} />}
                  {graphViewType === 'document-source' && <DocumentSourceGraph projectId={project.id} />}
                  {graphViewType === 'environment' && <EnvironmentGraph projectId={project.id} />}
                </Grid.Col>
                <Grid.Col span={12}>
                  <ChatInterface projectId={project.id} />
                </Grid.Col>
              </Grid>
            </Tabs.Panel>

            <Tabs.Panel value="knowledge-graph" pt="md">
              <Grid>
                <Grid.Col span={12} mb="md">
                  <GraphVisualizer projectId={project.id} />
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

            <Tabs.Panel value="explorer" pt="md">
              <ProjectExplorerView projectId={project.id} />
            </Tabs.Panel>

            <Tabs.Panel value="centrality" pt="md">
              <ProjectCentralityView projectId={project.id} />
            </Tabs.Panel>

            <Tabs.Panel value="query-console" pt="md">
              <ProjectQueryConsoleView projectId={project.id} />
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

        {/* LLM Configuration Tab - with subtabs for Config and Usage */}
        <Tabs.Panel value="llm-config" pt="md">
          <Tabs defaultValue="config" orientation="horizontal" variant="pills">
            <Tabs.List mb="md">
              <Tabs.Tab value="config" leftSection={<IconSettings size={16} />}>
                LLM Configuration
              </Tabs.Tab>
              <Tabs.Tab value="usage" leftSection={<IconDatabase size={16} />}>
                Usage & Analytics
              </Tabs.Tab>
            </Tabs.List>

            <Tabs.Panel value="config" pt="xs">
              <ProcessLLMConfiguration
                projectId={project.id}
                project={project}
              />
            </Tabs.Panel>

            <Tabs.Panel value="usage" pt="xs">
              <LLMUsageTab />
            </Tabs.Panel>
          </Tabs>
        </Tabs.Panel>

        {/* Knowledge Tab - Stage 1 & 2: Facts & Insights */}
        <Tabs.Panel value="knowledge" pt="md">
          <KnowledgeTab projectId={project.id} />
        </Tabs.Panel>

        {/* Document Analysis Dashboard Tab */}
        <Tabs.Panel value="document-analysis" pt="md">
          {activeTab === 'document-analysis' && (
            <DocumentAnalysisDashboard projectId={project.id} />
          )}
        </Tabs.Panel>

        {/* Document Search Tab */}
        <Tabs.Panel value="search" pt="md">
          <DocumentSearchTab projectId={project.id} />
        </Tabs.Panel>

        {/* Discussions Tab */}
        <Tabs.Panel value="discussions" pt="md">
          <DiscussionsTab projectId={project.id} />
        </Tabs.Panel>

        {/* History Tab */}
        <Tabs.Panel value="history" pt="md">
          <ProjectHistory projectId={project.id} />
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
