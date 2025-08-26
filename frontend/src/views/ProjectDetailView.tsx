/**
 * Project Detail View - Multi-tabbed workspace for individual projects
 */

import React, { useState, useEffect } from 'react';
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
} from '@tabler/icons-react';
import { useParams, useNavigate } from 'react-router-dom';
import { notifications } from '@mantine/notifications';
// import ReactMarkdown from 'react-markdown';
// import remarkGfm from 'remark-gfm';
// import rehypeHighlight from 'rehype-highlight';
import { useProject } from '../hooks/useProjects';
import { GraphVisualizer } from '../components/project-detail/GraphVisualizer';
import { ChatInterface } from '../components/project-detail/ChatInterface';
import AgentActivityLog from '../components/project-detail/AgentActivityLog';
import ProjectHistory from '../components/project-detail/ProjectHistory';
import DocumentTemplates from '../components/project-detail/DocumentTemplates';
import CrewInteractionViewer from '../components/project-detail/CrewInteractionViewer';
import FloatingChatWidget from '../components/FloatingChatWidget';
import FileUpload from '../components/FileUpload';
import ProcessLLMConfiguration from '../components/ProcessLLMConfiguration';
import ProcessingProgressView from '../components/ProcessingProgressView';
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

  // Use WebSocket-based project stats
  const { stats: wsProjectStats, loading: statsLoading, error: statsError, lastEvent, refreshStats } = useProjectStats(projectId || '');

  // Convert WebSocket stats to legacy format for compatibility
  const projectStats = {
    fileCount: wsProjectStats?.files_count || 0,
    embeddings: wsProjectStats?.embeddings_count || 0,
    graphNodes: wsProjectStats?.graph_nodes || 0,
    agentInteractions: 0, // This would need to be added to WebSocket stats
    deliverables: 0 // This would need to be added to WebSocket stats
  };
  const [llmConfigModalOpen, setLlmConfigModalOpen] = useState(false);
  const [llmConfigs, setLlmConfigs] = useState<any[]>([]);
  const [selectedLlmConfig, setSelectedLlmConfig] = useState('');
  const [testingLLM, setTestingLLM] = useState(false);
  const [testResult, setTestResult] = useState<any>(null);
  const [testQuery, setTestQuery] = useState('');
  const [selectedConfigName, setSelectedConfigName] = useState('');
  // Project Brief (description / RFP / timeline)
  const [showProjectBrief, setShowProjectBrief] = useState<boolean>(true);
  const [isEditingBrief, setIsEditingBrief] = useState<boolean>(false);
  const [briefDescription, setBriefDescription] = useState<string>('');
  const [briefRfp, setBriefRfp] = useState<string>('');
  const [briefTimeline, setBriefTimeline] = useState<string>('');
  
  // Processing Progress View state
  const [showProcessingProgress, setShowProcessingProgress] = useState(false);

  // Assessment state management from context
  const { assessmentState } = useAssessment();

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
  };

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
  <div>
      {/* Project Header - Compact Layout */}
      <Card shadow="sm" p="md" radius="md" withBorder mb="xs" style={{ width: 'calc(100% - 8px)', marginRight: 8 }}>
        {/* Line 1: Project Name, Client, Files, Created, Last Updated, Edit Icon */}
        <Group justify="space-between" align="center" mb="sm">
          <Group gap="lg" align="center">
            <Text size="xl" fw={700} c="dark">{project.name}</Text>
            <Text size="sm" fw={500} c="dimmed">
              Client: {project.client_name} ({project.client_contact})
            </Text>
            <Text size="xs" c="dimmed">
              Files: {projectStats?.fileCount || 0}
            </Text>
            <Text size="xs" c="dimmed">
              Created: {new Date(project.created_at).toLocaleDateString()}
            </Text>
            <Text size="xs" c="dimmed">
              Updated: {new Date(project.updated_at).toLocaleDateString()}
            </Text>
            <Badge color={getStatusColor(project.status)} variant="light" size="sm">
              {project.status}
            </Badge>
          </Group>
          <ActionIcon
            size="sm"
            variant="subtle"
            onClick={() => setIsEditingBrief(!isEditingBrief)}
          >
            <IconEdit size={16} />
          </ActionIcon>
        </Group>

        {/* Line 2: LLM Configuration with Change/Test buttons on the right */}
        <Group justify="space-between" align="center" mb={showProjectBrief ? "sm" : 0}>
          <Group gap="sm" align="center">
            <IconRobot size={16} color="#495057" />
            <Text size="sm" fw={600}>LLM Configuration:</Text>
            {project?.llm_provider ? (
              (() => {
                const config = llmConfigs.find(c => c.id === project.llm_api_key_id);
                const configExists = !!config;
                return (
                  <Group gap="xs">
                    <Text size="sm" fw={600} c={configExists ? "dark" : "red.6"}>
                      {configExists ? config.name : "Missing"}
                    </Text>
                    <Badge color={configExists ? "green" : "red"} variant="light" size="xs">
                      {configExists ? "OK" : "ERR"}
                    </Badge>
                  </Group>
                );
              })()
            ) : (
              <Group gap="xs">
                <Text size="sm" fw={600} c="dimmed">Not Configured</Text>
                <Badge color="orange" variant="light" size="xs">Setup Required</Badge>
              </Group>
            )}
          </Group>
          <Group gap="xs">
            <Button
              size="xs"
              variant="light"
              onClick={() => setLlmConfigModalOpen(true)}
            >
              Change
            </Button>
            <Button
              size="xs"
              variant="outline"
              loading={testingLLM}
              onClick={testProjectLLM}
              disabled={!project?.llm_provider}
            >
              {testingLLM ? 'Testing...' : 'Test'}
            </Button>
          </Group>
        </Group>

        {/* Collapsible Project Details */}
        <Collapse in={showProjectBrief}>
          {/* Line 3: Project Description, RFP Details, Timeline (reduced height) */}
          {!isEditingBrief ? (
            <Grid gutter="lg">
              <Grid.Col span={6}>
                <div style={{ padding: '8px', backgroundColor: '#f8f9fa', borderRadius: '6px', border: '1px solid #e9ecef', minHeight: '40px' }}>
                  <Text size="xs" c="dimmed" fw={700} tt="uppercase" mb={4} style={{ letterSpacing: '0.5px' }}>Project Description</Text>
                  <Text size="sm" style={{ whiteSpace: 'pre-wrap', lineHeight: 1.3, color: '#495057' }}>
                    {project.description || 'No description provided'}
                  </Text>
                </div>
              </Grid.Col>
              <Grid.Col span={3}>
                <div style={{ padding: '8px', backgroundColor: '#f8f9fa', borderRadius: '6px', border: '1px solid #e9ecef', minHeight: '40px' }}>
                  <Text size="xs" c="dimmed" fw={700} tt="uppercase" mb={4} style={{ letterSpacing: '0.5px' }}>RFP Details</Text>
                  <Text size="sm" style={{ whiteSpace: 'pre-wrap', lineHeight: 1.3, color: '#495057' }}>
                    {(project as any).rfp_summary || (project as any).rfp || 'No RFP details provided'}
                  </Text>
                </div>
              </Grid.Col>
              <Grid.Col span={3}>
                <div style={{ padding: '8px', backgroundColor: '#f8f9fa', borderRadius: '6px', border: '1px solid #e9ecef', minHeight: '40px' }}>
                  <Text size="xs" c="dimmed" fw={700} tt="uppercase" mb={4} style={{ letterSpacing: '0.5px' }}>Timeline</Text>
                  <Text size="sm" style={{ whiteSpace: 'pre-wrap', lineHeight: 1.3, color: '#495057' }}>
                    {(project as any).timeline_notes || (project as any).timeline || 'No timeline specified'}
                  </Text>
                </div>
              </Grid.Col>
            </Grid>
          ) : (
            <Stack gap="xs">
              <Grid gutter="xs">
                <Grid.Col span={6}>
                  <Textarea
                    label="Client Name"
                    value={project.client_name}
                    onChange={(e) => {
                      // Update local state - you'll need to add this to component state
                      // For now, we'll handle this in the save function
                    }}
                    autosize
                    minRows={1}
                    size="xs"
                  />
                </Grid.Col>
                <Grid.Col span={6}>
                  <Textarea
                    label="Client Contact"
                    value={project.client_contact || ''}
                    onChange={(e) => {
                      // Update local state
                    }}
                    autosize
                    minRows={1}
                    size="xs"
                  />
                </Grid.Col>
              </Grid>
              <Textarea
                label="Project Description"
                autosize
                minRows={2}
                value={briefDescription}
                onChange={(e) => setBriefDescription(e.currentTarget.value)}
                size="xs"
              />
              <Grid gutter="xs">
                <Grid.Col span={6}>
                  <Textarea
                    label="RFP Details"
                    autosize
                    minRows={2}
                    value={briefRfp}
                    onChange={(e) => setBriefRfp(e.currentTarget.value)}
                    size="xs"
                  />
                </Grid.Col>
                <Grid.Col span={6}>
                  <Textarea
                    label="Timeline Details"
                    autosize
                    minRows={2}
                    value={briefTimeline}
                    onChange={(e) => setBriefTimeline(e.currentTarget.value)}
                    size="xs"
                  />
                </Grid.Col>
              </Grid>
              <Group justify="flex-end" gap="xs">
                <Button
                  size="xs"
                  variant="light"
                  color="gray"
                  onClick={() => {
                    setIsEditingBrief(false);
                    setBriefDescription(project.description || '');
                    setBriefRfp((project as any).rfp_summary || (project as any).rfp || '');
                    setBriefTimeline((project as any).timeline_notes || (project as any).timeline || '');
                  }}
                >
                  Cancel
                </Button>
                <Button
                  size="xs"
                  onClick={async () => {
                    try {
                      await apiService.updateProject(project.id, {
                        description: briefDescription,
                        rfp: briefRfp,
                        timeline: briefTimeline,
                      } as any);
                      notifications.show({
                      title: 'Project Updated',
                      message: 'Project details have been saved successfully',
                      color: 'green',
                    });
                    setIsEditingBrief(false);
                    if (projectId) await fetchProject(projectId);
                  } catch (e) {
                    notifications.show({
                      title: 'Save Failed',
                      message: 'Could not update project details',
                      color: 'red',
                    });
                  }
                }}
              >
                Save Changes
              </Button>
              </Group>
            </Stack>
          )}
        </Collapse>

        {/* Toggle button for project details */}
        <Group justify="center" mt="xs">
          <Button
            size="xs"
            variant="subtle"
            onClick={() => setShowProjectBrief(!showProjectBrief)}
          >
            {showProjectBrief ? 'Hide Details' : 'Show Details'}
          </Button>
        </Group>
      </Card>

      {/* Tabbed Interface */}
      <Tabs value={activeTab} onChange={(value) => value && setActiveTab(value)}>
        <Tabs.List>
          <Tabs.Tab value="overview" leftSection={<IconFolder size={16} />}>
            Overview
          </Tabs.Tab>
          <Tabs.Tab value="assessment" leftSection={<IconUpload size={16} />}>
            Processing
          </Tabs.Tab>
          <Tabs.Tab value="discovery" leftSection={<IconGraph size={16} />}>
            Interactive Graph
          </Tabs.Tab>
          <Tabs.Tab value="agents" leftSection={<IconRobot size={16} />}>
            Crew/Agent/Tool Interaction
          </Tabs.Tab>
          <Tabs.Tab value="templates" leftSection={<IconTemplate size={16} />}>
            Exported Documents
          </Tabs.Tab>
          <Tabs.Tab value="llm-config" leftSection={<IconSettings size={16} />}>
            LLM Configuration
          </Tabs.Tab>
          <Tabs.Tab value="report" leftSection={<IconFileText size={16} />}>
            Final Report
          </Tabs.Tab>
          <Tabs.Tab value="history" leftSection={<IconHistory size={16} />}>
            History
          </Tabs.Tab>
        </Tabs.List>

        {/* Persistent Assessment Progress Section */}
        {(assessmentState.isRunning || assessmentState.status === 'running' || project.status === 'running') && (
          <Card shadow="sm" p="xs" radius="md" withBorder mt="xs" style={{
            backgroundColor: assessmentState.status === 'failed' ? '#fff5f5' : '#f8f9fa',
            borderColor: assessmentState.status === 'failed' ? '#e53e3e' : '#e9ecef'
          }}>
            <Group justify="space-between" mb="xs">
              <Group gap="xs">
                {assessmentState.status === 'running' ? (
                  <Loader size="xs" />
                ) : assessmentState.status === 'failed' ? (
                  <IconAlertCircle size={14} color="red" />
                ) : (
                  <IconCheck size={14} color="green" />
                )}
                <Text size="xs" fw={600} c={assessmentState.status === 'failed' ? 'red' : assessmentState.status === 'completed' ? 'green' : 'blue'}>
                  {assessmentState.status === 'running' ? 'Assessment in Progress' :
                   assessmentState.status === 'failed' ? 'Assessment Failed' :
                   assessmentState.status === 'completed' ? 'Assessment Completed' : 'Assessment Status'}
                </Text>
                {assessmentState.startTime && (
                  <Text size="xs" c="dimmed">
                    Started: {assessmentState.startTime.toLocaleTimeString()}
                  </Text>
                )}
              </Group>
              <Badge
                color={assessmentState.status === 'failed' ? 'red' : assessmentState.status === 'completed' ? 'green' : 'blue'}
                variant="light"
                size="xs"
              >
                {assessmentState.status.toUpperCase()}
              </Badge>
            </Group>
            {assessmentState.logs.length > 0 && (
              <div>
                <Text size="xs" fw={500} mb="xs">Recent Activity:</Text>
                <div style={{ maxHeight: '60px', overflowY: 'auto', fontSize: '11px', fontFamily: 'monospace' }}>
                  {assessmentState.logs.slice(-3).map((log: string, index: number) => (
                    <div key={index} style={{ marginBottom: '1px' }}>
                      {log}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </Card>
        )}

        {/* Overview Tab */}
        <Tabs.Panel value="overview" pt="xs">
          <Grid>
            <Grid.Col span={9}>
              <Card shadow="sm" p="sm" radius="md" withBorder>
                <Group justify="space-between" mb="xs">
                  <Text size="md" fw={600}>
                    Project Status
                  </Text>
                  <Group gap="xs">
                    <Button
                      variant="light"
                      size="xs"
                      leftSection={<IconRefresh size={12} />}
                      onClick={fetchProjectStats}
                      loading={false}
                    >
                      Refresh
                    </Button>
                    <Button
                      variant={showProcessingProgress ? "filled" : "outline"}
                      size="xs" 
                      leftSection={<IconClock size={12} />}
                      onClick={() => setShowProcessingProgress(!showProcessingProgress)}
                    >
                      {showProcessingProgress ? "Hide" : "Show"} Progress
                    </Button>
                    <Badge
                      color={getStatusColor(project.status)}
                      variant="filled"
                      size="sm"
                    >
                      {project.status.toUpperCase()}
                    </Badge>
                  </Group>
                </Group>

                {/* WebSocket Connection Status - Only show errors */}
                {statsError && (
                  <Alert icon={<IconWifiOff size={14} />} color="red" variant="light" p="xs">
                    <Group justify="space-between">
                      <Text size="xs">Real-time stats connection failed: {statsError}</Text>
                      <Text size="xs">Offline</Text>
                    </Group>
                  </Alert>
                )}

                {/* High-Level Project Metrics */}
                <Grid gutter="xs">
                  <Grid.Col span={6}>
                    <Paper p="xs" withBorder radius="md" style={{ backgroundColor: '#f8f9fa' }}>
                      <Group gap="xs" justify="space-between" align="center">
                        <Group gap="xs">
                          <IconFile size={14} color="#495057" />
                          <Text size="xs" fw={600} c="dark.6">Documents</Text>
                        </Group>
                        <Text size="md" fw={700} c="blue.6">{projectStats.fileCount}</Text>
                      </Group>
                    </Paper>
                  </Grid.Col>

                  <Grid.Col span={6}>
                    <Paper p="xs" withBorder radius="md" style={{ backgroundColor: '#f8f9fa' }}>
                      <Group gap="xs" justify="space-between" align="center">
                        <Group gap="xs">
                          <IconDatabase size={14} color="#495057" />
                          <Text size="xs" fw={600} c="dark.6">Embeddings</Text>
                        </Group>
                        <Text size="md" fw={700} c="green.6">{projectStats.embeddings.toLocaleString()}</Text>
                      </Group>
                    </Paper>
                  </Grid.Col>

                  <Grid.Col span={6}>
                    <Paper p="xs" withBorder radius="md" style={{ backgroundColor: '#f8f9fa' }}>
                      <Group gap="xs" justify="space-between" align="center">
                        <Group gap="xs">
                          <IconGraph size={14} color="#495057" />
                          <Text size="xs" fw={600} c="dark.6">Knowledge Graph</Text>
                        </Group>
                        <Text size="md" fw={700} c="purple.6">{projectStats.graphNodes.toLocaleString()}</Text>
                      </Group>
                    </Paper>
                  </Grid.Col>

                  <Grid.Col span={6}>
                    <Paper p="xs" withBorder radius="md" style={{ backgroundColor: '#f8f9fa' }}>
                      <Group gap="xs" justify="space-between" align="center">
                        <Group gap="xs">
                          <IconRobot size={14} color="#495057" />
                          <Text size="xs" fw={600} c="dark.6">Agent Interactions</Text>
                        </Group>
                        <Text size="md" fw={700} c="orange.6">{projectStats.agentInteractions.toLocaleString()}</Text>
                      </Group>
                    </Paper>
                  </Grid.Col>

                  <Grid.Col span={6}>
                    <Paper p="xs" withBorder radius="md" style={{ backgroundColor: '#f8f9fa' }}>
                      <Group gap="xs" justify="space-between" align="center">
                        <Group gap="xs">
                          <IconFileText size={14} color="#495057" />
                          <Text size="xs" fw={600} c="dark.6">Deliverables</Text>
                        </Group>
                        <Text size="md" fw={700} c="red.6">{projectStats.deliverables}</Text>
                      </Group>
                    </Paper>
                  </Grid.Col>

                  <Grid.Col span={6}>
                    <Paper p="xs" withBorder radius="md" style={{ backgroundColor: '#f8f9fa' }}>
                      <Group gap="xs" justify="space-between" align="center">
                        <Group gap="xs">
                          <IconClock size={16} color="#495057" />
                          <Text size="sm" fw={600} c="dark.6">Last Updated</Text>
                        </Group>
                        <Text size="sm" fw={600} c="dark.7">{new Date(project.updated_at).toLocaleDateString()}</Text>
                      </Group>
                    </Paper>
                  </Grid.Col>
                </Grid>



                {/* LLM Test Results Display */}
                {testResult && (
                  <Paper p="md" withBorder radius="md" mt="md" style={{
                    backgroundColor: testResult.status === 'success' ? '#e8f5e8' : '#ffe8e8',
                    marginLeft: '0px', // Fix left cutoff
                    paddingLeft: '16px' // Ensure proper padding
                  }}>
                    <Stack gap="sm">
                      <Group gap="xs">
                        <Text size="sm" fw={600}>
                          LLM Test Result:
                        </Text>
                        <Badge color={testResult.status === 'success' ? 'green' : 'red'}>
                          {testResult.status === 'success' ? 'Success' : 'Failed'}
                        </Badge>
                      </Group>

                      <div style={{ marginLeft: '0px' }}>
                        <Text size="xs" c="dimmed" mb="xs">Query sent to LLM:</Text>
                        <Paper p="xs" style={{
                          backgroundColor: '#f0f0f0',
                          fontFamily: 'monospace',
                          fontSize: '12px',
                          marginLeft: '0px'
                        }}>
                          {testQuery}
                        </Paper>
                      </div>

                      <div style={{ marginLeft: '0px' }}>
                        <Text size="xs" c="dimmed" mb="xs">
                          {testResult.status === 'success' ? 'Response received:' : 'Error message:'}
                        </Text>
                        <Paper p="xs" style={{
                          backgroundColor: testResult.status === 'success' ? '#e8f5e8' : '#ffe8e8',
                          fontFamily: 'monospace',
                          fontSize: '12px',
                          marginLeft: '0px', // Fix left cutoff
                          paddingLeft: '12px' // Ensure proper padding
                        }}>
                          {testResult.status === 'success'
                            ? (typeof testResult.response === 'string' ? testResult.response : JSON.stringify(testResult.response, null, 2))
                            : (typeof testResult.message === 'string' ? testResult.message : JSON.stringify(testResult.message, null, 2))}
                        </Paper>
                      </div>

                      {testResult.status === 'success' && (
                        <Text size="xs" c="green" fw={500} style={{ marginLeft: '0px' }}>
                          ✅ LLM configuration is working correctly.
                        </Text>
                      )}

                      {testResult.status === 'error' && (
                        <Text size="xs" c="red" fw={500} style={{ marginLeft: '0px' }}>
                          ❌ LLM configuration failed. Please check your API key and configuration.
                        </Text>
                      )}
                    </Stack>
                  </Paper>
                )}

                {/* Status Alert */}
                {project.status === 'initiated' && (
                  <Alert color="blue" mt="md">
                    <Text size="sm">
                      Ready for file upload and assessment. Go to "File Management & Assessment" to get started.
                    </Text>
                  </Alert>
                )}

                {project.status === 'running' && (
                  <Alert color="yellow" mt="md">
                    <Text size="sm">
                      Assessment in progress. Monitor progress in "File Management & Assessment" tab.
                    </Text>
                  </Alert>
                )}

                {project.status === 'completed' && (
                  <Alert color="green" mt="md">
                    <Text size="sm">
                      Assessment completed! View results in "Final Report" and explore "Interactive Graph".
                    </Text>
                  </Alert>
                )}
              </Card>
            </Grid.Col>

            <Grid.Col span={3}>
              <Card shadow="sm" p="lg" radius="md" withBorder>
                <Text size="lg" fw={600} mb="md">
                  Quick Actions
                </Text>
                <div>
                  <Button
                    fullWidth
                    mb="md"
                    leftSection={<IconUpload size={16} />}
                    onClick={() => setActiveTab('assessment')}
                  >
                    Upload Files
                  </Button>
                  <Button
                    fullWidth
                    mb="md"
                    variant="light"
                    leftSection={<IconGraph size={16} />}
                    onClick={() => setActiveTab('discovery')}
                    disabled={project.status !== 'completed'}
                  >
                    View Infrastructure Graph
                  </Button>
                  <Button
                    fullWidth
                    variant="light"
                    leftSection={<IconFileText size={16} />}
                    onClick={() => setActiveTab('report')}
                    disabled={project.status !== 'completed'}
                  >
                    View Report
                  </Button>
                </div>
              </Card>
            </Grid.Col>
          </Grid>
          
          {/* Processing Progress View */}
          <ProcessingProgressView
            projectId={project.id}
            isVisible={showProcessingProgress}
            onToggleVisibility={() => setShowProcessingProgress(!showProcessingProgress)}
          />
        </Tabs.Panel>

        {/* Assessment Tab */}
        <Tabs.Panel value="assessment" pt="md">
          <FileUpload projectId={project.id} onFilesUploaded={fetchProjectStats} />
        </Tabs.Panel>

        {/* Interactive Discovery Tab */}
        <Tabs.Panel value="discovery" pt="md">
          <Tabs value={discoveryTab} onChange={(value) => setDiscoveryTab(value || 'knowledge-graph')} orientation="horizontal">
            <Tabs.List>
              <Tabs.Tab value="knowledge-graph">Knowledge Graph</Tabs.Tab>
              <Tabs.Tab value="infrastructure">Infrastructure Relationships</Tabs.Tab>
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

        {/* Final Report Tab */}
        <Tabs.Panel value="report" pt="md">
          <Card shadow="sm" p="lg" radius="md" withBorder>
            <Group justify="space-between" mb="md">
              <Text size="lg" fw={600}>
                Assessment Report
              </Text>
              <Group gap="md">
                {project.report_url && (
                  <Button
                    variant="light"
                    leftSection={<IconDownload size={16} />}
                    onClick={() => window.open(project.report_url, '_blank')}
                  >
                    Download DOCX
                  </Button>
                )}
                {project.report_artifact_url && (
                  <Button
                    variant="light"
                    color="red"
                    leftSection={<IconDownload size={16} />}
                    onClick={() => window.open(project.report_artifact_url, '_blank')}
                  >
                    Download PDF
                  </Button>
                )}
                <ActionIcon variant="subtle" onClick={fetchReportContent}>
                  <IconRefresh size={16} />
                </ActionIcon>
              </Group>
            </Group>

            <Divider mb="md" />

            {reportLoading ? (
              <Group justify="center" p="xl">
                <Loader size="lg" />
                <Text>Loading report content...</Text>
              </Group>
            ) : (
              <Paper p="md" style={{ backgroundColor: '#f8f9fa' }}>
                <Text style={{ whiteSpace: 'pre-wrap', fontFamily: 'monospace', fontSize: '14px', lineHeight: 1.6 }}>
                  {reportContent || 'No report content available. Complete an assessment to generate the report.'}
                </Text>
              </Paper>
            )}
          </Card>
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
