/**
 * Projects View - Comprehensive project management interface
 */

import React, { useState } from 'react';
import {
  Card,
  Text,
  Group,
  Button,
  Table,
  Badge,
  ActionIcon,
  Modal,
  TextInput,
  Textarea,
  Select,
  Loader,
  Alert,
  Menu,
  Divider,
} from '@mantine/core';
import {
  IconPlus,
  IconEye,
  IconEdit,
  IconTrash,
  IconDownload,
  IconDots,
  IconAlertCircle,
  IconFolder,
} from '@tabler/icons-react';
import { useNavigate } from 'react-router-dom';
import { useProjects } from '../hooks/useProjects';
import { Project } from '../services/api';
import { notifications } from '@mantine/notifications';

export const ProjectsView: React.FC = () => {
  const navigate = useNavigate();
  const { projects, loading, error, createProject, deleteProject } = useProjects();
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [creating, setCreating] = useState(false);
  const [deleting, setDeleting] = useState(false);

  // Form state for creating new project
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    client_name: '',
    client_contact: '',
  });

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

  const handleCreateProject = async () => {
    if (!formData.name || !formData.client_name) {
      notifications.show({
        title: 'Validation Error',
        message: 'Project name and client name are required',
        color: 'red',
      });
      return;
    }

    try {
      setCreating(true);
      await createProject(formData);
      setCreateModalOpen(false);
      setFormData({ name: '', description: '', client_name: '', client_contact: '' });
      notifications.show({
        title: 'Success',
        message: 'Project created successfully',
        color: 'green',
      });
    } catch (err) {
      notifications.show({
        title: 'Error',
        message: 'Failed to create project',
        color: 'red',
      });
    } finally {
      setCreating(false);
    }
  };

  const handleDeleteProject = async () => {
    if (!selectedProject) return;

    try {
      setDeleting(true);
      await deleteProject(selectedProject.id);
      setDeleteModalOpen(false);
      setSelectedProject(null);
      notifications.show({
        title: 'Success',
        message: 'Project deleted successfully',
        color: 'green',
      });
    } catch (err) {
      notifications.show({
        title: 'Error',
        message: 'Failed to delete project',
        color: 'red',
      });
    } finally {
      setDeleting(false);
    }
  };

  const openDeleteModal = (project: Project) => {
    setSelectedProject(project);
    setDeleteModalOpen(true);
  };

  if (error) {
    return (
      <Alert icon={<IconAlertCircle size={16} />} title="Error" color="red">
        {error}
      </Alert>
    );
  }

  return (
    <div>
      {/* Header */}
      <Group justify="space-between" mb="xl">
        <div>
          <Text size="xl" fw={600} mb="xs">
            Project Management
          </Text>
          <Text size="sm" color="dimmed">
            Manage your cloud migration projects and assessments
          </Text>
        </div>
        <Button
          leftSection={<IconPlus size={16} />}
          onClick={() => setCreateModalOpen(true)}
        >
          Create New Project
        </Button>
      </Group>

      {/* Projects Table */}
      <Card shadow="sm" p="lg" radius="md" withBorder>
        {loading ? (
          <Group justify="center" p="xl">
            <Loader size="lg" />
          </Group>
        ) : projects.length === 0 ? (
          <Group justify="center" p="xl">
            <div style={{ textAlign: 'center' }}>
              <IconFolder size={48} color="#ced4da" />
              <Text size="lg" color="dimmed" mt="md">
                No projects yet
              </Text>
              <Text size="sm" color="dimmed">
                Create your first project to get started with cloud migration assessments
              </Text>
              <Button
                mt="md"
                leftSection={<IconPlus size={16} />}
                onClick={() => setCreateModalOpen(true)}
              >
                Create Project
              </Button>
            </div>
          </Group>
        ) : (
          <Table>
            <thead>
              <tr>
                <th>Project Name</th>
                <th>Client</th>
                <th>Status</th>
                <th>Created</th>
                <th>Last Updated</th>
                <th>Reports</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {projects.map((project) => (
                <tr key={project.id}>
                  <td>
                    <div>
                      <Text size="sm" fw={500}>
                        {project.name}
                      </Text>
                      <Text size="xs" color="dimmed">
                        {project.description}
                      </Text>
                    </div>
                  </td>
                  <td>
                    <div>
                      <Text size="sm">{project.client_name}</Text>
                      {project.client_contact && (
                        <Text size="xs" color="dimmed">
                          {project.client_contact}
                        </Text>
                      )}
                    </div>
                  </td>
                  <td>
                    <Badge
                      color={getStatusColor(project.status)}
                      variant="light"
                      size="sm"
                    >
                      {project.status}
                    </Badge>
                  </td>
                  <td>
                    <Text size="sm" color="dimmed">
                      {new Date(project.created_at).toLocaleDateString()}
                    </Text>
                  </td>
                  <td>
                    <Text size="sm" color="dimmed">
                      {new Date(project.updated_at).toLocaleDateString()}
                    </Text>
                  </td>
                  <td>
                    <Group gap="xs">
                      {project.report_url && (
                        <Button
                          size="xs"
                          variant="light"
                          leftSection={<IconDownload size={12} />}
                          onClick={() => window.open(project.report_url, '_blank')}
                        >
                          DOCX
                        </Button>
                      )}
                      {project.report_artifact_url && (
                        <Button
                          size="xs"
                          variant="light"
                          color="red"
                          leftSection={<IconDownload size={12} />}
                          onClick={() => window.open(project.report_artifact_url, '_blank')}
                        >
                          PDF
                        </Button>
                      )}
                    </Group>
                  </td>
                  <td>
                    <Group gap="xs">
                      <ActionIcon
                        size="sm"
                        variant="subtle"
                        onClick={() => navigate(`/projects/${project.id}`)}
                      >
                        <IconEye size={16} />
                      </ActionIcon>
                      <Menu shadow="md" width={200}>
                        <Menu.Target>
                          <ActionIcon size="sm" variant="subtle">
                            <IconDots size={16} />
                          </ActionIcon>
                        </Menu.Target>
                        <Menu.Dropdown>
                          <Menu.Item
                            leftSection={<IconEye size={14} />}
                            onClick={() => navigate(`/projects/${project.id}`)}
                          >
                            View Details
                          </Menu.Item>
                          <Menu.Item leftSection={<IconEdit size={14} />}>
                            Edit Project
                          </Menu.Item>
                          <Menu.Divider />
                          <Menu.Item
                            leftSection={<IconTrash size={14} />}
                            color="red"
                            onClick={() => openDeleteModal(project)}
                          >
                            Delete Project
                          </Menu.Item>
                        </Menu.Dropdown>
                      </Menu>
                    </Group>
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>

      {/* Create Project Modal */}
      <Modal
        opened={createModalOpen}
        onClose={() => setCreateModalOpen(false)}
        title="Create New Project"
        size="md"
      >
        <div>
          <TextInput
            label="Project Name"
            placeholder="Enter project name"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            required
            mb="md"
          />
          <Textarea
            label="Description"
            placeholder="Enter project description"
            value={formData.description}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            mb="md"
            minRows={3}
          />
          <TextInput
            label="Client Name"
            placeholder="Enter client name"
            value={formData.client_name}
            onChange={(e) => setFormData({ ...formData, client_name: e.target.value })}
            required
            mb="md"
          />
          <TextInput
            label="Client Contact"
            placeholder="Enter client contact email"
            value={formData.client_contact}
            onChange={(e) => setFormData({ ...formData, client_contact: e.target.value })}
            mb="xl"
          />
          <Group justify="flex-end">
            <Button
              variant="subtle"
              onClick={() => setCreateModalOpen(false)}
              disabled={creating}
            >
              Cancel
            </Button>
            <Button
              onClick={handleCreateProject}
              loading={creating}
            >
              Create Project
            </Button>
          </Group>
        </div>
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal
        opened={deleteModalOpen}
        onClose={() => setDeleteModalOpen(false)}
        title="Delete Project"
        size="sm"
      >
        <div>
          <Text mb="md">
            Are you sure you want to delete the project "{selectedProject?.name}"?
            This action cannot be undone.
          </Text>
          <Group justify="flex-end">
            <Button
              variant="subtle"
              onClick={() => setDeleteModalOpen(false)}
              disabled={deleting}
            >
              Cancel
            </Button>
            <Button
              color="red"
              onClick={handleDeleteProject}
              loading={deleting}
            >
              Delete
            </Button>
          </Group>
        </div>
      </Modal>
    </div>
  );
};
