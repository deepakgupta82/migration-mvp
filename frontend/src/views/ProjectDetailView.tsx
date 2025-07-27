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
} from '@tabler/icons-react';
import { useParams, useNavigate } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import { useProject } from '../hooks/useProjects';
import { GraphVisualizer } from '../components/project-detail/GraphVisualizer';
import { ChatInterface } from '../components/project-detail/ChatInterface';
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
      <Card shadow="sm" p="lg" radius="md" withBorder mb="xl">
        <Group justify="space-between" align="flex-start">
          <div style={{ flex: 1 }}>
            <Group gap="md" mb="md">
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

            <Text c="dimmed" mb="md">
              {project.description}
            </Text>

            <Grid>
              <Grid.Col span={6}>
                <Group gap="xs" mb="xs">
                  <IconUser size={16} color="#868e96" />
                  <Text size="sm" fw={500}>Client:</Text>
                  <Text size="sm">{project.client_name}</Text>
                </Group>
                {project.client_contact && (
                  <Group gap="xs" mb="xs">
                    <Text size="sm" c="dimmed" ml={24}>
                      {project.client_contact}
                    </Text>
                  </Group>
                )}
              </Grid.Col>
              <Grid.Col span={6}>
                <Group gap="xs" mb="xs">
                  <IconCalendar size={16} color="#868e96" />
                  <Text size="sm" fw={500}>Created:</Text>
                  <Text size="sm">{new Date(project.created_at).toLocaleDateString()}</Text>
                </Group>
                <Group gap="xs" mb="xs">
                  <Text size="sm" fw={500} ml={24}>Last Updated:</Text>
                  <Text size="sm">{new Date(project.updated_at).toLocaleDateString()}</Text>
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
          <Tabs.Tab value="report" leftSection={<IconFileText size={16} />}>
            Final Report
          </Tabs.Tab>
        </Tabs.List>

        {/* Overview Tab */}
        <Tabs.Panel value="overview" pt="xl">
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
        <Tabs.Panel value="assessment" pt="xl">
          <FileUpload projectId={project.id} />
        </Tabs.Panel>

        {/* Interactive Discovery Tab */}
        <Tabs.Panel value="discovery" pt="xl">
          <Grid>
            <Grid.Col span={12} mb="md">
              <GraphVisualizer projectId={project.id} />
            </Grid.Col>
            <Grid.Col span={12}>
              <ChatInterface projectId={project.id} />
            </Grid.Col>
          </Grid>
        </Tabs.Panel>

        {/* Final Report Tab */}
        <Tabs.Panel value="report" pt="xl">
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
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  rehypePlugins={[rehypeHighlight]}
                  components={{
                    h1: ({ children }) => (
                      <Text size="xl" fw={700} mb="md" c="dark">
                        {children}
                      </Text>
                    ),
                    h2: ({ children }) => (
                      <Text size="lg" fw={600} mb="md" c="dark" mt="xl">
                        {children}
                      </Text>
                    ),
                    h3: ({ children }) => (
                      <Text size="md" fw={600} mb="sm" c="dark" mt="lg">
                        {children}
                      </Text>
                    ),
                    p: ({ children }) => (
                      <Text mb="md" style={{ lineHeight: 1.6 }}>
                        {children}
                      </Text>
                    ),
                    img: ({ src, alt }) => (
                      <img
                        src={src}
                        alt={alt}
                        style={{
                          maxWidth: '100%',
                          height: 'auto',
                          margin: '16px 0',
                          borderRadius: '8px',
                          border: '1px solid #e9ecef',
                        }}
                      />
                    ),
                  }}
                >
                  {reportContent || 'No report content available. Complete an assessment to generate the report.'}
                </ReactMarkdown>
              </Paper>
            )}
          </Card>
        </Tabs.Panel>
      </Tabs>
    </div>
  );
};
