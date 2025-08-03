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
import { apiService } from '../services/api';
import { useAssessment } from '../contexts/AssessmentContext';

export const ProjectDetailView: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const { project, loading, error } = useProject(projectId || null);
  const [activeTab, setActiveTab] = useState<string>('overview');
  const [reportContent, setReportContent] = useState<string>('');
  const [reportLoading, setReportLoading] = useState(false);
  const [projectStats, setProjectStats] = useState({
    fileCount: 0,
    embeddings: 0,
    graphNodes: 0,
    agentInteractions: 0,
    deliverables: 0
  });
  const [llmConfigModalOpen, setLlmConfigModalOpen] = useState(false);
  const [llmConfigs, setLlmConfigs] = useState<any[]>([]);
  const [selectedLlmConfig, setSelectedLlmConfig] = useState('');
  const [testingLLM, setTestingLLM] = useState(false);
  const [testResult, setTestResult] = useState<any>(null);
  const [testQuery, setTestQuery] = useState('');
  const [selectedConfigName, setSelectedConfigName] = useState('');

  // Assessment state management from context
  const { assessmentState } = useAssessment();

  // Load LLM configurations
  const loadLLMConfigurations = async () => {
    try {
      const response = await fetch('http://localhost:8000/llm-configurations');
      if (response.ok) {
        const configs = await response.json();
        setLlmConfigs(configs);
        // Set current project's LLM config as selected
        if (project?.llm_api_key_id) {
          setSelectedLlmConfig(project.llm_api_key_id);
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
      const testQuery = "Hello, please respond with 'LLM test successful' to confirm connectivity.";
      setTestQuery(testQuery);

      // Use the same endpoint as Settings and Project creation
      const response = await fetch('http://localhost:8000/api/test-llm-config', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          config_id: project.llm_api_key_id,
          provider: project.llm_provider,
          model: project.llm_model,
          api_key: 'from_config', // Will be retrieved from stored config
          temperature: parseFloat(project.llm_temperature || '0.1'),
          max_tokens: parseInt(project.llm_max_tokens || '100')
        }),
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
        query: testQuery,
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
      const testQuery = "Hello, please respond with 'LLM test successful' to confirm connectivity.";
      setTestQuery(testQuery);

      // Use the same endpoint as other test buttons
      const response = await fetch('http://localhost:8000/api/test-llm-config', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          config_id: selectedLlmConfig,
          provider: llmConfigs.find(c => c.id === selectedLlmConfig)?.provider,
          model: llmConfigs.find(c => c.id === selectedLlmConfig)?.model,
          api_key: 'from_config',
          temperature: 0.1,
          max_tokens: 100
        }),
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
      const selectedConfig = llmConfigs.find(c => c.id === selectedLlmConfig);
      if (!selectedConfig) return;

      setSelectedConfigName(selectedConfig.name);

      // Update the project with selected LLM configuration
      const updateResponse = await fetch(`http://localhost:8000/projects/${projectId}`, {
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
        window.location.reload();
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
    loadLLMConfigurations();
  }, [project]);

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

  const fetchProjectStats = async () => {
    if (!projectId) return;

    try {
      // Fetch actual project statistics
      const response = await apiService.getProjectFiles(projectId);

      // Get enhanced project stats from backend
      const statsResponse = await fetch(`http://localhost:8000/api/projects/${projectId}/stats`);
      const stats = statsResponse.ok ? await statsResponse.json() : {};

      setProjectStats({
        fileCount: response.length || 0,
        embeddings: stats.embeddings || 0,
        graphNodes: stats.graph_nodes || 0,
        agentInteractions: stats.agent_interactions || 0,
        deliverables: stats.deliverables || 0
      });
    } catch (err) {
      console.error('Failed to fetch project stats:', err);
    }
  };

  React.useEffect(() => {
    if (activeTab === 'report' && projectId) {
      fetchReportContent();
    }
  }, [activeTab, projectId]);

  React.useEffect(() => {
    if (projectId) {
      fetchProjectStats();
    }
  }, [projectId]);

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
      {/* Project Header */}
      <Card shadow="sm" p="md" radius="md" withBorder mb="xs">
        {/* Project Details - All in one line */}
        <Group justify="space-between" align="center" mb="md" style={{ flexWrap: 'nowrap' }}>
          {/* Left side - Project name, status, client, dates */}
          <Group gap="xl" align="center" style={{ flex: 1, flexWrap: 'nowrap' }}>
            {/* Project Name and Status */}
            <Group gap="md" align="center" style={{ minWidth: '250px' }}>
              <Text size="xl" fw={700}>
                {project.name}
              </Text>
              <Badge
                color={getStatusColor(project.status)}
                variant="light"
                size="lg"
              >
                {project.status}
              </Badge>
            </Group>

            {/* Client */}
            <Group gap="xs" align="center" style={{ minWidth: '180px' }}>
              <IconUser size={16} color="#495057" />
              <div>
                <Text size="xs" c="dimmed" fw={500}>CLIENT</Text>
                <Text size="sm" fw={600}>{project.client_name}</Text>
                {project.client_contact && (
                  <Text size="xs" c="dimmed">{project.client_contact}</Text>
                )}
              </div>
            </Group>

            {/* Created Date */}
            <Group gap="xs" align="center" style={{ minWidth: '120px' }}>
              <IconCalendar size={16} color="#495057" />
              <div>
                <Text size="xs" c="dimmed" fw={500}>CREATED</Text>
                <Text size="sm" fw={600}>{new Date(project.created_at).toLocaleDateString()}</Text>
              </div>
            </Group>

            {/* Updated Date */}
            <Group gap="xs" align="center" style={{ minWidth: '120px' }}>
              <IconClock size={16} color="#495057" />
              <div>
                <Text size="xs" c="dimmed" fw={500}>UPDATED</Text>
                <Text size="sm" fw={600}>{new Date(project.updated_at).toLocaleDateString()}</Text>
              </div>
            </Group>

            {/* Description (if exists and not a test description) */}
            {project.description &&
             project.description !== 'Testing all fixes' &&
             project.description !== 'Testing correct stats calculation' &&
             project.description !== 'End-to-end testing of LLM workflow' &&
             project.description !== 'Testing with fresh LLM config' &&
             project.description.trim() !== '' && (
              <Group gap="xs" align="center" style={{ minWidth: '200px', flex: 1 }}>
                <IconFileText size={16} color="#495057" />
                <div>
                  <Text size="xs" c="dimmed" fw={500}>DESCRIPTION</Text>
                  <Text size="sm" fw={600} style={{ maxWidth: '300px' }} truncate>
                    {project.description}
                  </Text>
                </div>
              </Group>
            )}
          </Group>

          {/* Right side - Report download buttons */}
          <Group gap="md">
            {project.report_url && (
              <Button
                variant="light"
                leftSection={<IconDownload size={16} />}
                onClick={() => window.open(project.report_url, '_blank')}
              >
                Final Report (DOCX)
              </Button>
            )}
            {project.report_artifact_url && (
              <Button
                variant="light"
                color="red"
                leftSection={<IconDownload size={16} />}
                onClick={() => window.open(project.report_artifact_url, '_blank')}
              >
                Final Report (PDF)
              </Button>
            )}
          </Group>
        </Group>

      </Card>

      {/* LLM Configuration Section - Compact version above tabs */}
      <Card shadow="sm" p="sm" radius="md" withBorder mb="sm">
        <Group justify="space-between" align="center" mb="xs">
          <Text size="md" fw={600}>LLM Configuration</Text>
          <Group gap="xs">
            <Button
              size="xs"
              variant="light"
              leftSection={<IconRobot size={14} />}
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

        <Paper p="sm" withBorder radius="md" style={{ backgroundColor: '#f8f9fa' }}>
          {project?.llm_provider ? (
            (() => {
              const config = llmConfigs.find(c => c.id === project.llm_api_key_id);
              const configExists = !!config;

              return (
                <Group justify="space-between" align="center">
                  <Group gap="sm">
                    <IconRobot size={20} color={configExists ? "#495057" : "#fa5252"} />
                    <div>
                      <Text size="sm" fw={600} c={configExists ? "dark.7" : "red.6"}>
                        {configExists ? config.name : "Configuration Deleted"}
                      </Text>
                      <Text size="xs" c="dimmed">
                        {project.llm_provider?.toUpperCase()} / {project.llm_model}
                        {configExists ? " • Active Configuration" : " • Configuration Missing"}
                      </Text>
                    </div>
                  </Group>
                  <Badge
                    color={configExists ? "green" : "red"}
                    variant="light"
                    size="sm"
                  >
                    {configExists ? "Configured" : "Missing"}
                  </Badge>
                </Group>
              );
            })()
          ) : (
            <Group justify="space-between" align="center">
              <Group gap="sm">
                <IconRobot size={20} color="#868e96" />
                <div>
                  <Text size="sm" fw={600} c="dimmed">
                    No Default LLM Configuration Selected
                  </Text>
                  <Text size="xs" c="dimmed">
                    Configure LLM to enable AI features
                  </Text>
                </div>
              </Group>
              <Badge color="orange" variant="light" size="sm">
                Not Configured
              </Badge>
            </Group>
          )}
        </Paper>

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
                  {testResult.status === 'success' ? testResult.response : testResult.message}
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
      </Card>

      {/* Tabbed Interface */}
      <Tabs value={activeTab} onChange={(value) => value && setActiveTab(value)}>
        <Tabs.List>
          <Tabs.Tab value="overview" leftSection={<IconFolder size={16} />}>
            Overview
          </Tabs.Tab>
          <Tabs.Tab value="assessment" leftSection={<IconUpload size={16} />}>
            Process & Assess Documents
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
          <Tabs.Tab value="report" leftSection={<IconFileText size={16} />}>
            Final Report
          </Tabs.Tab>
          <Tabs.Tab value="history" leftSection={<IconHistory size={16} />}>
            History
          </Tabs.Tab>
        </Tabs.List>

        {/* Persistent Assessment Progress Section */}
        {(assessmentState.isRunning || assessmentState.status === 'running' || project.status === 'running') && (
          <Card shadow="sm" p="sm" radius="md" withBorder mt="sm" style={{
            backgroundColor: assessmentState.status === 'failed' ? '#fff5f5' : '#f8f9fa',
            borderColor: assessmentState.status === 'failed' ? '#e53e3e' : '#e9ecef'
          }}>
            <Group justify="space-between" mb="xs">
              <Group gap="sm">
                {assessmentState.status === 'running' ? (
                  <Loader size="sm" />
                ) : assessmentState.status === 'failed' ? (
                  <IconAlertCircle size={16} color="red" />
                ) : (
                  <IconCheck size={16} color="green" />
                )}
                <Text fw={600} c={assessmentState.status === 'failed' ? 'red' : assessmentState.status === 'completed' ? 'green' : 'blue'}>
                  {assessmentState.status === 'running' ? 'Assessment in Progress' :
                   assessmentState.status === 'failed' ? 'Assessment Failed' :
                   assessmentState.status === 'completed' ? 'Assessment Completed' : 'Assessment Status'}
                </Text>
                {assessmentState.startTime && (
                  <Text size="sm" c="dimmed">
                    Started: {assessmentState.startTime.toLocaleTimeString()}
                  </Text>
                )}
              </Group>
              <Badge
                color={assessmentState.status === 'failed' ? 'red' : assessmentState.status === 'completed' ? 'green' : 'blue'}
                variant="light"
              >
                {assessmentState.status.toUpperCase()}
              </Badge>
            </Group>
            {assessmentState.logs.length > 0 && (
              <div>
                <Text size="sm" fw={500} mb="xs">Recent Activity:</Text>
                <div style={{ maxHeight: '80px', overflowY: 'auto', fontSize: '12px', fontFamily: 'monospace' }}>
                  {assessmentState.logs.slice(-5).map((log: string, index: number) => (
                    <div key={index} style={{ marginBottom: '2px' }}>
                      {log}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </Card>
        )}

        {/* Overview Tab */}
        <Tabs.Panel value="overview" pt="md">
          <Grid>
            <Grid.Col span={9}>
              <Card shadow="sm" p="lg" radius="md" withBorder>
                <Group justify="space-between" mb="md">
                  <Text size="lg" fw={600}>
                    Project Status
                  </Text>
                  <Group gap="md">
                    <Button
                      variant="light"
                      size="xs"
                      leftSection={<IconRefresh size={14} />}
                      onClick={fetchProjectStats}
                      loading={false}
                    >
                      Refresh Stats
                    </Button>
                    <Badge
                      color={getStatusColor(project.status)}
                      variant="filled"
                      size="lg"
                    >
                      {project.status.toUpperCase()}
                    </Badge>
                  </Group>
                </Group>

                {/* High-Level Project Metrics */}
                <Grid gutter="md">
                  <Grid.Col span={6}>
                    <Paper p="sm" withBorder radius="md" style={{ backgroundColor: '#f8f9fa' }}>
                      <Group gap="xs" justify="space-between" align="center">
                        <Group gap="xs">
                          <IconFile size={16} color="#495057" />
                          <Text size="sm" fw={600} c="dark.6">Documents</Text>
                        </Group>
                        <Text size="lg" fw={700} c="blue.6">{projectStats.fileCount}</Text>
                      </Group>
                    </Paper>
                  </Grid.Col>

                  <Grid.Col span={6}>
                    <Paper p="sm" withBorder radius="md" style={{ backgroundColor: '#f8f9fa' }}>
                      <Group gap="xs" justify="space-between" align="center">
                        <Group gap="xs">
                          <IconDatabase size={16} color="#495057" />
                          <Text size="sm" fw={600} c="dark.6">Embeddings</Text>
                        </Group>
                        <Text size="lg" fw={700} c="green.6">{projectStats.embeddings.toLocaleString()}</Text>
                      </Group>
                    </Paper>
                  </Grid.Col>

                  <Grid.Col span={6}>
                    <Paper p="sm" withBorder radius="md" style={{ backgroundColor: '#f8f9fa' }}>
                      <Group gap="xs" justify="space-between" align="center">
                        <Group gap="xs">
                          <IconGraph size={16} color="#495057" />
                          <Text size="sm" fw={600} c="dark.6">Knowledge Graph</Text>
                        </Group>
                        <Text size="lg" fw={700} c="purple.6">{projectStats.graphNodes.toLocaleString()}</Text>
                      </Group>
                    </Paper>
                  </Grid.Col>

                  <Grid.Col span={6}>
                    <Paper p="sm" withBorder radius="md" style={{ backgroundColor: '#f8f9fa' }}>
                      <Group gap="xs" justify="space-between" align="center">
                        <Group gap="xs">
                          <IconRobot size={16} color="#495057" />
                          <Text size="sm" fw={600} c="dark.6">Agent Interactions</Text>
                        </Group>
                        <Text size="lg" fw={700} c="orange.6">{projectStats.agentInteractions.toLocaleString()}</Text>
                      </Group>
                    </Paper>
                  </Grid.Col>

                  <Grid.Col span={6}>
                    <Paper p="sm" withBorder radius="md" style={{ backgroundColor: '#f8f9fa' }}>
                      <Group gap="xs" justify="space-between" align="center">
                        <Group gap="xs">
                          <IconFileText size={16} color="#495057" />
                          <Text size="sm" fw={600} c="dark.6">Deliverables</Text>
                        </Group>
                        <Text size="lg" fw={700} c="red.6">{projectStats.deliverables}</Text>
                      </Group>
                    </Paper>
                  </Grid.Col>

                  <Grid.Col span={6}>
                    <Paper p="sm" withBorder radius="md" style={{ backgroundColor: '#f8f9fa' }}>
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
                          {testResult.status === 'success' ? testResult.response : testResult.message}
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
        </Tabs.Panel>

        {/* Assessment Tab */}
        <Tabs.Panel value="assessment" pt="md">
          <FileUpload projectId={project.id} onFilesUploaded={fetchProjectStats} />
        </Tabs.Panel>

        {/* Interactive Discovery Tab */}
        <Tabs.Panel value="discovery" pt="md">
          <Grid>
            <Grid.Col span={12} mb="md">
              <GraphVisualizer projectId={project.id} />
            </Grid.Col>
            <Grid.Col span={12}>
              <ChatInterface projectId={project.id} />
            </Grid.Col>
          </Grid>
        </Tabs.Panel>

        {/* Crew/Agent/Tool Interaction Tab */}
        <Tabs.Panel value="agents" pt="md">
          <CrewInteractionViewer
            projectId={project.id}
          />
        </Tabs.Panel>

        {/* Document Templates Tab */}
        <Tabs.Panel value="templates" pt="md">
          <DocumentTemplates projectId={project.id} />
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
            value={selectedLlmConfig}
            onChange={(value) => setSelectedLlmConfig(value || '')}
            data={llmConfigs.map(config => ({
              value: config.id,
              label: `${config.name} (${config.provider}/${config.model}) - ${config.status === 'configured' ? 'Ready' : 'Needs API Key'}`
            }))}
            searchable
            disabled={llmConfigs.length === 0}
            rightSection={llmConfigs.length === 0 ? <Loader size="xs" /> : undefined}
          />

          {selectedLlmConfig && (
            <Paper p="sm" withBorder radius="md" style={{ backgroundColor: '#f8f9fa' }}>
              {(() => {
                const selectedConfig = llmConfigs.find(c => c.id === selectedLlmConfig);
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
                    {testResult.status === 'success' ? testResult.response : testResult.message}
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
