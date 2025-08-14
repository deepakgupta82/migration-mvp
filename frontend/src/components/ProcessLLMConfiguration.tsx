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
  Paper,
  Switch,
  Divider
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
  project?: any; // Project object containing default LLM configuration
}

interface ProcessConfig {
  provider?: string;
  model?: string;
  temperature?: number;
  api_key?: string;
  use_default?: boolean; // New field for inheritance
}

interface SavedLLMConfig {
  id: string;
  name: string;
  provider: string;
  model: string;
  config: Record<string, any>;
}

const ProcessLLMConfiguration: React.FC<ProcessLLMConfigurationProps> = ({ 
  projectId, 
  project 
}) => {
  const [configs, setConfigs] = useState<Record<string, ProcessConfig>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<Record<string, boolean>>({});
  const [testing, setTesting] = useState<Record<string, boolean>>({});
  const [savedConfigs, setSavedConfigs] = useState<SavedLLMConfig[]>([]);
  const [ollamaModels, setOllamaModels] = useState<string[]>([]);

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

  // Default project LLM configuration
  const defaultLLMConfig = project ? {
    provider: project.llm_provider,
    model: project.llm_model,
    temperature: project.llm_temperature || 0.1,
    api_key: project.llm_api_key || ''
  } : null;

  // Get available models based on provider from saved configurations
  const getAvailableModels = (provider: string): Array<{value: string, label: string}> => {
    let models: string[] = [];
    
    if (provider === 'ollama') {
      models = ollamaModels;
    } else {
      // Filter saved configurations by provider
      const providerConfigs = savedConfigs.filter(config => config.provider === provider);
      models = providerConfigs.map(config => config.model);
    }

    // Convert string array to Mantine Select format
    return models.map(model => ({ value: model, label: model }));
  };

  // Load saved LLM configurations from Settings
  const loadSavedConfigurations = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/llm/configurations');
      if (response.ok) {
        const configs = await response.json();
        setSavedConfigs(configs);
      }
    } catch (error) {
      console.error('Failed to load saved configurations:', error);
    }
  };

  // Load Ollama models
  const loadOllamaModels = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/ollama/models');
      if (response.ok) {
        const data = await response.json();
        setOllamaModels(data.models || []);
      }
    } catch (error) {
      console.error('Failed to load Ollama models:', error);
      // Don't show error notification as Ollama might not be running
    }
  };

  // Load existing configurations
  const loadConfigurations = async () => {
    try {
      const response = await fetch(`http://localhost:8000/api/projects/${projectId}/process-llm-config`);
      if (response.ok) {
        const data = await response.json();
        
        // Initialize configs with use_default=true for unset processes
        const initialConfigs: Record<string, ProcessConfig> = {};
        processTypes.forEach(process => {
          if (data[process.key]) {
            initialConfigs[process.key] = data[process.key];
            // If no explicit use_default field, determine it
            if (initialConfigs[process.key].use_default === undefined) {
              initialConfigs[process.key].use_default = !data[process.key].provider;
            }
          } else {
            // New process - use default configuration
            initialConfigs[process.key] = { use_default: true };
          }
        });
        
        setConfigs(initialConfigs);
      }
    } catch (error) {
      console.error('Failed to load configurations:', error);
      notifications.show({
        title: 'Error',
        message: 'Failed to load process configurations',
        color: 'red',
      });
    } finally {
      setLoading(false);
    }
  };

  // Save configuration for a specific process
  const saveConfiguration = async (processKey: string) => {
    const config = configs[processKey];
    if (!config) return;

    setSaving(prev => ({ ...prev, [processKey]: true }));

    try {
      let payload;
      
      if (config.use_default) {
        // Clear process-specific configuration to use defaults
        payload = {
          provider: null,
          model: null,
          temperature: null,
          api_key: null
        };
      } else {
        // Use process-specific configuration
        payload = {
          provider: config.provider,
          model: config.model,
          temperature: config.temperature || 0.1,
          api_key: config.api_key || ''
        };
      }

      const response = await fetch(
        `http://localhost:8000/api/projects/${projectId}/process-llm-config/${processKey}`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        }
      );

      if (response.ok) {
        notifications.show({
          title: 'Success',
          message: `Configuration saved for ${processTypes.find(p => p.key === processKey)?.name}`,
          color: 'green',
        });
      } else {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to save configuration');
      }
    } catch (error: any) {
      notifications.show({
        title: 'Error',
        message: error.message || 'Failed to save configuration',
        color: 'red',
      });
    } finally {
      setSaving(prev => ({ ...prev, [processKey]: false }));
    }
  };

  // Test configuration for a specific process
  const testConfiguration = async (processKey: string) => {
    const config = configs[processKey];
    if (!config) return;

    setTesting(prev => ({ ...prev, [processKey]: true }));

    try {
      if (config.use_default) {
        // For default configuration, let the backend handle it using project's LLM config
        if (!project?.llm_provider || !project?.llm_model) {
          throw new Error('Project does not have a default LLM configuration set');
        }

        const response = await fetch(
          `http://localhost:8000/api/projects/${projectId}/process-llm-config/${processKey}/test`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              use_project_default: true
            }),
          }
        );

        const result = await response.json();

        if (response.ok && result.success) {
          notifications.show({
            title: 'Test Successful',
            message: `${processTypes.find(p => p.key === processKey)?.name} configuration is working`,
            color: 'green',
          });
        } else {
          throw new Error(result.error || 'Test failed');
        }
      } else {
        // For process-specific configuration, send the details directly
        if (!config.provider || !config.model) {
          throw new Error('Provider and model are required for testing');
        }

        const response = await fetch(
          `http://localhost:8000/api/projects/${projectId}/process-llm-config/${processKey}/test`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              use_project_default: false,
              provider: config.provider,
              model: config.model,
              temperature: config.temperature || 0.1,
              api_key: config.api_key || ''
            }),
          }
        );

        const result = await response.json();

        if (response.ok && result.success) {
          notifications.show({
            title: 'Test Successful',
            message: `${processTypes.find(p => p.key === processKey)?.name} configuration is working`,
            color: 'green',
          });
        } else {
          throw new Error(result.error || 'Test failed');
        }
      }
    } catch (error: any) {
      notifications.show({
        title: 'Test Failed',
        message: error.message || 'Configuration test failed',
        color: 'red',
      });
    } finally {
      setTesting(prev => ({ ...prev, [processKey]: false }));
    }
  };

  // Update configuration
  const updateConfig = (processKey: string, field: string, value: any) => {
    setConfigs(prev => ({
      ...prev,
      [processKey]: {
        ...prev[processKey],
        [field]: value
      }
    }));
  };

  // Toggle inheritance
  const toggleInheritance = (processKey: string, useDefault: boolean) => {
    setConfigs(prev => ({
      ...prev,
      [processKey]: {
        ...prev[processKey],
        use_default: useDefault,
        // Clear specific settings when switching to default
        ...(useDefault ? { provider: undefined, model: undefined, temperature: undefined, api_key: undefined } : {})
      }
    }));
  };

  useEffect(() => {
    if (projectId) {
      Promise.all([
        loadConfigurations(),
        loadSavedConfigurations(),
        loadOllamaModels()
      ]);
    }
  }, [projectId]);

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: '2rem' }}>
        <Loader />
      </div>
    );
  }

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Title order={3}>Process-Specific LLM Configuration</Title>
        <Button
          variant="light"
          onClick={() => {
            loadConfigurations();
            loadSavedConfigurations();
            loadOllamaModels();
          }}
        >
          Refresh
        </Button>
      </Group>

      {defaultLLMConfig && (
        <Alert icon={<IconInfoCircle size={16} />} color="blue" variant="light">
          <Text size="sm">
            <strong>Default Project LLM:</strong> {defaultLLMConfig.provider?.toUpperCase()} / {defaultLLMConfig.model}
            <br />
            Processes can inherit this configuration or use their own settings.
          </Text>
        </Alert>
      )}

      <Grid>
        {processTypes.map((processType) => {
          const config = configs[processType.key] || { use_default: true };
          const isLoading = saving[processType.key] || testing[processType.key];
          const effectiveConfig = config.use_default ? defaultLLMConfig : config;

          return (
            <Grid.Col key={processType.key} span={6}>
              <Card shadow="sm" padding="lg" style={{ height: '100%' }}>
                <Group justify="space-between" mb="xs">
                  <Group>
                    <processType.icon size={20} />
                    <Text size="sm" fw={500}>{processType.name}</Text>
                  </Group>
                  <Badge color={processType.color} size="xs">
                    {processType.priority}
                  </Badge>
                </Group>

                <Text size="xs" color="dimmed" mb="md">
                  {processType.description}
                </Text>

                {/* Inheritance Toggle */}
                <Group mb="md">
                  <Switch
                    checked={!config.use_default}
                    onChange={(event) => toggleInheritance(processType.key, !event.currentTarget.checked)}
                    label="Use custom configuration"
                    description={config.use_default ? "Inheriting from project defaults" : "Using process-specific settings"}
                  />
                </Group>

                {config.use_default ? (
                  // Show inherited configuration
                  <Paper p="sm" withBorder bg="gray.0">
                    <Text size="xs" color="dimmed" mb="xs">Inherited Configuration:</Text>
                    {defaultLLMConfig ? (
                      <Stack gap="xs">
                        <Text size="sm"><strong>Provider:</strong> {defaultLLMConfig.provider}</Text>
                        <Text size="sm"><strong>Model:</strong> {defaultLLMConfig.model}</Text>
                        <Text size="sm"><strong>Temperature:</strong> {defaultLLMConfig.temperature}</Text>
                      </Stack>
                    ) : (
                      <Text size="sm" color="red">No default project LLM configured</Text>
                    )}
                  </Paper>
                ) : (
                  // Show process-specific configuration form
                  <Stack gap="xs">
                    <Select
                      label="Provider"
                      placeholder="Select provider"
                      data={providers}
                      value={config.provider || ''}
                      onChange={(value) => updateConfig(processType.key, 'provider', value)}
                      disabled={isLoading}
                    />

                    {config.provider && (
                      <Select
                        label="Model"
                        placeholder="Select model"
                        data={getAvailableModels(config.provider)}
                        value={config.model || ''}
                        onChange={(value) => updateConfig(processType.key, 'model', value)}
                        disabled={isLoading}
                      />
                    )}

                    <NumberInput
                      label="Temperature"
                      placeholder="0.1"
                      min={0}
                      max={2}
                      step={0.1}
                      value={config.temperature || 0.1}
                      onChange={(value) => updateConfig(processType.key, 'temperature', value)}
                      disabled={isLoading}
                    />

                    {config.provider !== 'ollama' && (
                      <TextInput
                        label="API Key"
                        placeholder="Optional - leave empty to use project default"
                        value={config.api_key || ''}
                        onChange={(event) => updateConfig(processType.key, 'api_key', event.target.value)}
                        disabled={isLoading}
                        type="password"
                      />
                    )}
                  </Stack>
                )}

                <Divider my="md" />

                <Group justify="space-between">
                  <Button
                    variant="outline"
                    leftSection={<IconTestPipe size={16} />}
                    onClick={() => testConfiguration(processType.key)}
                    loading={testing[processType.key]}
                    disabled={!effectiveConfig?.provider || !effectiveConfig?.model}
                    size="xs"
                  >
                    Test
                  </Button>

                  <Button
                    variant="filled"
                    onClick={() => saveConfiguration(processType.key)}
                    loading={saving[processType.key]}
                    size="xs"
                  >
                    Save
                  </Button>
                </Group>
              </Card>
            </Grid.Col>
          );
        })}
      </Grid>
    </Stack>
  );
};

export default ProcessLLMConfiguration;
