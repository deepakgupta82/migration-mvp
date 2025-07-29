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
            <Group gap="sm" mb="sm">
              <Text size="lg" fw={700}>
                {project.name}
              </Text>
              <Badge
                color={getStatusColor(project.status)}
                variant="light"
                size="md"
              >
                {project.status}
              </Badge>
            </Group>

            <Text c="dimmed" mb="sm" size="sm">
              {project.description}
            </Text>

            <Grid gutter="xs">
              <Grid.Col span={6}>
                <Group gap="xs" mb={4}>
                  <IconUser size={14} color="#868e96" />
                  <Text size="xs" fw={500}>Client:</Text>
                  <Text size="xs">{project.client_name}</Text>
                </Group>
                {project.client_contact && (
                  <Group gap="xs" mb={4}>
                    <Text size="xs" c="dimmed" ml={20}>
                      {project.client_contact}
                    </Text>
                  </Group>
                )}
              </Grid.Col>
              <Grid.Col span={6}>
                <Group gap="xs" mb={4}>
                  <IconCalendar size={14} color="#868e96" />
                  <Text size="xs" fw={500}>Created:</Text>
                  <Text size="xs">{new Date(project.created_at).toLocaleDateString()}</Text>
                </Group>
                <Group gap="xs" mb={4}>
                  <Text size="xs" fw={500} ml={20}>Last Updated:</Text>
                  <Text size="xs">{new Date(project.updated_at).toLocaleDateString()}</Text>
                </Group>
              </Grid.Col>
            </Grid>
          </div>

          <div>
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
            Interactive Discovery
          </Tabs.Tab>
          <Tabs.Tab value="agents" leftSection={<IconRobot size={16} />}>
            Agent Activity
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
            <Grid.Col span={8}>
              <Card shadow="sm" p="lg" radius="md" withBorder>
                <Text size="lg" fw={600} mb="md">
                  Project Status
                </Text>
                <div>
                  <Group gap="md" mb="md">
                    <Badge
                      color={getStatusColor(project.status)}
                      variant="filled"
                      size="lg"
                    >
                      {project.status.toUpperCase()}
                    </Badge>
                    <Text size="sm" c="dimmed">
                      Last updated: {new Date(project.updated_at).toLocaleString()}
                    </Text>
                  </Group>

                  {project.status === 'initiated' && (
                    <Alert color="blue" mb="md">
                      <Text size="sm">
                        This project is ready for file upload and assessment.
                        Go to the "File Management & Assessment" tab to get started.
                      </Text>
                    </Alert>
                  )}

                  {project.status === 'running' && (
                    <Alert color="yellow" mb="md">
                      <Text size="sm">
                        Assessment is currently in progress. You can monitor the progress
                        in the "File Management & Assessment" tab.
                      </Text>
                    </Alert>
                  )}

                  {project.status === 'completed' && (
                    <Alert color="green" mb="md">
                      <Text size="sm">
                        Assessment completed successfully! You can view the results in the
                        "Final Report" tab and explore insights in "Interactive Discovery".
                      </Text>
                    </Alert>
                  )}
                </div>
              </Card>
            </Grid.Col>

            <Grid.Col span={4}>
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
