import React, { useState, useEffect } from 'react';
import {
  Modal,
  Stack,
  Select,
  Button,
  Group,
  Text,
  Alert,
  NumberInput,
  Divider,
  Badge,
  Card,
  Title,
  Loader
} from '@mantine/core';
import { IconInfoCircle, IconKey, IconBrain, IconSettings } from '@tabler/icons-react';
import { apiService } from '../services/api';

interface LLMConfig {
  provider: string;
  model: string;
  apiKeyId: string;
  temperature: number;
  maxTokens: number;
}

interface LLMConfigurationModalProps {
  opened: boolean;
  onClose: () => void;
  onConfirm: (config: LLMConfig) => void;
  projectId: string;
  currentConfig?: LLMConfig | null;
}

interface PlatformSetting {
  key: string;
  value: string;
  description?: string;
}

const LLMConfigurationModal: React.FC<LLMConfigurationModalProps> = ({
  opened,
  onClose,
  onConfirm,
  projectId,
  currentConfig
}) => {
  const [provider, setProvider] = useState<string>(currentConfig?.provider || 'openai');
  const [model, setModel] = useState<string>(currentConfig?.model || '');
  const [apiKeyId, setApiKeyId] = useState<string>(currentConfig?.apiKeyId || '');
  const [temperature, setTemperature] = useState<number>(currentConfig?.temperature || 0.1);
  const [maxTokens, setMaxTokens] = useState<number>(currentConfig?.maxTokens || 4000);
  const [availableKeys, setAvailableKeys] = useState<PlatformSetting[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fetchingModels, setFetchingModels] = useState(false);
  const [dynamicModels, setDynamicModels] = useState<{value: string, label: string}[]>([]);
  const [modelFetchTimeout, setModelFetchTimeout] = useState<NodeJS.Timeout | null>(null);

  // Model options for different providers
  const modelOptions = {
    openai: [
      { value: 'gpt-4o', label: 'GPT-4o (Latest)' },
      { value: 'gpt-4o-mini', label: 'GPT-4o Mini' },
      { value: 'gpt-4-turbo', label: 'GPT-4 Turbo' },
      { value: 'gpt-4', label: 'GPT-4' },
      { value: 'gpt-3.5-turbo', label: 'GPT-3.5 Turbo' }
    ],
    anthropic: [
      { value: 'claude-3-5-sonnet-latest', label: 'Claude 3.5 Sonnet (Latest)' },
      { value: 'claude-3-5-sonnet-20241022', label: 'Claude 3.5 Sonnet' },
      { value: 'claude-3-5-haiku-latest', label: 'Claude 3.5 Haiku (Latest)' },
      { value: 'claude-3-5-haiku-20241022', label: 'Claude 3.5 Haiku' },
      { value: 'claude-3-opus-latest', label: 'Claude 3 Opus (Latest)' }
    ],
    gemini: [
      { value: 'gemini-2.0-flash-exp', label: 'Gemini 2.0 Flash (Experimental)' },
      { value: 'gemini-1.5-pro-latest', label: 'Gemini 1.5 Pro (Latest)' },
      { value: 'gemini-1.5-flash-latest', label: 'Gemini 1.5 Flash (Latest)' },
      { value: 'gemini-1.5-pro', label: 'Gemini 1.5 Pro' },
      { value: 'gemini-1.5-flash', label: 'Gemini 1.5 Flash' },
      { value: 'gemini-pro', label: 'Gemini Pro' }
    ]
  };

  useEffect(() => {
    if (opened) {
      fetchAvailableKeys();
    }
  }, [opened]);

  useEffect(() => {
    // Set default model when provider changes
    if (provider && modelOptions[provider as keyof typeof modelOptions]) {
      const defaultModel = modelOptions[provider as keyof typeof modelOptions][0]?.value;
      if (defaultModel && !model) {
        setModel(defaultModel);
      }
    }
    // Clear dynamic models when provider changes
    setDynamicModels([]);
  }, [provider]);

  // Fetch dynamic models when API key is selected
  useEffect(() => {
    if (provider && apiKeyId && provider !== 'ollama') {
      fetchDynamicModels();
    }
  }, [provider, apiKeyId]);

  const fetchDynamicModels = async () => {
    if (!provider || !apiKeyId || provider === 'ollama') return;

    setFetchingModels(true);
    setError(null);

    // Set timeout for model fetching
    const timeout = setTimeout(() => {
      setFetchingModels(false);
      setError('Model fetching timed out. Using default models.');
    }, 15000); // 15 second timeout

    setModelFetchTimeout(timeout);

    try {
      // Get the actual API key value from platform settings
      const keySettings = await apiService.getPlatformSettings();
      const apiKeySetting = keySettings.find(setting => setting.key === apiKeyId);

      if (!apiKeySetting) {
        throw new Error('API key not found');
      }

      const response = await fetch(`http://localhost:8000/api/models/${provider}?api_key=${encodeURIComponent(apiKeySetting.value)}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const result = await response.json();
        if (result.status === 'success' && result.models && result.models.length > 0) {
          const models = result.models.map((model: any) => ({
            value: model.id,
            label: model.description || model.name || model.id
          }));
          setDynamicModels(models);

          // Set the first model as default if no model is selected
          if (!model && models.length > 0) {
            setModel(models[0].value);
          }
        } else {
          throw new Error(result.message || 'No models found');
        }
      } else {
        throw new Error(`Failed to fetch models: ${response.status}`);
      }
    } catch (err: any) {
      console.error('Error fetching dynamic models:', err);
      setError(`Failed to fetch models: ${err.message}`);
    } finally {
      if (modelFetchTimeout) {
        clearTimeout(modelFetchTimeout);
        setModelFetchTimeout(null);
      }
      setFetchingModels(false);
    }
  };

  const cancelModelFetch = () => {
    if (modelFetchTimeout) {
      clearTimeout(modelFetchTimeout);
      setModelFetchTimeout(null);
    }
    setFetchingModels(false);
    setError('Model fetching cancelled');
  };

  const fetchAvailableKeys = async () => {
    try {
      setLoading(true);

      // For testing purposes, use mock data until backend is fixed
      const mockSettings = [
        {
          key: 'OPENAI_API_KEY',
          value: 'sk-test-openai-key-12345',
          description: 'OpenAI API Key for GPT models'
        },
        {
          key: 'GEMINI_API_KEY',
          value: 'AIza-test-gemini-key-67890',
          description: 'Google Gemini API Key'
        },
        {
          key: 'ANTHROPIC_API_KEY',
          value: 'sk-ant-test-key-54321',
          description: 'Anthropic Claude API Key'
        }
      ];

      // Filter for API keys based on provider
      const keySettings = mockSettings.filter((setting: PlatformSetting) =>
        setting.key.toLowerCase().includes('api_key') ||
        setting.key.toLowerCase().includes('key')
      );

      setAvailableKeys(keySettings);
    } catch (err) {
      console.error('Error fetching API keys:', err);
      setError('Failed to fetch available API keys');
    } finally {
      setLoading(false);
    }
  };

  const handleConfirm = () => {
    if (!provider || !model || !apiKeyId) {
      setError('Please fill in all required fields');
      return;
    }

    const config: LLMConfig = {
      provider,
      model,
      apiKeyId,
      temperature,
      maxTokens
    };

    onConfirm(config);
  };

  const getProviderKeys = () => {
    return availableKeys.filter(key =>
      key.key.toLowerCase().includes(provider.toLowerCase())
    );
  };

  const getProviderBadgeColor = (provider: string) => {
    switch (provider) {
      case 'openai': return 'green';
      case 'anthropic': return 'violet';
      case 'gemini': return 'blue';
      case 'ollama': return 'orange';
      default: return 'gray';
    }
  };

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={
        <Group>
          <IconBrain size={24} />
          <Title order={3}>Configure LLM for Assessment</Title>
        </Group>
      }
      size="lg"
      centered
    >
      <Stack gap="md">
        {error && (
          <Alert icon={<IconInfoCircle size={16} />} color="red" onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        <Card withBorder p="md">
          <Stack gap="sm">
            <Group>
              <IconSettings size={20} />
              <Text fw={500}>Provider & Model Selection</Text>
            </Group>

            <Select
              label="LLM Provider"
              placeholder="Select a provider"
              value={provider}
              onChange={(value) => {
                setProvider(value || '');
                setModel(''); // Reset model when provider changes
                setApiKeyId(''); // Reset API key when provider changes
              }}
              data={[
                { value: 'openai', label: 'OpenAI' },
                { value: 'anthropic', label: 'Anthropic (Claude)' },
                { value: 'gemini', label: 'Google Gemini' },
                { value: 'ollama', label: 'Ollama (Local)' }
              ]}
              required
            />

            {provider && (
              <>
                <Select
                  label="Model"
                  placeholder={fetchingModels ? "Fetching models..." : "Select a model"}
                  value={model}
                  onChange={(value) => setModel(value || '')}
                  data={dynamicModels.length > 0 ? dynamicModels : (modelOptions[provider as keyof typeof modelOptions] || [])}
                  required
                  disabled={fetchingModels}
                  rightSection={fetchingModels ? (
                    <Group gap="xs">
                      <Loader size="xs" />
                      <Button size="xs" variant="subtle" onClick={cancelModelFetch}>
                        Cancel
                      </Button>
                    </Group>
                  ) : undefined}
                />

                {fetchingModels && (
                  <Alert icon={<IconInfoCircle size={16} />} color="blue">
                    Fetching available models from {provider}... This may take a few seconds.
                  </Alert>
                )}

                {dynamicModels.length > 0 && (
                  <Alert icon={<IconInfoCircle size={16} />} color="green">
                    Found {dynamicModels.length} models from {provider} API. Using live model list.
                  </Alert>
                )}
              </>
            )}

            {provider && model && (
              <Group>
                <Badge color={getProviderBadgeColor(provider)} variant="light">
                  {provider.toUpperCase()}
                </Badge>
                <Text size="sm" c="dimmed">{model}</Text>
              </Group>
            )}
          </Stack>
        </Card>

        <Card withBorder p="md">
          <Stack gap="sm">
            <Group>
              <IconKey size={20} />
              <Text fw={500}>API Key Selection</Text>
            </Group>

            {provider !== 'ollama' && (
              <Select
                label="API Key"
                placeholder="Select an API key"
                value={apiKeyId}
                onChange={(value) => setApiKeyId(value || '')}
                data={getProviderKeys().map(key => ({
                  value: key.key,
                  label: `${key.key} ${key.description ? `(${key.description})` : ''}`
                }))}
                required={provider !== 'ollama'}
                disabled={loading || getProviderKeys().length === 0}
              />
            )}

            {provider !== 'ollama' && getProviderKeys().length === 0 && (
              <Alert icon={<IconInfoCircle size={16} />} color="yellow">
                No API keys found for {provider}. Please configure API keys in Settings &gt; LLM Configuration.
              </Alert>
            )}

            {provider === 'ollama' && (
              <Alert icon={<IconInfoCircle size={16} />} color="blue">
                Ollama runs locally and doesn't require an API key.
              </Alert>
            )}
          </Stack>
        </Card>

        <Divider />

        <Group grow>
          <NumberInput
            label="Temperature"
            description="Controls randomness (0.0 = deterministic, 1.0 = creative)"
            value={temperature}
            onChange={(value) => setTemperature(typeof value === 'number' ? value : 0.1)}
            min={0}
            max={1}
            step={0.1}
            decimalScale={1}
          />

          <NumberInput
            label="Max Tokens"
            description="Maximum tokens in response"
            value={maxTokens}
            onChange={(value) => setMaxTokens(typeof value === 'number' ? value : 4000)}
            min={100}
            max={8000}
            step={100}
          />
        </Group>

        <Group justify="flex-end" mt="md">
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={handleConfirm}
            disabled={!provider || !model || (provider !== 'ollama' && !apiKeyId)}
            loading={loading}
          >
            Start Assessment
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
};

export default LLMConfigurationModal;
