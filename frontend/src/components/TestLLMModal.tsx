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
  Textarea,
  Code,
  Loader
} from '@mantine/core';
import { IconInfoCircle, IconKey, IconBrain, IconSettings, IconTestPipe, IconCheck, IconX } from '@tabler/icons-react';
import { apiService } from '../services/api';

interface TestLLMConfig {
  provider: string;
  model: string;
  apiKeyId: string;
  temperature: number;
  maxTokens: number;
}

interface TestLLMModalProps {
  opened: boolean;
  onClose: () => void;
  projectId: string;
}

interface PlatformSetting {
  key: string;
  value: string;
  description?: string;
}

interface TestResult {
  status: string;
  provider: string;
  model: string;
  response?: string;
  error?: string;
  message: string;
}

const TestLLMModal: React.FC<TestLLMModalProps> = ({
  opened,
  onClose,
  projectId
}) => {
  const [provider, setProvider] = useState<string>('openai');
  const [model, setModel] = useState<string>('');
  const [apiKeyId, setApiKeyId] = useState<string>('');
  const [temperature, setTemperature] = useState<number>(0.1);
  const [maxTokens, setMaxTokens] = useState<number>(4000);
  const [availableKeys, setAvailableKeys] = useState<PlatformSetting[]>([]);
  const [loading, setLoading] = useState(false);
  const [testing, setTesting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<TestResult | null>(null);

  // Model options for each provider
  const modelOptions = {
    openai: [
      { value: 'gpt-4o', label: 'GPT-4o (Latest)' },
      { value: 'gpt-4o-mini', label: 'GPT-4o Mini' },
      { value: 'gpt-4-turbo', label: 'GPT-4 Turbo' },
      { value: 'gpt-4', label: 'GPT-4' },
      { value: 'gpt-3.5-turbo', label: 'GPT-3.5 Turbo' }
    ],
    anthropic: [
      { value: 'claude-3-5-sonnet-20241022', label: 'Claude 3.5 Sonnet (Latest)' },
      { value: 'claude-3-5-haiku-20241022', label: 'Claude 3.5 Haiku' },
      { value: 'claude-3-opus-20240229', label: 'Claude 3 Opus' },
      { value: 'claude-3-sonnet-20240229', label: 'Claude 3 Sonnet' }
    ],
    gemini: [
      { value: 'gemini-2.0-flash-exp', label: 'Gemini 2.0 Flash (Experimental)' },
      { value: 'gemini-1.5-pro', label: 'Gemini 1.5 Pro' },
      { value: 'gemini-1.5-flash', label: 'Gemini 1.5 Flash' },
      { value: 'gemini-pro', label: 'Gemini Pro' }
    ],
    ollama: [
      { value: 'llama2', label: 'Llama 2' },
      { value: 'llama3', label: 'Llama 3' },
      { value: 'codellama', label: 'Code Llama' },
      { value: 'mistral', label: 'Mistral' }
    ]
  };

  useEffect(() => {
    if (opened) {
      fetchAvailableKeys();
      // Set default model when provider changes
      const defaultModel = modelOptions[provider as keyof typeof modelOptions]?.[0]?.value || '';
      setModel(defaultModel);
      setApiKeyId('');
      setTestResult(null);
      setError(null);
    }
  }, [opened, provider]);

  const fetchAvailableKeys = async () => {
    setLoading(true);
    try {
      // Get real API keys from backend settings
      try {
        const response = await fetch('http://localhost:8000/platform-settings');
        if (response.ok) {
          const settings = await response.json();
          setAvailableKeys(settings);
        } else {
          setError('No API keys configured. Please configure API keys in Settings > LLM Configuration.');
          setAvailableKeys([]);
        }
      } catch (fetchError) {
        setError('Failed to load API key configuration. Please configure API keys in Settings > LLM Configuration.');
        setAvailableKeys([]);
      }
    } catch (err) {
      console.error('Error setting up API keys:', err);
      setError('Failed to initialize API keys');
    } finally {
      setLoading(false);
    }
  };

  const handleTest = async () => {
    if (!provider || !model) {
      setError('Please select provider and model');
      return;
    }

    setTesting(true);
    setError(null);
    setTestResult(null);

    try {
      console.log('Testing LLM with:', { provider, model, apiKeyId });

      // Test the LLM directly using the new endpoint
      const result = await apiService.testLLM(provider, model, apiKeyId);
      console.log('Test result:', result);

      setTestResult(result);

      if (result.status === 'success') {
        // Optionally update the project with the working configuration
        try {
          await apiService.updateProject(projectId, {
            llm_provider: provider,
            llm_model: model,
            llm_api_key_id: apiKeyId,
            llm_temperature: temperature.toString(),
            llm_max_tokens: maxTokens.toString()
          });
          console.log('Project updated with working LLM configuration');
        } catch (updateError) {
          console.warn('Could not update project with LLM config:', updateError);
          // Don't fail the test if project update fails
        }
      }
    } catch (error) {
      console.error('LLM test error:', error);
      setError(`Test failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setTesting(false);
    }
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

  const getResultIcon = () => {
    if (!testResult) return null;
    return testResult.status === 'success' ?
      <IconCheck size={20} color="green" /> :
      <IconX size={20} color="red" />;
  };

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={
        <Group>
          <IconTestPipe size={24} />
          <Title order={3}>Test LLM Configuration</Title>
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

            <Select
              label="Model"
              placeholder="Select a model"
              value={model}
              onChange={(value) => setModel(value || '')}
              data={modelOptions[provider as keyof typeof modelOptions] || []}
              required
              disabled={!provider}
            />

            <Group>
              <Badge color={getProviderBadgeColor(provider)} variant="light">
                {provider.toUpperCase()}
              </Badge>
              {model && (
                <Badge variant="outline">
                  {model}
                </Badge>
              )}
            </Group>
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

        {testResult && (
          <Card withBorder p="md" style={{ backgroundColor: testResult.status === 'success' ? '#f0f9ff' : '#fef2f2' }}>
            <Stack gap="sm">
              <Group>
                {getResultIcon()}
                <Text fw={500}>Test Result</Text>
                <Badge color={testResult.status === 'success' ? 'green' : 'red'}>
                  {testResult.status.toUpperCase()}
                </Badge>
              </Group>

              <Text size="sm">
                <strong>Provider:</strong> {testResult.provider} | <strong>Model:</strong> {testResult.model}
              </Text>

              <Text size="sm">
                <strong>Message:</strong> {testResult.message}
              </Text>

              {testResult.response && (
                <div>
                  <Text size="sm" fw={500} mb="xs">Response:</Text>
                  <Code block>
                    {testResult.response}
                  </Code>
                </div>
              )}

              {testResult.error && (
                <div>
                  <Text size="sm" fw={500} mb="xs" c="red">Error:</Text>
                  <Code block color="red">
                    {testResult.error}
                  </Code>
                </div>
              )}
            </Stack>
          </Card>
        )}

        <Group justify="flex-end" mt="md">
          <Button variant="outline" onClick={onClose}>
            Close
          </Button>
          <Button
            leftSection={testing ? <Loader size="sm" /> : <IconTestPipe size={16} />}
            onClick={handleTest}
            disabled={!provider || !model || (provider !== 'ollama' && !apiKeyId) || testing}
            loading={testing}
            color="blue"
          >
            {testing ? 'Testing...' : 'Test LLM'}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
};

export default TestLLMModal;
