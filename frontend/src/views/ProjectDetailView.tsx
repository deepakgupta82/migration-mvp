/**
 * Project Detail View - Multi-tabbed workspace for individual projects
 */

import React, { useState } from 'react';
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
} from '@tabler/icons-react';
import { useParams, useNavigate } from 'react-router-dom';
// import ReactMarkdown from 'react-markdown';
// import remarkGfm from 'remark-gfm';
// import rehypeHighlight from 'rehype-highlight';
import { useProject } from '../hooks/useProjects';
import { GraphVisualizer } from '../components/project-detail/GraphVisualizer';
import { ChatInterface } from '../components/project-detail/ChatInterface';
import AgentActivityLog from '../components/project-detail/AgentActivityLog';
import ProjectHistory from '../components/project-detail/ProjectHistory';
import DocumentTemplates from '../components/project-detail/DocumentTemplates';
import FloatingChatWidget from '../components/FloatingChatWidget';
import FileUpload from '../components/FileUpload';
import { apiService } from '../services/api';

export const ProjectDetailView: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const { project, loading, error } = useProject(projectId || null);
  const [activeTab, setActiveTab] = useState<string>('overview');
  const [reportContent, setReportContent] = useState<string>('');
  const [reportLoading, setReportLoading] = useState(false);

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

  React.useEffect(() => {
    if (activeTab === 'report' && projectId) {
      fetchReportContent();
    }
  }, [activeTab, projectId]);

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
      <Card shadow="sm" p="md" radius="md" withBorder mb="md">
        <Group justify="space-between" align="flex-start">
          <div style={{ flex: 1 }}>
            <Group gap="md" mb="sm" wrap="wrap" align="center">
              <Text size="lg" fw={700}>
                {project.name}
              </Text>
              <Badge
                color={getStatusColor(project.status)}
                variant="light"
                size="sm"
              >
                {project.status}
              </Badge>
              <Text size="xs" c="dimmed">•</Text>
              <Group gap="xs">
                <IconUser size={12} color="#868e96" />
                <Text size="xs" fw={500}>Client:</Text>
                <Text size="xs">{project.client_name}</Text>
                {project.client_contact && (
                  <Text size="xs" c="dimmed">({project.client_contact})</Text>
                )}
              </Group>
              <Text size="xs" c="dimmed">•</Text>
              <Group gap="xs">
                <IconCalendar size={12} color="#868e96" />
                <Text size="xs" fw={500}>Created:</Text>
                <Text size="xs">{new Date(project.created_at).toLocaleDateString()}</Text>
              </Group>
              <Text size="xs" c="dimmed">•</Text>
              <Group gap="xs">
                <Text size="xs" fw={500}>Updated:</Text>
                <Text size="xs">{new Date(project.updated_at).toLocaleDateString()}</Text>
              </Group>
            </Group>
            <Text c="dimmed" size="sm" style={{ lineHeight: 1.3, marginTop: '4px' }}>
              {project.description}
            </Text>
          </div>

          <div>
            <Group gap="md">
              <Button
                variant="outline"
                leftSection={<IconTemplate size={16} />}
                onClick={() => setActiveTab('templates')}
              >
                Document Templates
              </Button>
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
          </div>
        </Group>
      </Card>

      {/* Tabbed Interface */}
      <Tabs value={activeTab} onChange={(value) => value && setActiveTab(value)}>
        <Tabs.List>
          <Tabs.Tab value="overview" leftSection={<IconFolder size={16} />}>
            Overview
          </Tabs.Tab>
          <Tabs.Tab value="assessment" leftSection={<IconUpload size={16} />}>
            File Management & Assessment
          </Tabs.Tab>
          <Tabs.Tab value="discovery" leftSection={<IconGraph size={16} />}>
            Interactive Graph
          </Tabs.Tab>
          <Tabs.Tab value="agents" leftSection={<IconRobot size={16} />}>
            Agent Activity
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

        {/* Overview Tab */}
        <Tabs.Panel value="overview" pt="md">
          <Grid>
            <Grid.Col span={9}>
              <Card shadow="sm" p="lg" radius="md" withBorder>
                <Group justify="space-between" mb="md">
                  <Text size="lg" fw={600}>
                    Project Status
                  </Text>
                  <Badge
                    color={getStatusColor(project.status)}
                    variant="filled"
                    size="lg"
                  >
                    {project.status.toUpperCase()}
                  </Badge>
                </Group>

                {/* High-Level Project Metrics */}
                <Grid gutter="md">
                  <Grid.Col span={6}>
                    <Paper p="md" withBorder radius="md" style={{ backgroundColor: '#f8f9fa' }}>
                      <Group gap="xs" mb="xs">
                        <IconFile size={16} color="#495057" />
                        <Text size="sm" fw={600} c="dark.6">Documents</Text>
                      </Group>
                      <Text size="xl" fw={700} c="blue.6">24</Text>
                      <Text size="xs" c="dimmed">Files uploaded</Text>
                    </Paper>
                  </Grid.Col>

                  <Grid.Col span={6}>
                    <Paper p="md" withBorder radius="md" style={{ backgroundColor: '#f8f9fa' }}>
                      <Group gap="xs" mb="xs">
                        <IconDatabase size={16} color="#495057" />
                        <Text size="sm" fw={600} c="dark.6">Embeddings</Text>
                      </Group>
                      <Text size="xl" fw={700} c="green.6">1,247</Text>
                      <Text size="xs" c="dimmed">Vector embeddings in Weaviate</Text>
                    </Paper>
                  </Grid.Col>

                  <Grid.Col span={6}>
                    <Paper p="md" withBorder radius="md" style={{ backgroundColor: '#f8f9fa' }}>
                      <Group gap="xs" mb="xs">
                        <IconGraph size={16} color="#495057" />
                        <Text size="sm" fw={600} c="dark.6">Knowledge Graph</Text>
                      </Group>
                      <Text size="xl" fw={700} c="purple.6">156</Text>
                      <Text size="xs" c="dimmed">Nodes & relationships in Neo4j</Text>
                    </Paper>
                  </Grid.Col>

                  <Grid.Col span={6}>
                    <Paper p="md" withBorder radius="md" style={{ backgroundColor: '#f8f9fa' }}>
                      <Group gap="xs" mb="xs">
                        <IconRobot size={16} color="#495057" />
                        <Text size="sm" fw={600} c="dark.6">Agent Interactions</Text>
                      </Group>
                      <Text size="xl" fw={700} c="orange.6">89</Text>
                      <Text size="xs" c="dimmed">AI agent processing sessions</Text>
                    </Paper>
                  </Grid.Col>

                  <Grid.Col span={6}>
                    <Paper p="md" withBorder radius="md" style={{ backgroundColor: '#f8f9fa' }}>
                      <Group gap="xs" mb="xs">
                        <IconFileText size={16} color="#495057" />
                        <Text size="sm" fw={600} c="dark.6">Deliverables</Text>
                      </Group>
                      <Text size="xl" fw={700} c="red.6">7</Text>
                      <Text size="xs" c="dimmed">Final documents created</Text>
                    </Paper>
                  </Grid.Col>

                  <Grid.Col span={6}>
                    <Paper p="md" withBorder radius="md" style={{ backgroundColor: '#f8f9fa' }}>
                      <Group gap="xs" mb="xs">
                        <IconClock size={16} color="#495057" />
                        <Text size="sm" fw={600} c="dark.6">Last Updated</Text>
                      </Group>
                      <Text size="sm" fw={600} c="dark.7">{new Date(project.updated_at).toLocaleDateString()}</Text>
                      <Text size="xs" c="dimmed">{new Date(project.updated_at).toLocaleTimeString()}</Text>
                    </Paper>
                  </Grid.Col>
                </Grid>

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
          <FileUpload projectId={project.id} />
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

        {/* Agent Activity Tab */}
        <Tabs.Panel value="agents" pt="md">
          <AgentActivityLog
            projectId={project.id}
            isAssessmentRunning={project.status === 'running'}
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
    </div>
  );
};
