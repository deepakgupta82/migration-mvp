/**
 * Cloud Migration View - Phase 1: Cloud Orchestration
 * Professional interface for managing migration waves, resources, and execution
 */

import React, { useEffect, useState } from 'react';
import {
  Card,
  Text,
  Group,
  Button,
  Stack,
  Title,
  Badge,
  Table,
  Modal,
  TextInput,
  Select,
  Textarea,
  Alert,
  ActionIcon,
  Menu,
  Tabs,
  ThemeIcon,
  Progress,
  Timeline,
  SimpleGrid,
  Paper,
  Loader,
  Center,
  rem,
} from '@mantine/core';
import {
  IconCloud,
  IconPlus,
  IconEdit,
  IconTrash,
  IconPlaylistAdd,
  IconRocket,
  IconCheck,
  IconClock,
  IconAlertCircle,
  IconDots,
  IconEye,
  IconRefresh,
  IconServer,
  IconDatabase,
  IconNetworkOff,
  IconArrowRight,
} from '@tabler/icons-react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { notifications } from '@mantine/notifications';

interface MigrationWave {
  wave_id: string;
  project_id: string;
  name: string;
  description?: string;
  target_cloud: 'aws' | 'azure' | 'gcp';
  priority: number;
  status: 'draft' | 'ready' | 'in_progress' | 'completed' | 'failed';
  resource_count: number;
  created_at: string;
  updated_at: string;
}

interface WaveResource {
  resource_id: string;
  wave_id: string;
  resource_type: string;
  source_identifier: string;
  target_config?: any;
  dependencies?: string[];
  migration_status: 'pending' | 'in_progress' | 'completed' | 'failed';
}

