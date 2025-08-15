/**
 * LLM Configuration Page - Full page for LLM settings
 * Moved from Settings tab to dedicated page
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Stack,
  Button,
  Group,
  Badge,
  Text,
  Card,
  TextInput,
  PasswordInput,
  Select,
  NumberInput,
  Textarea,
  ActionIcon,
  Modal,
  Alert,
  Table,
  Loader,
  Tooltip,
} from '@mantine/core';
import {
  IconBrain,
  IconPlus,
  IconRefresh,
  IconEdit,
  IconTrash,
  IconTestPipe,
  IconAlertCircle,
  IconCheck,
} from '@tabler/icons-react';

import { SettingsPageLayout } from '../../components/layout/SettingsPageLayout';
import { notifications } from '@mantine/notifications';
import { useLLMConfig } from '../../contexts/LLMConfigContext';

// Types (extracted from SettingsView)
interface LLMSettings {
  id?: string;
  provider: string;
  model: string;
  api_key?: string;
  temperature?: number;
  max_tokens?: number;
  base_url?: string;
  custom_endpoint?: string;
  ollama_host?: string;
  gemini_project_id?: string;
  name?: string;
  savedAt?: string;
  created_at?: string;
  status?: string;
  description?: string;
}

export const LLMConfigurationPage: React.FC = () => {
  const [modalOpened, setModalOpened] = useState(false);
  const [editingConfig, setEditingConfig] = useState<LLMSettings | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testingLLM, setTestingLLM] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<{[key: string]: any}>({});

  const { configurations: savedConfigurations, reloadConfigurations } = useLLMConfig();

  // LLM Configuration State
  const [llmSettings, setLlmSettings] = useState<LLMSettings>({
    provider: 'openai',
    model: 'gpt-4',
    api_key: '',
    temperature: 0.7,
    max_tokens: 4000,
    base_url: '',
    name: '',
    description: '',
  });

  const handleAddNew = () => {
    setEditingConfig(null);
    setLlmSettings({
      provider: 'openai',
      model: 'gpt-4',
      api_key: '',
      temperature: 0.7,
      max_tokens: 4000,
      base_url: '',
      name: '',
      description: '',
    });
    setModalOpened(true);
  };

  const handleEdit = (config: LLMSettings) => {
    setEditingConfig(config);
    setLlmSettings(config);
    setModalOpened(true);
  };

  const handleModalClose = () => {
    setModalOpened(false);
    setEditingConfig(null);
    reloadConfigurations();
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const url = editingConfig 
        ? `http://localhost:8000/api/llm/configurations/${editingConfig.id}`
        : 'http://localhost:8000/api/llm/configurations';
      
      const method = editingConfig ? 'PUT' : 'POST';
      
      const response = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(llmSettings),
      });

      if (response.ok) {
        notifications.show({
          title: 'Success',
          message: `LLM configuration ${editingConfig ? 'updated' : 'created'} successfully`,
          color: 'green',
          icon: <IconCheck size="1rem" />,
        });
        handleModalClose();
      } else {
        throw new Error('Failed to save configuration');
      }
    } catch (error) {
      notifications.show({
        title: 'Error',
        message: `Failed to ${editingConfig ? 'update' : 'create'} configuration`,
        color: 'red',
        icon: <IconAlertCircle size="1rem" />,
      });
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (configId: string) => {
    try {
      const response = await fetch(`http://localhost:8000/api/llm/configurations/${configId}`, {
        method: 'DELETE',
      });

      if (response.ok) {
        notifications.show({
          title: 'Success',
          message: 'Configuration deleted successfully',
          color: 'green',
          icon: <IconCheck size="1rem" />,
        });
        reloadConfigurations();
      } else {
        throw new Error('Failed to delete configuration');
      }
    } catch (error) {
      notifications.show({
        title: 'Error',
        message: 'Failed to delete configuration',
        color: 'red',
        icon: <IconAlertCircle size="1rem" />,
      });
    }
  };

  const handleTest = async (config: LLMSettings) => {
    const configId = config.id || config.name || 'test';
    setTestingLLM(configId);
    
    try {
      const response = await fetch('http://localhost:8000/api/llm/test', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(config),
      });

      const result = await response.json();
      setTestResults(prev => ({ ...prev, [configId]: result }));

      if (result.success) {
        notifications.show({
          title: 'Test Successful',
          message: 'LLM configuration is working correctly',
          color: 'green',
          icon: <IconCheck size="1rem" />,
        });
      } else {
        notifications.show({
          title: 'Test Failed',
          message: result.error || 'Failed to connect to LLM',
          color: 'red',
          icon: <IconAlertCircle size="1rem" />,
        });
      }
    } catch (error) {
      notifications.show({
        title: 'Test Error',
        message: 'Unable to test configuration',
        color: 'red',
        icon: <IconAlertCircle size="1rem" />,
      });
    } finally {
      setTestingLLM(null);
    }
  };

  const pageActions = (
    <Group gap="sm">
      <Button
        leftSection={<IconRefresh size="1rem" />}
        variant="light"
        onClick={reloadConfigurations}
        loading={loading}
      >
        Refresh
      </Button>
      <Button
        leftSection={<IconPlus size="1rem" />}
        onClick={handleAddNew}
      >
        Add LLM Configuration
      </Button>
    </Group>
  );

  const providerOptions = [
    { value: 'openai', label: 'OpenAI' },
    { value: 'anthropic', label: 'Anthropic (Claude)' },
    { value: 'google', label: 'Google (Gemini)' },
    { value: 'azure', label: 'Azure OpenAI' },
    { value: 'ollama', label: 'Ollama (Local)' },
    { value: 'custom', label: 'Custom Endpoint' },
  ];

  return (
    <>
      <SettingsPageLayout
        title="LLM Configuration"
        description="Manage AI language models, API keys, and model-specific configurations for the platform. Configure multiple providers and set process-specific LLM preferences."
        icon={<IconBrain size="1.5rem" />}
        breadcrumbText="LLM Configuration"
        actions={pageActions}
      >
        <Stack gap="xl">
          {/* Status overview */}
          <Group gap="lg">
            <Badge variant="light" size="lg">
              {savedConfigurations.length} Configuration{savedConfigurations.length !== 1 ? 's' : ''}
            </Badge>
            <Text size="sm" c="dimmed">
              Configure OpenAI, Anthropic, Google Gemini, and other AI providers
            </Text>
          </Group>

          {/* Configurations List */}
          {savedConfigurations.length === 0 ? (
            <Card p="xl" style={{ textAlign: 'center' }}>
              <Stack gap="md" align="center">
                <IconBrain size="3rem" color="gray" />
                <Text size="lg" fw={600}>No LLM Configurations</Text>
                <Text c="dimmed">Get started by adding your first LLM configuration</Text>
                <Button
                  leftSection={<IconPlus size="1rem" />}
                  onClick={handleAddNew}
                >
                  Add First Configuration
                </Button>
              </Stack>
            </Card>
          ) : (
            <Table>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Name</Table.Th>
                  <Table.Th>Provider</Table.Th>
                  <Table.Th>Model</Table.Th>
                  <Table.Th>Status</Table.Th>
                  <Table.Th>Actions</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {savedConfigurations.map((config) => {
                  const configId = config.id || config.name || 'unknown';
                  const testResult = testResults[configId];
                  const isTesting = testingLLM === configId;

                  return (
                    <Table.Tr key={configId}>
                      <Table.Td>
                        <Group gap="sm">
                          <Text fw={500}>{config.name || 'Unnamed'}</Text>
                          {config.description && (
                            <Text size="xs" c="dimmed">
                              {config.description}
                            </Text>
                          )}
                        </Group>
                      </Table.Td>
                      <Table.Td>
                        <Badge variant="light">
                          {config.provider.toUpperCase()}
                        </Badge>
                      </Table.Td>
                      <Table.Td>
                        <Text size="sm">{config.model}</Text>
                      </Table.Td>
                      <Table.Td>
                        {isTesting ? (
                          <Group gap="xs">
                            <Loader size="xs" />
                            <Text size="sm" c="dimmed">Testing...</Text>
                          </Group>
                        ) : testResult ? (
                          <Badge color={testResult.success ? 'green' : 'red'}>
                            {testResult.success ? 'Working' : 'Error'}
                          </Badge>
                        ) : (
                          <Badge color="gray">Unknown</Badge>
                        )}
                      </Table.Td>
                      <Table.Td>
                        <Group gap="xs">
                          <Tooltip label="Test Connection">
                            <ActionIcon
                              variant="light"
                              onClick={() => handleTest(config)}
                              loading={isTesting}
                            >
                              <IconTestPipe size="1rem" />
                            </ActionIcon>
                          </Tooltip>
                          <Tooltip label="Edit">
                            <ActionIcon
                              variant="light"
                              onClick={() => handleEdit(config)}
                            >
                              <IconEdit size="1rem" />
                            </ActionIcon>
                          </Tooltip>
                          <Tooltip label="Delete">
                            <ActionIcon
                              variant="light"
                              color="red"
                              onClick={() => handleDelete(config.id!)}
                            >
                              <IconTrash size="1rem" />
                            </ActionIcon>
                          </Tooltip>
                        </Group>
                      </Table.Td>
                    </Table.Tr>
                  );
                })}
              </Table.Tbody>
            </Table>
          )}
        </Stack>
      </SettingsPageLayout>

      {/* Configuration Modal */}
      <Modal
        opened={modalOpened}
        onClose={handleModalClose}
        title={`${editingConfig ? 'Edit' : 'Add'} LLM Configuration`}
        size="lg"
      >
        <Stack gap="md">
          <Group grow>
            <TextInput
              label="Configuration Name"
              placeholder="My OpenAI Config"
              value={llmSettings.name || ''}
              onChange={(e) => setLlmSettings(prev => ({ ...prev, name: e.target.value }))}
              required
            />
            <Select
              label="Provider"
              value={llmSettings.provider}
              onChange={(value) => setLlmSettings(prev => ({ ...prev, provider: value || 'openai' }))}
              data={providerOptions}
              required
            />
          </Group>

          <Group grow>
            <TextInput
              label="Model"
              placeholder="gpt-4, claude-3, etc."
              value={llmSettings.model}
              onChange={(e) => setLlmSettings(prev => ({ ...prev, model: e.target.value }))}
              required
            />
            <NumberInput
              label="Max Tokens"
              value={llmSettings.max_tokens}
              onChange={(value) => setLlmSettings(prev => ({ ...prev, max_tokens: Number(value) || 4000 }))}
              min={100}
              max={32000}
            />
          </Group>

          <PasswordInput
            label="API Key"
            placeholder="Enter your API key"
            value={llmSettings.api_key || ''}
            onChange={(e) => setLlmSettings(prev => ({ ...prev, api_key: e.target.value }))}
          />

          {(llmSettings.provider === 'custom' || llmSettings.provider === 'azure') && (
            <TextInput
              label="Base URL"
              placeholder="https://api.example.com/v1"
              value={llmSettings.base_url || ''}
              onChange={(e) => setLlmSettings(prev => ({ ...prev, base_url: e.target.value }))}
            />
          )}

          <NumberInput
            label="Temperature"
            description="Controls randomness (0.0 = deterministic, 1.0 = creative)"
            value={llmSettings.temperature}
            onChange={(value) => setLlmSettings(prev => ({ ...prev, temperature: Number(value) || 0.7 }))}
            min={0}
            max={2}
            step={0.1}
            decimalScale={1}
          />

          <Textarea
            label="Description"
            placeholder="Optional description for this configuration"
            value={llmSettings.description || ''}
            onChange={(e) => setLlmSettings(prev => ({ ...prev, description: e.target.value }))}
            minRows={2}
          />

          <Group justify="flex-end" mt="md">
            <Button variant="light" onClick={handleModalClose}>
              Cancel
            </Button>
            <Button onClick={handleSave} loading={saving}>
              {editingConfig ? 'Update' : 'Create'}
            </Button>
          </Group>
        </Stack>
      </Modal>
    </>
  );
};
