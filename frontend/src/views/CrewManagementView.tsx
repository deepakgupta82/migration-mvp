/**
 * Crew Management View - Dynamic Agent and Crew Editor
 * Allows users to edit AI agents, tasks, and crew configurations
 */

import React, { useState, useEffect } from 'react';
import {
  Container,
  Title,
  Text,
  Card,
  Group,
  Button,
  Stack,
  Tabs,
  Badge,
  ActionIcon,
  Modal,
  TextInput,
  Textarea,
  MultiSelect,
  Switch,
  NumberInput,
  Select,
  Alert,
  Loader,
  Divider,
  ScrollArea,
} from '@mantine/core';
import {
  IconRobot,
  IconEdit,
  IconPlus,
  IconTrash,
  IconDeviceFloppy,
  IconAlertCircle,
  IconCheck,
  IconUsers,
  IconClipboardList,
  IconSettings,
} from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';
import { useDisclosure } from '@mantine/hooks';
import {
  apiService,
  AgentDefinition,
  TaskDefinition,
  CrewDefinition,
  AvailableTool,
  CrewConfiguration,
} from '../services/api';

export function CrewManagementView() {
  const [config, setConfig] = useState<CrewConfiguration | null>(null);
  const [availableTools, setAvailableTools] = useState<AvailableTool[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);

  // Modal states
  const [agentModalOpened, { open: openAgentModal, close: closeAgentModal }] = useDisclosure(false);
  const [taskModalOpened, { open: openTaskModal, close: closeTaskModal }] = useDisclosure(false);
  const [crewModalOpened, { open: openCrewModal, close: closeCrewModal }] = useDisclosure(false);

  // Edit states
  const [editingAgent, setEditingAgent] = useState<AgentDefinition | null>(null);
  const [editingTask, setEditingTask] = useState<TaskDefinition | null>(null);
  const [editingCrew, setEditingCrew] = useState<CrewDefinition | null>(null);

  // Load initial data
  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const [crewConfig, tools] = await Promise.all([
        apiService.getCrewDefinitions(),
        apiService.getAvailableTools(),
      ]);
      setConfig(crewConfig);
      setAvailableTools(tools);
    } catch (error) {
      notifications.show({
        title: 'Error',
        message: `Failed to load crew definitions: ${error}`,
        color: 'red',
        icon: <IconAlertCircle size={16} />,
      });
    } finally {
      setLoading(false);
    }
  };

  const saveChanges = async () => {
    if (!config) return;

    try {
      setSaving(true);
      await apiService.updateCrewDefinitions(config);
      setHasChanges(false);
      notifications.show({
        title: 'Success',
        message: 'Crew definitions saved successfully',
        color: 'green',
        icon: <IconCheck size={16} />,
      });
    } catch (error) {
      notifications.show({
        title: 'Error',
        message: `Failed to save crew definitions: ${error}`,
        color: 'red',
        icon: <IconAlertCircle size={16} />,
      });
    } finally {
      setSaving(false);
    }
  };

  const handleEditAgent = (agent: AgentDefinition) => {
    setEditingAgent({ ...agent });
    openAgentModal();
  };

  const handleEditTask = (task: TaskDefinition) => {
    setEditingTask({ ...task });
    openTaskModal();
  };

  const handleEditCrew = (crew: CrewDefinition) => {
    setEditingCrew({ ...crew });
    openCrewModal();
  };

  const handleSaveAgent = () => {
    if (!editingAgent || !config) return;

    const updatedAgents = config.agents.map(agent =>
      agent.id === editingAgent.id ? editingAgent : agent
    );

    setConfig({ ...config, agents: updatedAgents });
    setHasChanges(true);
    closeAgentModal();
    setEditingAgent(null);
  };

  const handleSaveTask = () => {
    if (!editingTask || !config) return;

    const updatedTasks = config.tasks.map(task =>
      task.id === editingTask.id ? editingTask : task
    );

    setConfig({ ...config, tasks: updatedTasks });
    setHasChanges(true);
    closeTaskModal();
    setEditingTask(null);
  };

  const handleSaveCrew = () => {
    if (!editingCrew || !config) return;

    const updatedCrews = config.crews.map(crew =>
      crew.id === editingCrew.id ? editingCrew : crew
    );

    setConfig({ ...config, crews: updatedCrews });
    setHasChanges(true);
    closeCrewModal();
    setEditingCrew(null);
  };

  if (loading) {
    return (
      <Container size="xl" py="xl">
        <Group justify="center">
          <Loader size="lg" />
          <Text>Loading crew definitions...</Text>
        </Group>
      </Container>
    );
  }

  if (!config) {
    return (
      <Container size="xl" py="xl">
        <Alert icon={<IconAlertCircle size={16} />} title="Error" color="red">
          Failed to load crew definitions. Please try refreshing the page.
        </Alert>
      </Container>
    );
  }

  return (
    <Container size="xl" py="xl">
      <Group justify="space-between" mb="xl">
        <div>
          <Title order={1} size="h2" mb="xs">
            <Group gap="sm">
              <IconRobot size={32} />
              AI Crew Management
            </Group>
          </Title>
          <Text c="dimmed">
            Configure AI agents, tasks, and crew workflows for migration assessments
          </Text>
        </div>
        <Group>
          {hasChanges && (
            <Badge color="orange" variant="light">
              Unsaved Changes
            </Badge>
          )}
          <Button
            leftSection={<IconDeviceFloppy size={16} />}
            onClick={saveChanges}
            loading={saving}
            disabled={!hasChanges}
          >
            Save Changes
          </Button>
        </Group>
      </Group>

      <Tabs defaultValue="agents" variant="outline">
        <Tabs.List>
          <Tabs.Tab value="agents" leftSection={<IconUsers size={16} />}>
            Agents ({config.agents.length})
          </Tabs.Tab>
          <Tabs.Tab value="tasks" leftSection={<IconClipboardList size={16} />}>
            Tasks ({config.tasks.length})
          </Tabs.Tab>
          <Tabs.Tab value="crews" leftSection={<IconSettings size={16} />}>
            Crews ({config.crews.length})
          </Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="agents" pt="md">
          <Stack gap="md">
            {config.agents.map((agent) => (
              <Card key={agent.id} shadow="sm" padding="lg" radius="md" withBorder>
                <Group justify="space-between" mb="md">
                  <div>
                    <Text fw={600} size="lg">
                      {agent.role}
                    </Text>
                    <Text size="sm" c="dimmed">
                      ID: {agent.id}
                    </Text>
                  </div>
                  <ActionIcon
                    variant="light"
                    color="blue"
                    onClick={() => handleEditAgent(agent)}
                  >
                    <IconEdit size={16} />
                  </ActionIcon>
                </Group>

                <Text size="sm" mb="sm">
                  <strong>Goal:</strong> {agent.goal}
                </Text>

                <ScrollArea h={100} mb="sm">
                  <Text size="xs" c="dimmed">
                    <strong>Backstory:</strong> {agent.backstory}
                  </Text>
                </ScrollArea>

                <Group gap="xs" mb="sm">
                  <Text size="sm" fw={500}>Tools:</Text>
                  {agent.tools.map((tool) => (
                    <Badge key={tool} size="sm" variant="light">
                      {tool}
                    </Badge>
                  ))}
                </Group>

                <Group gap="md">
                  <Badge color={agent.allow_delegation ? 'green' : 'gray'} variant="light">
                    {agent.allow_delegation ? 'Can Delegate' : 'No Delegation'}
                  </Badge>
                  <Badge color={agent.verbose ? 'blue' : 'gray'} variant="light">
                    {agent.verbose ? 'Verbose' : 'Quiet'}
                  </Badge>
                </Group>
              </Card>
            ))}
          </Stack>
        </Tabs.Panel>

        <Tabs.Panel value="tasks" pt="md">
          <Stack gap="md">
            {config.tasks.map((task) => (
              <Card key={task.id} shadow="sm" padding="lg" radius="md" withBorder>
                <Group justify="space-between" mb="md">
                  <div>
                    <Text fw={600} size="lg">
                      {task.id.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                    </Text>
                    <Text size="sm" c="dimmed">
                      Assigned to: {task.agent}
                    </Text>
                  </div>
                  <ActionIcon
                    variant="light"
                    color="blue"
                    onClick={() => handleEditTask(task)}
                  >
                    <IconEdit size={16} />
                  </ActionIcon>
                </Group>

                <ScrollArea h={120} mb="sm">
                  <Text size="sm">
                    <strong>Description:</strong> {task.description}
                  </Text>
                </ScrollArea>

                <Text size="sm" c="dimmed">
                  <strong>Expected Output:</strong> {task.expected_output}
                </Text>
              </Card>
            ))}
          </Stack>
        </Tabs.Panel>

        <Tabs.Panel value="crews" pt="md">
          <Stack gap="md">
            {config.crews.map((crew) => (
              <Card key={crew.id} shadow="sm" padding="lg" radius="md" withBorder>
                <Group justify="space-between" mb="md">
                  <div>
                    <Text fw={600} size="lg">
                      {crew.name}
                    </Text>
                    <Text size="sm" c="dimmed">
                      {crew.description}
                    </Text>
                  </div>
                  <ActionIcon
                    variant="light"
                    color="blue"
                    onClick={() => handleEditCrew(crew)}
                  >
                    <IconEdit size={16} />
                  </ActionIcon>
                </Group>

                <Group gap="md" mb="sm">
                  <div>
                    <Text size="sm" fw={500}>Agents ({crew.agents.length}):</Text>
                    <Group gap="xs">
                      {crew.agents.map((agentId) => (
                        <Badge key={agentId} size="sm" variant="light" color="blue">
                          {agentId}
                        </Badge>
                      ))}
                    </Group>
                  </div>
                </Group>

                <Group gap="md" mb="sm">
                  <div>
                    <Text size="sm" fw={500}>Tasks ({crew.tasks.length}):</Text>
                    <Group gap="xs">
                      {crew.tasks.map((taskId) => (
                        <Badge key={taskId} size="sm" variant="light" color="green">
                          {taskId}
                        </Badge>
                      ))}
                    </Group>
                  </div>
                </Group>

                <Group gap="md">
                  <Badge color="orange" variant="light">
                    Process: {crew.process}
                  </Badge>
                  <Badge color={crew.memory ? 'purple' : 'gray'} variant="light">
                    {crew.memory ? 'Memory Enabled' : 'No Memory'}
                  </Badge>
                  <Badge color="cyan" variant="light">
                    Verbose: {crew.verbose}
                  </Badge>
                </Group>
              </Card>
            ))}
          </Stack>
        </Tabs.Panel>
      </Tabs>

      {/* Agent Edit Modal */}
      <Modal
        opened={agentModalOpened}
        onClose={closeAgentModal}
        title="Edit Agent"
        size="lg"
      >
        {editingAgent && (
          <Stack gap="md">
            <TextInput
              label="Role"
              value={editingAgent.role}
              onChange={(e) => setEditingAgent({ ...editingAgent, role: e.target.value })}
              required
            />
            <Textarea
              label="Goal"
              value={editingAgent.goal}
              onChange={(e) => setEditingAgent({ ...editingAgent, goal: e.target.value })}
              minRows={3}
              required
            />
            <Textarea
              label="Backstory"
              value={editingAgent.backstory}
              onChange={(e) => setEditingAgent({ ...editingAgent, backstory: e.target.value })}
              minRows={5}
              required
            />
            <MultiSelect
              label="Tools"
              data={availableTools.map(tool => ({ value: tool.id, label: tool.name }))}
              value={editingAgent.tools}
              onChange={(value) => setEditingAgent({ ...editingAgent, tools: value })}
            />
            <Group grow>
              <Switch
                label="Allow Delegation"
                checked={editingAgent.allow_delegation}
                onChange={(e) => setEditingAgent({ ...editingAgent, allow_delegation: e.target.checked })}
              />
              <Switch
                label="Verbose"
                checked={editingAgent.verbose}
                onChange={(e) => setEditingAgent({ ...editingAgent, verbose: e.target.checked })}
              />
            </Group>
            <Group justify="flex-end" mt="md">
              <Button variant="light" onClick={closeAgentModal}>
                Cancel
              </Button>
              <Button onClick={handleSaveAgent}>
                Save Agent
              </Button>
            </Group>
          </Stack>
        )}
      </Modal>

      {/* Task Edit Modal */}
      <Modal
        opened={taskModalOpened}
        onClose={closeTaskModal}
        title="Edit Task"
        size="lg"
      >
        {editingTask && (
          <Stack gap="md">
            <Textarea
              label="Description"
              value={editingTask.description}
              onChange={(e) => setEditingTask({ ...editingTask, description: e.target.value })}
              minRows={8}
              required
            />
            <Textarea
              label="Expected Output"
              value={editingTask.expected_output}
              onChange={(e) => setEditingTask({ ...editingTask, expected_output: e.target.value })}
              minRows={3}
              required
            />
            <Select
              label="Assigned Agent"
              data={config.agents.map(agent => ({ value: agent.id, label: agent.role }))}
              value={editingTask.agent}
              onChange={(value) => setEditingTask({ ...editingTask, agent: value || '' })}
              required
            />
            <Group justify="flex-end" mt="md">
              <Button variant="light" onClick={closeTaskModal}>
                Cancel
              </Button>
              <Button onClick={handleSaveTask}>
                Save Task
              </Button>
            </Group>
          </Stack>
        )}
      </Modal>

      {/* Crew Edit Modal */}
      <Modal
        opened={crewModalOpened}
        onClose={closeCrewModal}
        title="Edit Crew"
        size="lg"
      >
        {editingCrew && (
          <Stack gap="md">
            <TextInput
              label="Name"
              value={editingCrew.name}
              onChange={(e) => setEditingCrew({ ...editingCrew, name: e.target.value })}
              required
            />
            <Textarea
              label="Description"
              value={editingCrew.description}
              onChange={(e) => setEditingCrew({ ...editingCrew, description: e.target.value })}
              minRows={2}
            />
            <MultiSelect
              label="Agents"
              data={config.agents.map(agent => ({ value: agent.id, label: agent.role }))}
              value={editingCrew.agents}
              onChange={(value) => setEditingCrew({ ...editingCrew, agents: value })}
              required
            />
            <MultiSelect
              label="Tasks"
              data={config.tasks.map(task => ({ value: task.id, label: task.id }))}
              value={editingCrew.tasks}
              onChange={(value) => setEditingCrew({ ...editingCrew, tasks: value })}
              required
            />
            <Group grow>
              <Select
                label="Process"
                data={[
                  { value: 'sequential', label: 'Sequential' },
                  { value: 'hierarchical', label: 'Hierarchical' },
                ]}
                value={editingCrew.process}
                onChange={(value) => setEditingCrew({ ...editingCrew, process: value || 'sequential' })}
              />
              <NumberInput
                label="Verbose Level"
                value={editingCrew.verbose}
                onChange={(value) => setEditingCrew({ ...editingCrew, verbose: Number(value) || 0 })}
                min={0}
                max={3}
              />
            </Group>
            <Switch
              label="Enable Memory"
              checked={editingCrew.memory}
              onChange={(e) => setEditingCrew({ ...editingCrew, memory: e.target.checked })}
            />
            <Group justify="flex-end" mt="md">
              <Button variant="light" onClick={closeCrewModal}>
                Cancel
              </Button>
              <Button onClick={handleSaveCrew}>
                Save Crew
              </Button>
            </Group>
          </Stack>
        )}
      </Modal>
    </Container>
  );
}