export const CloudMigrationView: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const projectId = searchParams.get('project');

  const [waves, setWaves] = useState<MigrationWave[]>([]);
  const [selectedWave, setSelectedWave] = useState<MigrationWave | null>(null);
  const [waveResources, setWaveResources] = useState<WaveResource[]>([]);
  const [loading, setLoading] = useState(true);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [addResourceModalOpen, setAddResourceModalOpen] = useState(false);

  // Form state
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    target_cloud: 'aws' as 'aws' | 'azure' | 'gcp',
    priority: 1,
  });

  const [resourceFormData, setResourceFormData] = useState({
    resource_type: '',
    source_identifier: '',
    target_config: '{}',
  });

  useEffect(() => {
    loadWaves();
  }, [projectId]);

  const loadWaves = async () => {
    try {
      setLoading(true);
      const url = projectId
        ? `/api/cloud-orchestration/api/waves?project_id=${projectId}`
        : '/api/cloud-orchestration/api/waves';

      const response = await fetch(url, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token') || 'service-backend-token'}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        setWaves(data.waves || []);
      }
    } catch (error) {
      console.error('Failed to load migration waves:', error);
      notifications.show({
        title: 'Error',
        message: 'Failed to load migration waves',
        color: 'red',
      });
    } finally {
      setLoading(false);
    }
  };

  const loadWaveResources = async (waveId: string) => {
    try {
      const response = await fetch(`/api/cloud-orchestration/api/waves/${waveId}/resources`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token') || 'service-backend-token'}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        setWaveResources(data.resources || []);
      }
    } catch (error) {
      console.error('Failed to load wave resources:', error);
    }
  };

  const handleCreateWave = async () => {
    try {
      if (!projectId) {
        notifications.show({
          title: 'Error',
          message: 'Please select a project first',
          color: 'red',
        });
        return;
      }

      const response = await fetch('/api/cloud-orchestration/api/waves', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token') || 'service-backend-token'}`,
        },
        body: JSON.stringify({
          project_id: projectId,
          ...formData,
        }),
      });

      if (response.ok) {
        notifications.show({
          title: 'Success',
          message: 'Migration wave created successfully',
          color: 'green',
        });
        setCreateModalOpen(false);
        setFormData({ name: '', description: '', target_cloud: 'aws', priority: 1 });
        loadWaves();
      } else {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to create wave');
      }
    } catch (error: any) {
      notifications.show({
        title: 'Error',
        message: error.message || 'Failed to create migration wave',
        color: 'red',
      });
    }
  };

  const handleAddResource = async () => {
    if (!selectedWave) return;

    try {
      const response = await fetch(`/api/cloud-orchestration/api/waves/${selectedWave.wave_id}/resources`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token') || 'service-backend-token'}`,
        },
        body: JSON.stringify({
          ...resourceFormData,
          target_config: JSON.parse(resourceFormData.target_config),
        }),
      });

      if (response.ok) {
        notifications.show({
          title: 'Success',
          message: 'Resource added to wave',
          color: 'green',
        });
        setAddResourceModalOpen(false);
        setResourceFormData({ resource_type: '', source_identifier: '', target_config: '{}' });
        loadWaveResources(selectedWave.wave_id);
      } else {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to add resource');
      }
    } catch (error: any) {
      notifications.show({
        title: 'Error',
        message: error.message || 'Failed to add resource',
        color: 'red',
      });
    }
  };

  const handleExecuteWave = async (waveId: string) => {
    try {
      const response = await fetch(`/api/cloud-orchestration/api/waves/${waveId}/execute`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token') || 'service-backend-token'}`,
        },
      });

      if (response.ok) {
        notifications.show({
          title: 'Success',
          message: 'Migration wave execution started',
          color: 'green',
        });
        loadWaves();
      } else {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to execute wave');
      }
    } catch (error: any) {
      notifications.show({
        title: 'Error',
        message: error.message || 'Failed to execute wave',
        color: 'red',
      });
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'green';
      case 'in_progress': return 'blue';
      case 'ready': return 'cyan';
      case 'failed': return 'red';
      default: return 'gray';
    }
  };

  const getCloudIcon = (cloud: string) => {
    switch (cloud) {
      case 'aws': return '☁️';
      case 'azure': return '⛅';
      case 'gcp': return '🌤️';
      default: return '☁️';
    }
  };

  if (loading) {
    return (
      <Center h={400}>
        <Loader size="lg" />
      </Center>
    );
  }

  return (
    <Stack gap="lg">
      {/* Header */}
      <Group justify="space-between">
        <div>
          <Title order={2}>Cloud Migration</Title>
          <Text size="sm" c="dimmed">
            Manage migration waves and orchestrate cloud resource migrations
          </Text>
        </div>
        <Group>
          <ActionIcon variant="light" onClick={loadWaves}>
            <IconRefresh size={18} />
          </ActionIcon>
          <Button
            leftSection={<IconPlus size={18} />}
            onClick={() => setCreateModalOpen(true)}
            disabled={!projectId}
          >
            Create Wave
          </Button>
        </Group>
      </Group>

      {!projectId && (
        <Alert icon={<IconAlertCircle size={16} />} color="blue">
          Please select a project from the query parameters to manage migration waves
        </Alert>
      )}

      {/* Stats Cards */}
      <SimpleGrid cols={4}>
        <Paper p="md" withBorder>
          <Group justify="space-between">
            <div>
              <Text size="xs" c="dimmed" tt="uppercase">Total Waves</Text>
              <Text size="xl" fw={700}>{waves.length}</Text>
            </div>
            <ThemeIcon size="lg" variant="light" color="blue">
              <IconCloud size={24} />
            </ThemeIcon>
          </Group>
        </Paper>
        <Paper p="md" withBorder>
          <Group justify="space-between">
            <div>
              <Text size="xs" c="dimmed" tt="uppercase">In Progress</Text>
              <Text size="xl" fw={700}>
                {waves.filter(w => w.status === 'in_progress').length}
              </Text>
            </div>
            <ThemeIcon size="lg" variant="light" color="blue">
              <IconClock size={24} />
            </ThemeIcon>
          </Group>
        </Paper>
        <Paper p="md" withBorder>
          <Group justify="space-between">
            <div>
              <Text size="xs" c="dimmed" tt="uppercase">Completed</Text>
              <Text size="xl" fw={700}>
                {waves.filter(w => w.status === 'completed').length}
              </Text>
            </div>
            <ThemeIcon size="lg" variant="light" color="green">
              <IconCheck size={24} />
            </ThemeIcon>
          </Group>
        </Paper>
        <Paper p="md" withBorder>
          <Group justify="space-between">
            <div>
              <Text size="xs" c="dimmed" tt="uppercase">Total Resources</Text>
              <Text size="xl" fw={700}>
                {waves.reduce((sum, w) => sum + (w.resource_count || 0), 0)}
              </Text>
            </div>
            <ThemeIcon size="lg" variant="light" color="grape">
              <IconServer size={24} />
            </ThemeIcon>
          </Group>
        </Paper>
      </SimpleGrid>

      {/* Migration Waves Table */}
      <Card>
        <Table highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Wave Name</Table.Th>
              <Table.Th>Target Cloud</Table.Th>
              <Table.Th>Priority</Table.Th>
              <Table.Th>Resources</Table.Th>
              <Table.Th>Status</Table.Th>
              <Table.Th>Created</Table.Th>
              <Table.Th>Actions</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {waves.map((wave) => (
              <Table.Tr key={wave.wave_id}>
                <Table.Td>
                  <div>
                    <Text fw={500}>{wave.name}</Text>
                    {wave.description && (
                      <Text size="xs" c="dimmed">{wave.description}</Text>
                    )}
                  </div>
                </Table.Td>
                <Table.Td>
                  <Badge variant="light" color="blue">
                    {getCloudIcon(wave.target_cloud)} {wave.target_cloud.toUpperCase()}
                  </Badge>
                </Table.Td>
                <Table.Td>
                  <Badge variant="outline" size="sm">
                    P{wave.priority}
                  </Badge>
                </Table.Td>
                <Table.Td>
                  <Badge variant="filled" color="grape">
                    {wave.resource_count || 0}
                  </Badge>
                </Table.Td>
                <Table.Td>
                  <Badge color={getStatusColor(wave.status)}>
                    {wave.status}
                  </Badge>
                </Table.Td>
                <Table.Td>
                  <Text size="sm">
                    {new Date(wave.created_at).toLocaleDateString()}
                  </Text>
                </Table.Td>
                <Table.Td>
                  <Group gap="xs">
                    <ActionIcon
                      variant="light"
                      color="blue"
                      onClick={() => {
                        setSelectedWave(wave);
                        loadWaveResources(wave.wave_id);
                      }}
                    >
                      <IconEye size={16} />
                    </ActionIcon>
                    <ActionIcon
                      variant="light"
                      color="green"
                      onClick={() => handleExecuteWave(wave.wave_id)}
                      disabled={wave.status === 'in_progress' || wave.status === 'completed'}
                    >
                      <IconRocket size={16} />
                    </ActionIcon>
                    <Menu position="bottom-end">
                      <Menu.Target>
                        <ActionIcon variant="subtle">
                          <IconDots size={16} />
                        </ActionIcon>
                      </Menu.Target>
                      <Menu.Dropdown>
                        <Menu.Item
                          leftSection={<IconPlaylistAdd size={16} />}
                          onClick={() => {
                            setSelectedWave(wave);
                            setAddResourceModalOpen(true);
                          }}
                        >
                          Add Resources
                        </Menu.Item>
                        <Menu.Item leftSection={<IconEdit size={16} />}>
                          Edit Wave
                        </Menu.Item>
                        <Menu.Divider />
                        <Menu.Item leftSection={<IconTrash size={16} />} color="red">
                          Delete Wave
                        </Menu.Item>
                      </Menu.Dropdown>
                    </Menu>
                  </Group>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>

        {waves.length === 0 && (
          <Center p="xl">
            <Stack align="center" gap="sm">
              <IconNetworkOff size={48} stroke={1.5} color="gray" />
              <Text c="dimmed">No migration waves yet</Text>
              <Button
                size="sm"
                variant="light"
                leftSection={<IconPlus size={16} />}
                onClick={() => setCreateModalOpen(true)}
                disabled={!projectId}
              >
                Create First Wave
              </Button>
            </Stack>
          </Center>
        )}
      </Card>

      {/* Wave Resources Modal */}
      <Modal
        opened={selectedWave !== null && !addResourceModalOpen}
        onClose={() => setSelectedWave(null)}
        size="xl"
        title={
          <Group>
            <IconCloud size={20} />
            <Text fw={600}>Wave Resources: {selectedWave?.name}</Text>
          </Group>
        }
      >
        <Stack>
          <Group justify="space-between">
            <Text size="sm" c="dimmed">
              {waveResources.length} resources in this wave
            </Text>
            <Button
              size="sm"
              leftSection={<IconPlus size={16} />}
              onClick={() => setAddResourceModalOpen(true)}
            >
              Add Resource
            </Button>
          </Group>

          <Table>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Type</Table.Th>
                <Table.Th>Source</Table.Th>
                <Table.Th>Status</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {waveResources.map((resource) => (
                <Table.Tr key={resource.resource_id}>
                  <Table.Td>
                    <Badge variant="light">{resource.resource_type}</Badge>
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm" ff="monospace">{resource.source_identifier}</Text>
                  </Table.Td>
                  <Table.Td>
                    <Badge color={getStatusColor(resource.migration_status)}>
                      {resource.migration_status}
                    </Badge>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Stack>
      </Modal>

      {/* Create Wave Modal */}
      <Modal
        opened={createModalOpen}
        onClose={() => setCreateModalOpen(false)}
        title="Create Migration Wave"
      >
        <Stack>
          <TextInput
            label="Wave Name"
            placeholder="e.g., Production Database Migration"
            required
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
          />
          <Textarea
            label="Description"
            placeholder="Describe the migration wave..."
            rows={3}
            value={formData.description}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
          />
          <Select
            label="Target Cloud"
            required
            data={[
              { value: 'aws', label: '☁️ AWS' },
              { value: 'azure', label: '⛅ Azure' },
              { value: 'gcp', label: '🌤️ GCP' },
            ]}
            value={formData.target_cloud}
            onChange={(value) => setFormData({ ...formData, target_cloud: value as any })}
          />
          <Select
            label="Priority"
            required
            data={[
              { value: '1', label: 'P1 - Critical' },
              { value: '2', label: 'P2 - High' },
              { value: '3', label: 'P3 - Medium' },
              { value: '4', label: 'P4 - Low' },
            ]}
            value={String(formData.priority)}
            onChange={(value) => setFormData({ ...formData, priority: parseInt(value || '1') })}
          />
          <Group justify="flex-end" mt="md">
            <Button variant="subtle" onClick={() => setCreateModalOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreateWave}>Create Wave</Button>
          </Group>
        </Stack>
      </Modal>

      {/* Add Resource Modal */}
      <Modal
        opened={addResourceModalOpen}
        onClose={() => setAddResourceModalOpen(false)}
        title="Add Resource to Wave"
      >
        <Stack>
          <Select
            label="Resource Type"
            placeholder="Select resource type"
            required
            data={[
              { value: 'ec2', label: 'EC2 Instance' },
              { value: 'rds', label: 'RDS Database' },
              { value: 's3', label: 'S3 Bucket' },
              { value: 'lambda', label: 'Lambda Function' },
              { value: 'efs', label: 'EFS File System' },
            ]}
            value={resourceFormData.resource_type}
            onChange={(value) => setResourceFormData({ ...resourceFormData, resource_type: value || '' })}
          />
          <TextInput
            label="Source Identifier"
            placeholder="e.g., i-0123456789abcdef0"
            required
            value={resourceFormData.source_identifier}
            onChange={(e) => setResourceFormData({ ...resourceFormData, source_identifier: e.target.value })}
          />
          <Textarea
            label="Target Configuration (JSON)"
            placeholder='{"instance_type": "t3.medium", "region": "us-east-1"}'
            rows={4}
            value={resourceFormData.target_config}
            onChange={(e) => setResourceFormData({ ...resourceFormData, target_config: e.target.value })}
          />
          <Group justify="flex-end" mt="md">
            <Button variant="subtle" onClick={() => setAddResourceModalOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleAddResource}>Add Resource</Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  );
};

export default CloudMigrationView;
