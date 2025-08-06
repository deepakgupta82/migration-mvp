/**
 * Projects View - Professional project management interface inspired by Google AI Studio
 */

import React, { useState } from 'react';
import {
  Stack,
  Card,
  Text,
  Group,
  Table,
  Badge,
  ActionIcon,
  Button,
  Modal,
  TextInput,
  Textarea,
  Select,
  Loader,
  Center,
  ThemeIcon,
  Title,
  Pagination,
  Menu,
  rem,
} from '@mantine/core';
import {
  IconFolder,
  IconPlus,
  IconEye,
  IconEdit,
  IconTrash,
  IconDots,
  IconSearch,
  IconFilter,
  IconDownload,
  IconRefresh,
  IconPin,
  IconPinFilled,
} from '@tabler/icons-react';
import { useNavigate } from 'react-router-dom';
import { useProjects } from '../hooks/useProjects';
import { Project } from '../services/api';
import { notifications } from '@mantine/notifications';
import { useEffect } from 'react';

export const ProjectsView: React.FC = () => {
  const navigate = useNavigate();
  const { projects, loading, error, createProject, deleteProject, fetchProjects } = useProjects();

  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [newProject, setNewProject] = useState({
    name: '',
    description: '',
    client_name: '',
    client_contact: '',
    default_llm_config_id: '',
  });
  const [llmConfigs, setLlmConfigs] = useState<any[]>([]);
  const [testingLLM, setTestingLLM] = useState(false);
  const [testResult, setTestResult] = useState<any>(null);
  const [pinnedProjects, setPinnedProjects] = useState<Set<string>>(new Set());

  const itemsPerPage = 10;

  // Load pinned projects from localStorage
  useEffect(() => {
    const saved = localStorage.getItem('pinnedProjects');
    if (saved) {
      setPinnedProjects(new Set(JSON.parse(saved)));
    }
  }, []);

  // Save pinned projects to localStorage
  const savePinnedProjects = (pinned: Set<string>) => {
    localStorage.setItem('pinnedProjects', JSON.stringify(Array.from(pinned)));
  };

  // Toggle pin status
  const togglePin = (projectId: string) => {
    const newPinned = new Set(pinnedProjects);
    if (newPinned.has(projectId)) {
      newPinned.delete(projectId);
    } else {
      newPinned.add(projectId);
    }
    setPinnedProjects(newPinned);
    savePinnedProjects(newPinned);
  };

  // Filter and search projects, then sort by pinned status
  const filteredProjects = projects
    .filter((project) => {
      const matchesSearch = project.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                           project.client_name.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesStatus = !statusFilter || project.status === statusFilter;
      return matchesSearch && matchesStatus;
    })
    .sort((a, b) => {
      // Pinned projects first
      const aPinned = pinnedProjects.has(a.id);
      const bPinned = pinnedProjects.has(b.id);
      if (aPinned && !bPinned) return -1;
      if (!aPinned && bPinned) return 1;
      // Then by creation date (newest first)
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
    });

  // Paginate projects
  const totalPages = Math.ceil(filteredProjects.length / itemsPerPage);
  const paginatedProjects = filteredProjects.slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  );

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'green';
      case 'running': return 'blue';
      case 'initiated': return 'yellow';
      case 'failed': return 'red';
      default: return 'gray';
    }
  };

  const getStatusIcon = (status: string) => {
    return <IconFolder size={16} />;
  };

  // Load LLM configurations when modal opens
  useEffect(() => {
    if (createModalOpen) {
      loadLLMConfigurations();
    }
  }, [createModalOpen]);

  const loadLLMConfigurations = async () => {
    try {
      const response = await fetch('http://localhost:8000/llm-configurations');
      if (response.ok) {
        const configs = await response.json();
        setLlmConfigs(configs);
      }
    } catch (error) {
      console.error('Failed to load LLM configurations:', error);
    }
  };

  const testLLMConfiguration = async (configId: string, showInline: boolean = false) => {
    if (!configId) return false;

    setTestingLLM(true);
    if (showInline) {
      setTestResult(null);
    }

    try {
      const config = llmConfigs.find(c => c.id === configId);
      if (!config) {
        throw new Error('Configuration not found');
      }

      // Use the same endpoint as Settings page
      const response = await fetch('http://localhost:8000/api/test-llm-config', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          config_id: config.id,
          provider: config.provider,
          model: config.model,
          api_key: config.api_key,
          temperature: config.temperature || 0.1,
          max_tokens: 100
        }),
      });

      const result = await response.json();

      if (showInline) {
        // Store result for inline display
        setTestResult({
          ...result,
          timestamp: new Date().toLocaleTimeString(),
          query: "Hello, please respond with 'LLM test successful' to confirm connectivity.",
          configName: config.name || `${config.provider}/${config.model}`
        });
      }

      if (response.ok && result.status === 'success') {
        if (!showInline) {
          notifications.show({
            title: 'LLM Test Successful',
            message: `${config.name} is working correctly`,
            color: 'green',
          });
        }
        return true;
      } else {
        if (!showInline) {
          notifications.show({
            title: 'LLM Test Failed',
            message: result.message || 'Failed to connect to LLM',
            color: 'red',
          });
        }
        return false;
      }
    } catch (error) {
      if (showInline) {
        setTestResult({
          status: 'error',
          message: `Test failed: ${error}`,
          timestamp: new Date().toLocaleTimeString(),
          query: "Hello, please respond with 'LLM test successful' to confirm connectivity.",
          configName: 'Unknown'
        });
      } else {
        notifications.show({
          title: 'LLM Test Error',
          message: 'Failed to test LLM configuration',
          color: 'red',
        });
      }
      return false;
    } finally {
      setTestingLLM(false);
    }
  };

  const handleCreateProject = async () => {
    if (!newProject.default_llm_config_id) {
      notifications.show({
        title: 'LLM Configuration Required',
        message: 'Please select a default LLM configuration for this project',
        color: 'orange',
      });
      return;
    }

    try {
      await createProject(newProject);
      setCreateModalOpen(false);
      setNewProject({ name: '', description: '', client_name: '', client_contact: '', default_llm_config_id: '' });
      notifications.show({
        title: 'Success',
        message: 'Project created successfully with LLM configuration tested',
        color: 'green',
      });
    } catch (error) {
      notifications.show({
        title: 'Error',
        message: 'Failed to create project',
        color: 'red',
      });
    }
  };

  const handleRunAssessment = async (projectId: string) => {
    try {
      // Navigate to project detail page and trigger assessment
      navigate(`/projects/${projectId}`);

      // Show notification that assessment is starting
      notifications.show({
        title: 'Assessment Starting',
        message: 'Redirecting to project page to start assessment...',
        color: 'blue',
        icon: <IconRefresh size={16} />,
      });
    } catch (error) {
      notifications.show({
        title: 'Error',
        message: 'Failed to start assessment',
        color: 'red',
      });
    }
  };

  const handleDeleteProject = async (projectId: string) => {
    try {
      await deleteProject(projectId);
      notifications.show({
        title: 'Success',
        message: 'Project deleted successfully',
        color: 'green',
      });
    } catch (error) {
      console.error('Delete project error:', error);
      notifications.show({
        title: 'Error',
        message: error instanceof Error ? error.message : 'Failed to delete project',
        color: 'red',
      });
      // Refresh projects to ensure UI is in sync with backend
      fetchProjects();
    }
  };

  if (error && projects.length === 0) {
    return (
      <Center py={60}>
        <Stack gap="lg" align="center">
          <ThemeIcon size={64} radius="md" variant="light" color="red">
            <IconFolder size={32} />
          </ThemeIcon>
          <Stack gap={4} align="center">
            <Text size="lg" fw={600} c="red">
              Failed to load projects
            </Text>
            <Text size="sm" c="dimmed" style={{ textAlign: 'center', maxWidth: 300 }}>
              There was an error loading your projects. Please try refreshing the page.
            </Text>
          </Stack>
          <Button
            size="md"
            radius="md"
            onClick={() => {
              fetchProjects();
            }}
          >
            Try Again
          </Button>
        </Stack>
      </Center>
    );
  }

  return (
    <Stack gap="xl">
      {/* Professional Header Section */}
      <Card p="xl" radius="lg">
        <Group justify="space-between" mb="lg">
          <Stack gap={4}>
            <Title order={2} fw={600} c="dark.8">
              Project Management
            </Title>
            <Text size="sm" c="dimmed" fw={500}>
              Manage your cloud migration assessment projects
            </Text>
          </Stack>
          <Button
            size="md"
            radius="md"
            leftSection={<IconPlus size={16} />}
            onClick={() => setCreateModalOpen(true)}
          >
            Create New Project
          </Button>
        </Group>

        {/* Search and Filter Controls */}
        <Group gap="md">
          <TextInput
            placeholder="Search projects..."
            leftSection={<IconSearch size={16} />}
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.currentTarget.value)}
            style={{ flex: 1 }}
            radius="md"
          />
          <Select
            placeholder="Filter by status"
            leftSection={<IconFilter size={16} />}
            data={[
              { value: '', label: 'All Statuses' },
              { value: 'initiated', label: 'Initiated' },
              { value: 'running', label: 'Running' },
              { value: 'completed', label: 'Completed' },
              { value: 'failed', label: 'Failed' },
            ]}
            value={statusFilter}
            onChange={setStatusFilter}
            clearable
            radius="md"
            w={200}
          />
        </Group>
      </Card>

      {/* Professional Projects Table */}
      <Card p="xl" radius="lg">
        {loading ? (
          <Center py={60}>
            <Stack gap="md" align="center">
              <Loader size="lg" color="blue" />
              <Text size="sm" c="dimmed" fw={500}>
                Loading projects...
              </Text>
            </Stack>
          </Center>
        ) : filteredProjects.length === 0 ? (
          <Center py={60}>
            <Stack gap="lg" align="center">
              <ThemeIcon size={64} radius="md" variant="light" color="gray">
                <IconFolder size={32} />
              </ThemeIcon>
              <Stack gap={4} align="center">
                <Text size="lg" fw={600} c="dark.6">
                  {searchQuery || statusFilter ? 'No projects found' : 'No projects yet'}
                </Text>
                <Text size="sm" c="dimmed" style={{ textAlign: 'center', maxWidth: 300 }}>
                  {searchQuery || statusFilter
                    ? 'Try adjusting your search or filter criteria'
                    : 'Create your first migration assessment project to get started'
                  }
                </Text>
              </Stack>
              {!searchQuery && !statusFilter && (
                <Button
                  size="md"
                  radius="md"
                  onClick={() => setCreateModalOpen(true)}
                  leftSection={<IconPlus size={16} />}
                >
                  Create First Project
                </Button>
              )}
            </Stack>
          </Center>
        ) : (
          <>
            <Table striped highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Pin</Table.Th>
                  <Table.Th>Project Details</Table.Th>
                  <Table.Th>Client</Table.Th>
                  <Table.Th>Status</Table.Th>
                  <Table.Th>Created</Table.Th>
                  <Table.Th>Actions</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {paginatedProjects.map((project) => (
                  <Table.Tr key={project.id}>
                    <Table.Td>
                      <ActionIcon
                        size={28}
                        variant="subtle"
                        color={pinnedProjects.has(project.id) ? "yellow" : "gray"}
                        radius="md"
                        onClick={() => togglePin(project.id)}
                      >
                        {pinnedProjects.has(project.id) ? (
                          <IconPinFilled size={16} stroke={1.5} />
                        ) : (
                          <IconPin size={16} stroke={1.5} />
                        )}
                      </ActionIcon>
                    </Table.Td>
                    <Table.Td>
                      <Group gap="md">
                        <ThemeIcon
                          size={32}
                          radius="md"
                          variant="light"
                          color={getStatusColor(project.status)}
                        >
                          {getStatusIcon(project.status)}
                        </ThemeIcon>
                        <Stack gap={2}>
                          <Text size="sm" fw={600} c="dark.8">
                            {project.name}
                          </Text>
                          <Text size="xs" c="dimmed" truncate>
                            {project.description}
                          </Text>
                        </Stack>
                      </Group>
                    </Table.Td>
                    <Table.Td>
                      <Stack gap={2}>
                        <Text size="sm" fw={500} c="dark.7">
                          {project.client_name}
                        </Text>
                        <Text size="xs" c="dimmed">
                          {project.client_contact}
                        </Text>
                      </Stack>
                    </Table.Td>
                    <Table.Td>
                      <Badge
                        color={getStatusColor(project.status)}
                        variant="light"
                        size="md"
                        radius="md"
                        fw={500}
                      >
                        {project.status.charAt(0).toUpperCase() + project.status.slice(1)}
                      </Badge>
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm" c="dimmed" fw={500}>
                        {new Date(project.created_at).toLocaleDateString('en-US', {
                          month: 'short',
                          day: 'numeric',
                          year: 'numeric'
                        })}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      <Group gap="xs">
                        <ActionIcon
                          size={32}
                          variant="subtle"
                          color="blue"
                          radius="md"
                          onClick={() => navigate(`/projects/${project.id}`)}
                        >
                          <IconEye size={16} stroke={1.5} />
                        </ActionIcon>
                        <ActionIcon
                          size={32}
                          variant="subtle"
                          color="green"
                          radius="md"
                          onClick={() => handleRunAssessment(project.id)}
                          disabled={project.status === 'running'}
                        >
                          <IconRefresh size={16} stroke={1.5} />
                        </ActionIcon>
                        <Menu shadow="lg" width={180} position="bottom-end">
                          <Menu.Target>
                            <ActionIcon
                              size={32}
                              variant="subtle"
                              color="gray"
                              radius="md"
                            >
                              <IconDots size={16} stroke={1.5} />
                            </ActionIcon>
                          </Menu.Target>
                          <Menu.Dropdown>
                            <Menu.Item
                              leftSection={<IconEye size={16} />}
                              onClick={() => navigate(`/projects/${project.id}`)}
                            >
                              View Details
                            </Menu.Item>
                            <Menu.Item
                              leftSection={<IconRefresh size={16} />}
                              onClick={() => handleRunAssessment(project.id)}
                              disabled={project.status === 'running'}
                            >
                              {project.status === 'running' ? 'Assessment Running...' : 'Run Assessment'}
                            </Menu.Item>
                            <Menu.Divider />
                            <Menu.Item
                              leftSection={<IconEdit size={16} />}
                            >
                              Edit Project
                            </Menu.Item>
                            <Menu.Item
                              leftSection={<IconDownload size={16} />}
                            >
                              Export Data
                            </Menu.Item>
                            <Menu.Divider />
                            <Menu.Item
                              leftSection={<IconTrash size={16} />}
                              color="red"
                              onClick={() => handleDeleteProject(project.id)}
                            >
                              Delete Project
                            </Menu.Item>
                          </Menu.Dropdown>
                        </Menu>
                      </Group>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>

            {/* Pagination */}
            {totalPages > 1 && (
              <Group justify="center" mt="xl">
                <Pagination
                  value={currentPage}
                  onChange={setCurrentPage}
                  total={totalPages}
                  size="md"
                  radius="md"
                />
              </Group>
            )}
          </>
        )}
      </Card>

      {/* Professional Create Project Modal */}
      <Modal
        opened={createModalOpen}
        onClose={() => setCreateModalOpen(false)}
        title={
          <Group gap="sm">
            <ThemeIcon size={32} radius="md" variant="light" color="blue">
              <IconPlus size={18} />
            </ThemeIcon>
            <Text size="lg" fw={600}>
              Create New Project
            </Text>
          </Group>
        }
        size="lg"
        radius="lg"
      >
        <Stack gap="md">
          <TextInput
            label="Project Name"
            placeholder="Enter project name"
            value={newProject.name}
            onChange={(event) => setNewProject({ ...newProject, name: event.currentTarget.value })}
            required
            radius="md"
          />
          <Textarea
            label="Description"
            placeholder="Describe the migration project"
            value={newProject.description}
            onChange={(event) => setNewProject({ ...newProject, description: event.currentTarget.value })}
            rows={3}
            radius="md"
          />
          <TextInput
            label="Client Name"
            placeholder="Enter client organization name"
            value={newProject.client_name}
            onChange={(event) => setNewProject({ ...newProject, client_name: event.currentTarget.value })}
            required
            radius="md"
          />
          <TextInput
            label="Client Contact"
            placeholder="Enter client contact email (optional)"
            value={newProject.client_contact}
            onChange={(event) => setNewProject({ ...newProject, client_contact: event.currentTarget.value })}
            radius="md"
          />

          <Select
            label="Default LLM Configuration"
            placeholder="Select LLM configuration for this project"
            value={newProject.default_llm_config_id}
            onChange={(value) => setNewProject({ ...newProject, default_llm_config_id: value || '' })}
            data={llmConfigs.map(config => ({
              value: config.id,
              label: `${config.name} (${config.provider}/${config.model}) - ${config.status === 'configured' ? 'Ready' : 'Needs API Key'}`
            }))}
            required
            radius="md"
            description="This LLM will be used for document processing, chat, and deliverable generation"
          />

          {newProject.default_llm_config_id && (
            <Button
              variant="light"
              size="sm"
              loading={testingLLM}
              onClick={() => testLLMConfiguration(newProject.default_llm_config_id, true)}
              disabled={!newProject.default_llm_config_id}
            >
              {testingLLM ? 'Testing LLM...' : 'Test LLM Configuration'}
            </Button>
          )}

          {/* Inline Test Result Display */}
          {testResult && (
            <Card p="md" withBorder style={{
              backgroundColor: testResult.status === 'success' ? '#e8f5e8' : '#ffe8e8',
              marginLeft: '0px',
              marginRight: '0px',
              width: '100%'
            }}>
              <Stack gap="sm">
                <Group gap="xs">
                  <Text size="sm" fw={600}>
                    Test Result for {testResult.configName}:
                  </Text>
                  <Badge color={testResult.status === 'success' ? 'green' : 'red'}>
                    {testResult.status === 'success' ? 'Success' : 'Failed'}
                  </Badge>
                  <Text size="xs" c="dimmed">
                    at {testResult.timestamp}
                  </Text>
                </Group>

                <div style={{ marginLeft: '0px', width: '100%' }}>
                  <Text size="xs" c="dimmed" mb="xs">Query sent to LLM:</Text>
                  <div style={{
                    backgroundColor: '#f0f0f0',
                    padding: '8px',
                    borderRadius: '4px',
                    fontFamily: 'monospace',
                    fontSize: '12px',
                    marginLeft: '0px',
                    width: '100%',
                    boxSizing: 'border-box'
                  }}>
                    {testResult.query}
                  </div>
                </div>

                <div style={{ marginLeft: '0px', width: '100%' }}>
                  <Text size="xs" c="dimmed" mb="xs">
                    {testResult.status === 'success' ? 'Response received:' : 'Error message:'}
                  </Text>
                  <div style={{
                    backgroundColor: testResult.status === 'success' ? '#e8f5e8' : '#ffe8e8',
                    padding: '8px',
                    borderRadius: '4px',
                    fontFamily: 'monospace',
                    fontSize: '12px',
                    marginLeft: '0px',
                    width: '100%',
                    boxSizing: 'border-box',
                    wordWrap: 'break-word'
                  }}>
                    {testResult.status === 'success' ? testResult.response : testResult.message}
                  </div>
                </div>

                {testResult.status === 'success' && (
                  <Text size="xs" c="green" fw={500} style={{ marginLeft: '0px' }}>
                    ✅ LLM configuration is working correctly. You can proceed with project creation.
                  </Text>
                )}

                {testResult.status === 'error' && (
                  <Text size="xs" c="red" fw={500} style={{ marginLeft: '0px' }}>
                    ❌ LLM configuration failed. Please check the configuration in Settings.
                  </Text>
                )}
              </Stack>
            </Card>
          )}
          <Group justify="flex-end" mt="md">
            <Button
              variant="subtle"
              onClick={() => setCreateModalOpen(false)}
              radius="md"
            >
              Cancel
            </Button>
            <Button
              onClick={handleCreateProject}
              disabled={!newProject.name || !newProject.client_name || !newProject.default_llm_config_id}
              radius="md"
            >
              Create Project
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  );
};
