/**
 * Professional Dashboard View - SharePoint-like structured dashboard
 * Features professional stats grid and recent projects table
 */

import React, { useEffect, useState } from 'react';
import {
  Card,
  Text,
  Group,
  RingProgress,
  SimpleGrid,
  Table,
  Badge,
  ActionIcon,
  Button,
  Stack,
  Title,
  ThemeIcon,
  Box,
  Center,
  Menu,
  Skeleton,
  Alert,
  Loader,
  rem,
} from '@mantine/core';
import {
  IconFolder,
  IconCheck,
  IconClock,
  IconTrendingUp,
  IconEye,
  IconDots,
  IconActivity,
  IconTarget,
  IconPlus,
  IconArrowRight,
  IconAlertCircle, IconTopologyStar, IconFile,
} from '@tabler/icons-react';
import { useNavigate } from 'react-router-dom';
import { useProjects, useProjectStats } from '../hooks/useProjects';

export const DashboardView: React.FC = () => {
  const [platformStats, setPlatformStats] = useState<{ total_projects: number; total_documents: number; total_embeddings: number; total_neo4j_nodes: number; total_neo4j_relationships: number } | null>(null);
  const [platformLoading, setPlatformLoading] = useState(false);
  const loadPlatformStats = async () => {
    try {
      setPlatformLoading(true);
      const resp = await fetch('http://localhost:8000/api/platform/stats');
      if (resp.ok) {
        setPlatformStats(await resp.json());
      }
    } finally {
      setPlatformLoading(false);
    }
  };
  useEffect(() => { loadPlatformStats(); }, []);

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
    <Stack gap="md">
      {/* Professional Stats Grid - SharePoint Style */}
      <SimpleGrid cols={4} spacing="lg">
        {/* Total Projects Card */}
        <Card p="sm" radius="md">
          <Group justify="space-between" align="center">
            <Group gap="sm" style={{ flex: 1 }}>
              <ThemeIcon size={24} radius="md" variant="light" color="corporate">
                <IconFolder size={14} />
              </ThemeIcon>
              <Text size="sm" fw={600} c="dimmed" tt="uppercase">
                Total Projects
              </Text>
              {statsLoading ? (
                <Skeleton height={24} width={40} />
              ) : (
                <Text size="xl" fw={700} c="dark.8" ml="auto">
                  {stats?.total_projects || projects.length}
                </Text>
              )}
            </Group>
          </Group>
        </Card>

        {/* Active Projects Card */}
        <Card p="sm" radius="md">
          <Group justify="space-between" align="center">
            <Group gap="sm" style={{ flex: 1 }}>
              <ThemeIcon size={24} radius="md" variant="light" color="blue">
                <IconActivity size={14} />
              </ThemeIcon>
              <Text size="sm" fw={600} c="dimmed" tt="uppercase">
                Active Projects
              </Text>
              {statsLoading ? (
                <Skeleton height={24} width={40} />
              ) : (
                <Text size="xl" fw={700} c="dark.8" ml="auto">
                  {stats?.active_projects || projects.filter(p => p.status === 'running').length}
                </Text>
              )}
            </Group>
          </Group>
        </Card>

        {/* Completed Projects Card */}
        <Card p="sm" radius="md">
          <Group justify="space-between" align="center">
            <Group gap="sm" style={{ flex: 1 }}>
              <ThemeIcon size={24} radius="md" variant="light" color="green">
                <IconCheck size={14} />
              </ThemeIcon>
              <Text size="sm" fw={600} c="dimmed" tt="uppercase">
                Completed
              </Text>
              {statsLoading ? (
                <Skeleton height={24} width={40} />
              ) : (
                <Text size="xl" fw={700} c="dark.8" ml="auto">
                  {stats?.completed_assessments || projects.filter(p => p.status === 'completed').length}
                </Text>
              )}
            </Group>
          </Group>
        </Card>

        {/* Success Rate Card with RingProgress */}
        <Card p="sm" radius="md">
          <Group justify="space-between" align="center">
            <Group gap="sm" style={{ flex: 1 }}>
              <ThemeIcon size={24} radius="md" variant="light" color="teal">
                <IconTarget size={14} />
              </ThemeIcon>
              <Text size="sm" fw={600} c="dimmed" tt="uppercase">
                Success Rate
              </Text>
              {statsLoading ? (
                <Skeleton height={24} width={40} />
              ) : (
                <Text size="xl" fw={700} c="dark.8" ml="auto">
                  {stats?.total_projects && stats.total_projects > 0
                    ? Math.round((stats.completed_assessments / stats.total_projects) * 100)
                    : 85}%
                </Text>
              )}
            </Group>
          </Group>
        </Card>
      </SimpleGrid>

      {/* Professional Recent Projects Section */}
      <Card p="lg" radius="md">
        <Group justify="space-between" mb="lg">
          <Box>
            <Title order={3} fw={600} c="dark.8" mb={4}>
              Recent Projects
            </Title>
            <Text size="sm" c="dimmed">
              Latest migration assessment projects
            </Text>
          </Box>
          <Button
            variant="filled"
            color="corporate"
            leftSection={<IconArrowRight size={16} />}
            onClick={() => navigate('/projects')}
          >
            View All Projects
          </Button>
        </Group>

        {projectsLoading ? (
          <Stack gap="xs">
            {[...Array(3)].map((_, i) => (
              <Group key={i} gap="md" p="md">
                <Skeleton height={40} width={40} radius="md" />
                <Box style={{ flex: 1 }}>
                  <Skeleton height={16} width="60%" mb={8} />
                  <Skeleton height={12} width="40%" />
                </Box>
                <Skeleton height={24} width={80} radius="md" />
                <Skeleton height={32} width={32} radius="md" />
              </Group>
            ))}
          </Stack>
        ) : recentProjects.length === 0 ? (
          <Center py={80}>
            <Stack gap="lg" align="center">
              <ThemeIcon size={80} radius="md" variant="light" color="corporate">
                <IconFolder size={40} />
              </ThemeIcon>
              <Stack gap={8} align="center">
                <Text size="xl" fw={600} c="dark.7">
                  No projects have been created yet
                </Text>
                <Text size="sm" c="dimmed" ta="center" maw={400}>
                  Get started by creating your first cloud migration assessment project.
                  Our AI-powered platform will guide you through the entire process.
                </Text>
              </Stack>
              <Button
                size="lg"
                color="corporate"
                leftSection={<IconPlus size={18} />}
                onClick={() => navigate('/projects')}
      {/* Platform-wide Stats Grid */}
      <SimpleGrid cols={4} spacing="lg">
        <Card p="sm" radius="md">
          <Group justify="space-between" align="center">
            <Group gap="sm" style={{ flex: 1 }}>
              <ThemeIcon size={24} radius="md" variant="light" color="violet">
                <IconFile size={14} />
              </ThemeIcon>
              <Text size="sm" fw={600} c="dimmed" tt="uppercase">Total Documents</Text>
              {platformLoading ? <Skeleton height={24} width={40} /> : (
                <Text size="xl" fw={700} c="dark.8" ml="auto">{platformStats?.total_documents ?? '—'}</Text>
              )}
            </Group>
          </Group>
        </Card>

        <Card p="sm" radius="md">
          <Group justify="space-between" align="center">
            <Group gap="sm" style={{ flex: 1 }}>
              <ThemeIcon size={24} radius="md" variant="light" color="teal">
                <IconActivity size={14} />
              </ThemeIcon>
              <Text size="sm" fw={600} c="dimmed" tt="uppercase">Total Embeddings</Text>
              {platformLoading ? <Skeleton height={24} width={40} /> : (
                <Text size="xl" fw={700} c="dark.8" ml="auto">{platformStats?.total_embeddings ?? '—'}</Text>
              )}
            </Group>
          </Group>
        </Card>

        <Card p="sm" radius="md">
          <Group justify="space-between" align="center">
            <Group gap="sm" style={{ flex: 1 }}>
              <ThemeIcon size={24} radius="md" variant="light" color="blue">
                <IconTopologyStar size={14} />
              </ThemeIcon>
              <Text size="sm" fw={600} c="dimmed" tt="uppercase">Neo4j Nodes</Text>
              {platformLoading ? <Skeleton height={24} width={40} /> : (
                <Text size="xl" fw={700} c="dark.8" ml="auto">{platformStats?.total_neo4j_nodes ?? '—'}</Text>
              )}
            </Group>
          </Group>
        </Card>

        <Card p="sm" radius="md">
          <Group justify="space-between" align="center">
            <Group gap="sm" style={{ flex: 1 }}>
              <ThemeIcon size={24} radius="md" variant="light" color="orange">
                <IconTopologyStar size={14} />
              </ThemeIcon>
              <Text size="sm" fw={600} c="dimmed" tt="uppercase">Neo4j Relationships</Text>
              {platformLoading ? <Skeleton height={24} width={40} /> : (
                <Text size="xl" fw={700} c="dark.8" ml="auto">{platformStats?.total_neo4j_relationships ?? '—'}</Text>
              )}
            </Group>
          </Group>
        </Card>
      </SimpleGrid>

              >
                Create New Project
              </Button>
            </Stack>
          </Center>
        ) : (
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Project Details</Table.Th>
                <Table.Th>Client</Table.Th>
                <Table.Th>Status</Table.Th>
                <Table.Th>Last Updated</Table.Th>
                <Table.Th>Actions</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {recentProjects.map((project) => (
                <Table.Tr key={project.id}>
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
                      {new Date(project.updated_at).toLocaleDateString('en-US', {
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
                        color="corporate"
                        radius="md"
                        onClick={() => navigate(`/projects/${project.id}`)}
                      >
                        <IconEye size={16} stroke={1.5} />
                      </ActionIcon>
                      <Menu shadow="md" width={160} position="bottom-end">
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
                            leftSection={<IconEye size={14} />}
                            onClick={() => navigate(`/projects/${project.id}`)}
                          >
                            View Details
                          </Menu.Item>
                        </Menu.Dropdown>
                      </Menu>
                    </Group>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        )}
      </Card>
    </Stack>
  );
};
