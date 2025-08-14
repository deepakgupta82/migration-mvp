import React, { useState, useEffect } from 'react';
import {
  Card,
  Grid,
  Text,
  Button,
  Select,
  TextInput,
  NumberInput,
  Group,
  Badge,
  Alert,
  Loader,
  Stack,
  Title,
  ActionIcon,
  Paper
} from '@mantine/core';
import {
  IconTestPipe,
  IconTrash,
  IconCheck,
  IconX,
  IconInfoCircle,
  IconRobot,
  IconBrain,
  IconSearch,
  IconFile,
  IconDatabase
} from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';

interface ProcessLLMConfigurationProps {
  projectId: string;
}

interface ProcessConfig {
  provider?: string;
  model?: string;
  temperature?: number;
  api_key?: string;
}

const ProcessLLMConfiguration: React.FC<ProcessLLMConfigurationProps> = ({ projectId }) => {
  const [configs, setConfigs] = useState<Record<string, ProcessConfig>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<Record<string, boolean>>({});
  const [testing, setTesting] = useState<Record<string, boolean>>({});

  const processTypes = [
    {
      key: 'entity_extraction',
      name: 'Entity Extraction',
      description: 'Extract infrastructure entities and relationships from documents',
      icon: IconFile,
      priority: 'High',
      color: 'red'
    },
    {
      key: 'crew_assessment', 
      name: 'CrewAI Assessment',
      description: 'Multi-agent infrastructure assessment and migration planning',
      icon: IconRobot,
      priority: 'High',
      color: 'red'
    },
    {
      key: 'crew_documentation',
      name: 'CrewAI Documentation', 
      description: 'Generate professional documentation and reports',
      icon: IconBrain,
      priority: 'Medium',
      color: 'yellow'
    },
    {
      key: 'rag_synthesis',
      name: 'RAG Synthesis',
      description: 'Synthesize search results into coherent responses',
      icon: IconSearch,
      priority: 'Medium', 
      color: 'yellow'
    },
    {
      key: 'hybrid_search',
      name: 'Hybrid Search',
      description: 'Generate Cypher queries for graph databases',
      icon: IconDatabase,
      priority: 'Low',
      color: 'green'
    }
  ];

  const providers = [
    { value: 'openai', label: 'OpenAI' },
    { value: 'anthropic', label: 'Anthropic' },
    { value: 'google', label: 'Google' },
    { value: 'ollama', label: 'Ollama (Local)' }
  ];

  const models: Record<string, string[]> = {
    openai: ['gpt-4o', 'gpt-4o-mini', 'gpt-3.5-turbo'],
    anthropic: ['claude-3-5-sonnet-20241022', 'claude-3-haiku-20240307'],
    google: ['gemini-pro', 'gemini-flash'],
    ollama: ['llama3', 'mistral', 'codellama']
  };

  useEffect(() => {
    loadConfigurations();
  }, [projectId]);

  const loadConfigurations = async () => {
    try {
      setLoading(true);
      const response = await fetch(`http://localhost:8000/api/projects/${projectId}/llm-process-configs`);
      if (response.ok) {
        const data = await response.json();
        setConfigs(data);
      }
    } catch (err) {
      console.error('Failed to load configurations:', err);
    } finally {
      setLoading(false);
    }
  };

  const updateConfig = (processType: string, field: string, value: any) => {
    setConfigs(prev => ({
      ...prev,
      [processType]: {
        ...prev[processType],
        [field]: value
      }
    }));
  };

  const saveConfiguration = async (processType: string) => {
    try {
      setSaving(prev => ({ ...prev, [processType]: true }));
      const config = configs[processType];
      
      const response = await fetch(`http://localhost:8000/api/projects/${projectId}/llm-process-configs/${processType}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });

      if (response.ok) {
        notifications.show({
          title: 'Configuration Saved',
          message: `${processTypes.find(p => p.key === processType)?.name} configuration updated successfully`,
          color: 'green',
          icon: <IconCheck size={16} />,
        });
      } else {
        throw new Error('Failed to save configuration');
      }
    } catch (err) {
      notifications.show({
        title: 'Save Failed',
        message: 'Failed to save configuration. Please try again.',
        color: 'red',
        icon: <IconX size={16} />,
      });
      console.error(err);
    } finally {
      setSaving(prev => ({ ...prev, [processType]: false }));
    }
  };

  const testConfiguration = async (processType: string) => {
    try {
      setTesting(prev => ({ ...prev, [processType]: true }));
      
      const response = await fetch(`http://localhost:8000/api/projects/${projectId}/llm-process-configs/${processType}/test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });

      if (response.ok) {
        const result = await response.json();
        
        if (result.success) {
          notifications.show({
            title: 'Test Successful',
            message: `${processTypes.find(p => p.key === processType)?.name} LLM is working correctly`,
            color: 'green',
            icon: <IconCheck size={16} />,
          });
        } else {
          notifications.show({
            title: 'Test Failed', 
            message: result.error || 'LLM test failed',
            color: 'red',
            icon: <IconX size={16} />,
          });
        }
      }
    } catch (err) {
      notifications.show({
        title: 'Test Error',
        message: 'Failed to test LLM configuration',
        color: 'red',
        icon: <IconX size={16} />,
      });
      console.error(err);
    } finally {
      setTesting(prev => ({ ...prev, [processType]: false }));
    }
  };

  const deleteConfiguration = async (processType: string) => {
    try {
      const response = await fetch(`http://localhost:8000/api/projects/${projectId}/llm-process-configs/${processType}`, {
        method: 'DELETE',
      });

      if (response.ok) {
        notifications.show({
          title: 'Configuration Deleted',
          message: `${processTypes.find(p => p.key === processType)?.name} will now use project default`,
          color: 'blue',
          icon: <IconCheck size={16} />,
        });
        loadConfigurations();
      }
    } catch (err) {
      notifications.show({
        title: 'Delete Failed',
        message: 'Failed to delete configuration',
        color: 'red',
        icon: <IconX size={16} />,
      });
      console.error(err);
    }
  };

  if (loading) {
    return (
      <Card>
        <Group justify="center" p="xl">
          <Loader size="lg" />
          <Text>Loading LLM configurations...</Text>
        </Group>
      </Card>
    );
  }

  return (
    <Stack gap="lg">
      <div>
        <Title order={2} mb="xs">Process-Specific LLM Configuration</Title>
        <Text size="sm" c="dimmed">
          Configure different LLM providers and models for each AI process to optimize cost and performance.
        </Text>
      </div>

      <Alert icon={<IconInfoCircle size={16} />} color="blue" variant="light">
        Each process can use a different LLM configuration. If not configured, the process will use the project default LLM settings.
      </Alert>

      <Grid>
        {processTypes.map((process) => {
          const ProcessIcon = process.icon;
          const config = configs[process.key] || {};
          const hasConfig = Object.keys(config).length > 0;

          return (
            <Grid.Col key={process.key} span={{ base: 12, md: 6 }}>
              <Card shadow="sm" padding="lg" radius="md" withBorder>
                <Group justify="space-between" mb="md">
                  <Group>
                    <ProcessIcon size={20} />
                    <div>
                      <Text fw={600}>{process.name}</Text>
                      <Text size="xs" c="dimmed">{process.description}</Text>
                    </div>
                  </Group>
                  <Badge color={process.color} variant="light" size="sm">
                    {process.priority}
                  </Badge>
                </Group>

                <Stack gap="sm">
                  <Select
                    label="Provider"
                    placeholder="Select LLM provider"
                    data={providers}
                    value={config.provider || ''}
                    onChange={(value) => updateConfig(process.key, 'provider', value)}
                  />

                  {config.provider && (
                    <Select
                      label="Model"
                      placeholder="Select model"
                      data={models[config.provider] || []}
                      value={config.model || ''}
                      onChange={(value) => updateConfig(process.key, 'model', value)}
                    />
                  )}

                  {config.provider && config.provider !== 'ollama' && (
                    <TextInput
                      label="API Key"
                      placeholder="Enter API key"
                      type="password"
                      value={config.api_key || ''}
                      onChange={(e) => updateConfig(process.key, 'api_key', e.target.value)}
                    />
                  )}

                  <NumberInput
                    label="Temperature"
                    placeholder="0.7"
                    min={0}
                    max={2}
                    step={0.1}
                    decimalScale={1}
                    value={config.temperature || 0.7}
                    onChange={(value) => updateConfig(process.key, 'temperature', value)}
                  />

                  <Group justify="space-between" mt="md">
                    <Group>
                      <Button
                        size="sm"
                        variant="filled"
                        loading={saving[process.key]}
                        disabled={!config.provider || !config.model}
                        onClick={() => saveConfiguration(process.key)}
                      >
                        Save
                      </Button>
                      <Button
                        size="sm"
                        variant="light"
                        leftSection={<IconTestPipe size={16} />}
                        loading={testing[process.key]}
                        disabled={!hasConfig}
                        onClick={() => testConfiguration(process.key)}
                      >
                        Test
                      </Button>
                    </Group>
                    {hasConfig && (
                      <ActionIcon
                        color="red"
                        variant="subtle"
                        onClick={() => deleteConfiguration(process.key)}
                      >
                        <IconTrash size={16} />
                      </ActionIcon>
                    )}
                  </Group>
                </Stack>
              </Card>
            </Grid.Col>
          );
        })}
      </Grid>

      <Paper p="md" withBorder>
        <Text fw={600} mb="xs">Cost Optimization Tips</Text>
        <Stack gap="xs">
          <Text size="sm">• Use <strong>Ollama</strong> for local development (free)</Text>
          <Text size="sm">• Use <strong>Google Gemini Flash</strong> for simple tasks (low cost)</Text>
          <Text size="sm">• Use <strong>GPT-4o-mini</strong> for complex tasks requiring accuracy</Text>
          <Text size="sm">• Use <strong>Claude Haiku</strong> for fast text processing</Text>
          <Text size="sm">• Reserve <strong>GPT-4o</strong> only for the most critical processes</Text>
        </Stack>
      </Paper>
    </Stack>
  );
};

export default ProcessLLMConfiguration;
