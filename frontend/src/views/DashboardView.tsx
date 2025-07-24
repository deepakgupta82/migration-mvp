/**
 * Dashboard View - High-level overview of migration activities
 */

import React from 'react';
import {
  Grid,
  Card,
  Text,
  Group,
  RingProgress,
  SimpleGrid,
  Table,
  Badge,
  ActionIcon,
  Loader,
  Alert,
  Button,
} from '@mantine/core';
import {
  IconFolder,
  IconCheck,
  IconClock,
  IconTrendingUp,
  IconEye,
  IconAlertCircle,
} from '@tabler/icons-react';
import { useNavigate } from 'react-router-dom';
import { useProjects, useProjectStats } from '../hooks/useProjects';

export const DashboardView: React.FC = () => {
  const navigate = useNavigate();
  const { projects, loading: projectsLoading } = useProjects();
  const { stats, loading: statsLoading, error } = useProjectStats();

  // Get recent projects (last 5)
  const recentProjects = projects
    .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
    .slice(0, 5);

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

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <IconCheck size={16} />;
      case 'running':
        return <IconClock size={16} />;
      default:
        return <IconFolder size={16} />;
    }
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
      {/* Stats Cards */}
      <SimpleGrid cols={4} spacing="lg" mb="xl">
        <Card shadow="sm" p="lg" radius="md" withBorder>
          <Group position="apart" mb="xs">
            <Text size="sm" color="dimmed" weight={500}>
              Total Projects
            </Text>
            <IconFolder size={20} color="#1c7ed6" />
          </Group>
          <Group align="flex-end" spacing="xs">
            {statsLoading ? (
              <Loader size="sm" />
            ) : (
              <Text size="xl" weight={700}>
                {stats?.total_projects || 0}
              </Text>
            )}
          </Group>
        </Card>

        <Card shadow="sm" p="lg" radius="md" withBorder>
          <Group position="apart" mb="xs">
            <Text size="sm" color="dimmed" weight={500}>
              Active Projects
            </Text>
            <IconClock size={20} color="#fd7e14" />
          </Group>
          <Group align="flex-end" spacing="xs">
            {statsLoading ? (
              <Loader size="sm" />
            ) : (
              <Text size="xl" weight={700}>
                {stats?.active_projects || 0}
              </Text>
            )}
          </Group>
        </Card>

        <Card shadow="sm" p="lg" radius="md" withBorder>
          <Group position="apart" mb="xs">
            <Text size="sm" color="dimmed" weight={500}>
              Completed Assessments
            </Text>
            <IconCheck size={20} color="#51cf66" />
          </Group>
          <Group align="flex-end" spacing="xs">
            {statsLoading ? (
              <Loader size="sm" />
            ) : (
              <Text size="xl" weight={700}>
                {stats?.completed_assessments || 0}
              </Text>
            )}
          </Group>
        </Card>

        <Card shadow="sm" p="lg" radius="md" withBorder>
          <Group position="apart" mb="xs">
            <Text size="sm" color="dimmed" weight={500}>
              Success Rate
            </Text>
            <IconTrendingUp size={20} color="#51cf66" />
          </Group>
          <Group align="flex-end" spacing="xs">
            {statsLoading ? (
              <Loader size="sm" />
            ) : (
              <>
                <Text size="xl" weight={700}>
                  {stats?.total_projects && stats.total_projects > 0
                    ? Math.round((stats.completed_assessments / stats.total_projects) * 100)
                    : 0}%
                </Text>
                <RingProgress
                  size={60}
                  thickness={6}
                  sections={[
                    {
                      value: stats?.total_projects && stats.total_projects > 0
                        ? (stats.completed_assessments / stats.total_projects) * 100
                        : 0,
                      color: 'green',
                    },
                  ]}
                />
              </>
            )}
          </Group>
        </Card>
      </SimpleGrid>

      {/* Recent Projects Table */}
      <Card shadow="sm" p="lg" radius="md" withBorder>
        <Group position="apart" mb="md">
          <Text size="lg" weight={600}>
            Recent Projects
          </Text>
          <Button
            variant="light"
            size="sm"
            onClick={() => navigate('/projects')}
          >
            View All Projects
          </Button>
        </Group>

        {projectsLoading ? (
          <Group position="center" p="xl">
            <Loader size="lg" />
          </Group>
        ) : recentProjects.length === 0 ? (
          <Group position="center" p="xl">
            <div style={{ textAlign: 'center' }}>
              <IconFolder size={48} color="#ced4da" />
              <Text size="lg" color="dimmed" mt="md">
                No projects yet
              </Text>
              <Text size="sm" color="dimmed">
                Create your first project to get started
              </Text>
              <Button
                mt="md"
                onClick={() => navigate('/projects')}
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
                <th>Last Updated</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {recentProjects.map((project) => (
                <tr key={project.id}>
                  <td>
                    <Group spacing="sm">
                      {getStatusIcon(project.status)}
                      <div>
                        <Text size="sm" weight={500}>
                          {project.name}
                        </Text>
                        <Text size="xs" color="dimmed">
                          {project.description}
                        </Text>
                      </div>
                    </Group>
                  </td>
                  <td>
                    <Text size="sm">{project.client_name}</Text>
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
                      {new Date(project.updated_at).toLocaleDateString()}
                    </Text>
                  </td>
                  <td>
                    <ActionIcon
                      size="sm"
                      variant="subtle"
                      onClick={() => navigate(`/projects/${project.id}`)}
                    >
                      <IconEye size={16} />
                    </ActionIcon>
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
    </div>
  );
};
