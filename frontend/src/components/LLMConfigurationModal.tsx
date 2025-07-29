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
  Title
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
  }, [provider]);

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
              <Select
                label="Model"
                placeholder="Select a model"
                value={model}
                onChange={(value) => setModel(value || '')}
                data={modelOptions[provider as keyof typeof modelOptions] || []}
                required
              />
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
