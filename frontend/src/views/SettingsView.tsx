/**
 * Settings View - Comprehensive configuration management
 * Includes LLM settings, OAuth configuration, user management, and environment variables
 */

import React, { useState, useEffect } from 'react';
import {
  Container,
  Tabs,
  Card,
  Text,
  Group,
  Stack,
  TextInput,
  PasswordInput,
  Select,
  Switch,
  Button,
  Divider,
  Alert,
  Table,
  ActionIcon,
  Modal,
  NumberInput,
  Textarea,
  Badge,
  Title,
  Box,
  Grid,
  Loader,
} from '@mantine/core';
import {
  IconSettings,
  IconRobot,
  IconUsers,
  IconShield,
  IconDatabase,
  IconCloud,
  IconKey,
  IconEdit,
  IconTrash,
  IconPlus,
  IconAlertCircle,
  IconCheck,
  IconBrandOauth,
  IconMessage,
  IconTestPipe,
  IconX,
  IconServer,
  IconFileText,
} from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';
import ServiceStatusPanel from '../components/settings/ServiceStatusPanel';
import EnvironmentVariablesPanel from '../components/settings/EnvironmentVariablesPanel';
import GlobalDocumentTemplates from '../components/settings/GlobalDocumentTemplates';

// Types
interface LLMSettings {
  id?: string;  // Added for backend compatibility
  provider: string;
  model: string;
  api_key: string;
  temperature: number;
  max_tokens: number;
  base_url?: string;
  custom_endpoint?: string;
  ollama_host?: string;
  gemini_project_id?: string;
  name?: string;
  savedAt?: string;
  created_at?: string;  // Added for backend compatibility
  status?: string;  // Added for backend compatibility
  description?: string;  // Added for backend compatibility
}

interface OAuthSettings {
  enabled: boolean;
  provider: string;
  client_id: string;
  client_secret: string;
  redirect_uri: string;
  scopes: string[];
}

interface User {
  id: string;
  username: string;
  email: string;
  role: string;
  status: string;
  created_at: string;
}

interface EnvironmentVariable {
  key: string;
  value: string;
  description: string;
  category: string;
}

export const SettingsView: React.FC = () => {
  // State management
  const [activeTab, setActiveTab] = useState<string>('llm');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [userModalOpened, setUserModalOpened] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [savedConfigurations, setSavedConfigurations] = useState<LLMSettings[]>([]);
  const [testingLLM, setTestingLLM] = useState<string | null>(null); // Track which config is being tested
  const [testResults, setTestResults] = useState<{[key: string]: any}>({}); // Store test results for each config

  // LLM Settings State
  const [llmSettings, setLlmSettings] = useState<LLMSettings>({
    provider: 'openai',
    model: 'gpt-4',
    api_key: '',
    temperature: 0.7,
    max_tokens: 4000,
    base_url: '',
    custom_endpoint: '',
    ollama_host: 'http://localhost:11434',
    gemini_project_id: '',
    name: '',
  });
  const [availableModels, setAvailableModels] = useState<any[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);

  // OAuth Settings State
  const [oauthSettings, setOauthSettings] = useState<OAuthSettings>({
    enabled: false,
    provider: 'azure',
    client_id: '',
    client_secret: '',
    redirect_uri: '',
    scopes: ['openid', 'profile', 'email'],
  });

  // Users State
  const [users, setUsers] = useState<User[]>([
    {
      id: '1',
      username: 'admin',
      email: 'admin@nagarro.com',
      role: 'admin',
      status: 'active',
      created_at: '2024-01-01T00:00:00Z',
    },
  ]);

  // Environment Variables State
  const [envVars, setEnvVars] = useState<EnvironmentVariable[]>([
    {
      key: 'OPENAI_API_KEY',
      value: '***hidden***',
      description: 'OpenAI API key for LLM operations',
      category: 'LLM',
    },
    {
      key: 'DATABASE_URL',
      value: '***hidden***',
      description: 'PostgreSQL database connection string',
      category: 'Database',
    },
    {
      key: 'MINIO_ENDPOINT',
      value: 'localhost:9000',
      description: 'MinIO object storage endpoint',
      category: 'Storage',
    },
  ]);

  // New user form state
  const [newUser, setNewUser] = useState({
    username: '',
    email: '',
    password: '',
    role: 'user',
  });

  // Helper function to get model options based on provider
  const getModelOptions = (provider: string) => {
    switch (provider) {
      case 'openai':
        return [
          { value: 'gpt-4o', label: 'GPT-4o (Latest)' },
          { value: 'gpt-4o-2024-08-06', label: 'GPT-4o (2024-08-06)' },
          { value: 'gpt-4o-2024-05-13', label: 'GPT-4o (2024-05-13)' },
          { value: 'gpt-4o-mini', label: 'GPT-4o Mini' },
          { value: 'gpt-4-turbo', label: 'GPT-4 Turbo (Latest)' },
          { value: 'gpt-4-turbo-2024-04-09', label: 'GPT-4 Turbo (2024-04-09)' },
          { value: 'gpt-4', label: 'GPT-4' },
          { value: 'gpt-4-0613', label: 'GPT-4 (0613)' },
          { value: 'gpt-3.5-turbo', label: 'GPT-3.5 Turbo (Latest)' },
          { value: 'gpt-3.5-turbo-0125', label: 'GPT-3.5 Turbo (0125)' },
        ];
      case 'azure':
        return [
          { value: 'gpt-4', label: 'GPT-4' },
          { value: 'gpt-4-turbo', label: 'GPT-4 Turbo' },
          { value: 'gpt-35-turbo', label: 'GPT-3.5 Turbo' },
        ];
      case 'anthropic':
        return [
          { value: 'claude-3-5-sonnet-20241022', label: 'Claude 3.5 Sonnet (Latest)' },
          { value: 'claude-3-5-sonnet-20240620', label: 'Claude 3.5 Sonnet (June)' },
          { value: 'claude-3-5-haiku-20241022', label: 'Claude 3.5 Haiku (Latest)' },
          { value: 'claude-3-opus-20240229', label: 'Claude 3 Opus' },
          { value: 'claude-3-sonnet-20240229', label: 'Claude 3 Sonnet' },
          { value: 'claude-3-haiku-20240307', label: 'Claude 3 Haiku' },
        ];
      case 'gemini':
        return [
          // Latest Gemini 2.5 Models
          { value: 'gemini-2.5-pro', label: 'Gemini 2.5 Pro (Latest)' },
          { value: 'gemini-2.5-flash', label: 'Gemini 2.5 Flash (Latest)' },
          { value: 'gemini-2.5-flash-lite', label: 'Gemini 2.5 Flash Lite' },
          { value: 'gemini-2.5-flash-preview-05-20', label: 'Gemini 2.5 Flash Preview' },
          { value: 'gemini-live-2.5-flash-preview', label: 'Gemini 2.5 Flash Live' },

          // Gemini 2.0 Models
          { value: 'gemini-2.0-flash', label: 'Gemini 2.0 Flash' },
          { value: 'gemini-2.0-flash-001', label: 'Gemini 2.0 Flash (001)' },
          { value: 'gemini-2.0-flash-exp', label: 'Gemini 2.0 Flash (Experimental)' },
          { value: 'gemini-2.0-flash-lite', label: 'Gemini 2.0 Flash Lite' },
          { value: 'gemini-2.0-flash-live-001', label: 'Gemini 2.0 Flash Live' },

          // Gemini 1.5 Models (Deprecated but still available)
          { value: 'gemini-1.5-pro', label: 'Gemini 1.5 Pro (Deprecated)' },
          { value: 'gemini-1.5-pro-001', label: 'Gemini 1.5 Pro (001)' },
          { value: 'gemini-1.5-pro-002', label: 'Gemini 1.5 Pro (002)' },
          { value: 'gemini-1.5-flash', label: 'Gemini 1.5 Flash (Deprecated)' },
          { value: 'gemini-1.5-flash-001', label: 'Gemini 1.5 Flash (001)' },
          { value: 'gemini-1.5-flash-002', label: 'Gemini 1.5 Flash (002)' },
          { value: 'gemini-1.5-flash-8b', label: 'Gemini 1.5 Flash 8B (Deprecated)' },
        ];
      case 'ollama':
        return [
          { value: 'llama3.2', label: 'Llama 3.2 (Latest)' },
          { value: 'llama3.2:3b', label: 'Llama 3.2 3B' },
          { value: 'llama3.2:1b', label: 'Llama 3.2 1B' },
          { value: 'llama3.1', label: 'Llama 3.1' },
          { value: 'llama3.1:8b', label: 'Llama 3.1 8B' },
          { value: 'llama3.1:70b', label: 'Llama 3.1 70B' },
          { value: 'llama3', label: 'Llama 3' },
          { value: 'llama3:8b', label: 'Llama 3 8B' },
          { value: 'llama3:70b', label: 'Llama 3 70B' },
          { value: 'llama2', label: 'Llama 2' },
          { value: 'llama2:13b', label: 'Llama 2 13B' },
          { value: 'llama2:70b', label: 'Llama 2 70B' },
          { value: 'codellama', label: 'Code Llama' },
          { value: 'codellama:13b', label: 'Code Llama 13B' },
          { value: 'codellama:34b', label: 'Code Llama 34B' },
          { value: 'mistral', label: 'Mistral 7B' },
          { value: 'mistral-nemo', label: 'Mistral Nemo' },
          { value: 'mixtral', label: 'Mixtral 8x7B' },
          { value: 'mixtral:8x22b', label: 'Mixtral 8x22B' },
          { value: 'qwen2.5', label: 'Qwen 2.5' },
          { value: 'qwen2.5:14b', label: 'Qwen 2.5 14B' },
          { value: 'qwen2.5:32b', label: 'Qwen 2.5 32B' },
          { value: 'gemma2', label: 'Gemma 2' },
          { value: 'gemma2:9b', label: 'Gemma 2 9B' },
          { value: 'gemma2:27b', label: 'Gemma 2 27B' },
          { value: 'phi3', label: 'Phi-3' },
          { value: 'phi3:14b', label: 'Phi-3 14B' },
          { value: 'neural-chat', label: 'Neural Chat' },
          { value: 'starling-lm', label: 'Starling LM' },
          { value: 'orca-mini', label: 'Orca Mini' },
          { value: 'vicuna', label: 'Vicuna' },
        ];
      case 'custom':
        return [
          { value: 'custom-model', label: 'Custom Model' },
        ];
      default:
        return [
          { value: 'gpt-4', label: 'GPT-4' },
        ];
    }
  };

  // Load saved configurations from backend API
  useEffect(() => {
    const loadSavedConfigurations = async () => {
      try {
        const response = await fetch('http://localhost:8000/llm-configurations');
        if (response.ok) {
          const configs = await response.json();
          setSavedConfigurations(configs);
        }
      } catch (error) {
        console.error('Failed to load LLM configurations:', error);
        // Fallback to localStorage for backward compatibility
        const saved = localStorage.getItem('llm_configurations');
        if (saved) {
          setSavedConfigurations(JSON.parse(saved));
        }
      }
    };
    loadSavedConfigurations();
  }, []);

  // Clear models when provider changes to non-dynamic providers
  useEffect(() => {
    if (llmSettings.provider && llmSettings.provider !== 'openai' && llmSettings.provider !== 'gemini') {
      setAvailableModels([]);
    }
  }, [llmSettings.provider]);

  // Handlers
  const handleSaveLLMSettings = async () => {
    if (!llmSettings.name) {
      notifications.show({
        title: 'Validation Error',
        message: 'Please provide a name for this configuration',
        color: 'orange',
      });
      return;
    }

    setSaving(true);
    try {
      // Use the provided name or generate one
      const configToSave = { ...llmSettings, savedAt: new Date().toISOString() };

      // Save to backend API
      const response = await fetch('http://localhost:8000/llm-configurations', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(configToSave),
      });

      if (response.ok) {
        const savedConfig = await response.json();

        // Reload configurations from backend to get updated list
        const configsResponse = await fetch('http://localhost:8000/llm-configurations');
        if (configsResponse.ok) {
          const configs = await configsResponse.json();
          setSavedConfigurations(configs);
        }

        notifications.show({
          title: 'Configuration Saved!',
          message: `${llmSettings.name} configuration saved successfully`,
          color: 'green',
          icon: <IconCheck size={16} />,
          autoClose: 3000,
        });

        // Reset form
        setLlmSettings({
          provider: 'openai',
          model: 'gpt-4',
          api_key: '',
          temperature: 0.7,
          max_tokens: 4000,
          base_url: '',
          custom_endpoint: '',
          ollama_host: 'http://localhost:11434',
          gemini_project_id: '',
          name: '',
        });
      } else {
        throw new Error('Failed to save configuration');
      }
    } catch (error) {
      notifications.show({
        title: 'Error',
        message: 'Failed to save LLM settings',
        color: 'red',
        autoClose: 5000,
      });
    } finally {
      setSaving(false);
    }
  };

  const handleLoadConfiguration = (config: LLMSettings) => {
    setLlmSettings(config);
    notifications.show({
      title: 'Configuration Loaded',
      message: `Loaded ${config.provider} ${config.model} configuration`,
      color: 'blue',
      icon: <IconCheck size={16} />,
    });
  };

  const handleEditConfiguration = (config: LLMSettings) => {
    // Load the configuration into the form for editing
    setLlmSettings({
      ...config,
      // Ensure all required fields are present
      name: config.name || `${config.provider} ${config.model}`,
      provider: config.provider || 'openai',
      model: config.model || 'gpt-4',
      api_key: config.api_key || '',
      temperature: config.temperature || 0.7,
      max_tokens: config.max_tokens || 4000,
      base_url: config.base_url || '',
      custom_endpoint: config.custom_endpoint || '',
      ollama_host: config.ollama_host || 'http://localhost:11434',
      gemini_project_id: config.gemini_project_id || ''
    });

    // Load models for the selected provider
    loadModelsForProvider(config.provider, config.api_key);

    notifications.show({
      title: 'Configuration Loaded for Editing',
      message: `${config.name || config.provider + '/' + config.model} loaded. Make changes and save to update.`,
      color: 'blue',
      icon: <IconEdit size={16} />,
    });
  };

  // Load available models for a provider
  const loadModelsForProvider = async (provider: string, apiKey?: string) => {
    if (!provider || provider === 'ollama' || provider === 'anthropic') {
      // For providers that don't need API calls or have static models
      return;
    }

    if (!apiKey) {
      setAvailableModels([]);
      return;
    }

    setLoadingModels(true);
    try {
      const response = await fetch(`http://localhost:8000/api/models/${provider}?api_key=${encodeURIComponent(apiKey)}`);
      if (response.ok) {
        const result = await response.json();
        if (result.status === 'success') {
          setAvailableModels(result.models);
        } else {
          console.warn('Failed to load models:', result.message);
          setAvailableModels([]);
        }
      } else {
        console.warn('Failed to fetch models:', response.status);
        setAvailableModels([]);
      }
    } catch (error) {
      console.error('Error loading models:', error);
      setAvailableModels([]);
    } finally {
      setLoadingModels(false);
    }
  };

  const handleDeleteConfiguration = async (config: LLMSettings, index: number) => {
    try {
      // Check if this configuration is being used by any projects
      const projectsResponse = await fetch('http://localhost:8000/projects');
      if (projectsResponse.ok) {
        const projects = await projectsResponse.json();
        const usingProjects = projects.filter((project: any) =>
          project.llm_api_key_id === config.id
        );

        if (usingProjects.length > 0) {
          const projectNames = usingProjects.map((p: any) => p.name).join(', ');
          const confirmed = window.confirm(
            `This LLM configuration is being used by ${usingProjects.length} project(s): ${projectNames}\n\n` +
            `Deleting this configuration will remove it from these projects. ` +
            `They will need to be reconfigured with a new LLM before using AI features.\n\n` +
            `Are you sure you want to proceed?`
          );

          if (!confirmed) {
            return;
          }

          // Remove LLM configuration from affected projects
          for (const project of usingProjects) {
            await fetch(`http://localhost:8000/projects/${project.id}`, {
              method: 'PUT',
              headers: {
                'Content-Type': 'application/json',
              },
              body: JSON.stringify({
                llm_provider: null,
                llm_model: null,
                llm_api_key_id: null,
                llm_temperature: null,
                llm_max_tokens: null
              }),
            });
          }
        }
      }

      // Delete the configuration from backend
      if (config.id) {
        const deleteResponse = await fetch(`http://localhost:8000/llm-configurations/${config.id}`, {
          method: 'DELETE',
        });

        if (!deleteResponse.ok) {
          throw new Error('Failed to delete configuration from backend');
        }
      }

      // Update local state
      const updatedConfigs = savedConfigurations.filter((_, i) => i !== index);
      setSavedConfigurations(updatedConfigs);

      // Also remove from localStorage for backward compatibility
      localStorage.setItem('llm_configurations', JSON.stringify(updatedConfigs));

      notifications.show({
        title: 'Configuration Deleted',
        message: `${config.name || config.provider + '/' + config.model} removed successfully`,
        color: 'orange',
        icon: <IconTrash size={16} />,
      });

    } catch (error) {
      notifications.show({
        title: 'Delete Failed',
        message: `Failed to delete configuration: ${error}`,
        color: 'red',
        icon: <IconX size={16} />,
      });
    }
  };

  const handleTestLLMConfiguration = async (config: LLMSettings, configId?: string) => {
    const testId = configId || config.id || `${config.provider}-${config.model}`;
    setTestingLLM(testId);

    try {
      // Test the LLM configuration directly using the backend API
      const testResponse = await fetch('http://localhost:8000/api/test-llm-config', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          config_id: config.id,
          provider: config.provider,
          model: config.model,
          api_key: config.api_key,
          temperature: config.temperature,
          max_tokens: 100
        }),
      });

      const result = await testResponse.json();

      // Store the test result for inline display
      setTestResults(prev => ({
        ...prev,
        [testId]: {
          ...result,
          timestamp: new Date().toLocaleTimeString(),
          query: "Hello, please respond with 'LLM test successful' to confirm connectivity.",
          configName: config.name || `${config.provider}/${config.model}`
        }
      }));

      // Show brief notification
      if (testResponse.ok && result.status === 'success') {
        notifications.show({
          title: 'LLM Test Successful! ✅',
          message: `${config.name || config.provider + '/' + config.model} is working correctly. Check details below.`,
          color: 'green',
          autoClose: 3000,
        });
      } else {
        notifications.show({
          title: 'LLM Test Failed ❌',
          message: `${config.name || config.provider + '/' + config.model} test failed. Check details below.`,
          color: 'red',
          autoClose: 3000,
        });
      }
    } catch (error) {
      // Store error result for inline display
      setTestResults(prev => ({
        ...prev,
        [testId]: {
          status: 'error',
          message: `Test failed: ${error}`,
          timestamp: new Date().toLocaleTimeString(),
          query: "Hello, please respond with 'LLM test successful' to confirm connectivity.",
          configName: config.name || `${config.provider}/${config.model}`
        }
      }));

      notifications.show({
        title: 'LLM Test Error ❌',
        message: `Failed to test LLM configuration. Check details below.`,
        color: 'red',
        autoClose: 3000,
      });
    } finally {
      setTestingLLM(null);
    }
  };

  const handleSaveOAuthSettings = async () => {
    setLoading(true);
    try {
      // TODO: Implement API call to save OAuth settings
      await new Promise(resolve => setTimeout(resolve, 1000));
      notifications.show({
        title: 'Success',
        message: 'OAuth settings saved successfully',
        color: 'green',
        icon: <IconCheck size={16} />,
      });
    } catch (error) {
      notifications.show({
        title: 'Error',
        message: 'Failed to save OAuth settings',
        color: 'red',
      });
    } finally {
      setLoading(false);
    }
  };

  const handleCreateUser = async () => {
    if (!newUser.username || !newUser.email || !newUser.password) {
      notifications.show({
        title: 'Validation Error',
        message: 'Please fill in all required fields',
        color: 'orange',
      });
      return;
    }

    setLoading(true);
    try {
      // TODO: Implement API call to create user
      const user: User = {
        id: Date.now().toString(),
        username: newUser.username,
        email: newUser.email,
        role: newUser.role,
        status: 'active',
        created_at: new Date().toISOString(),
      };

      setUsers(prev => [...prev, user]);
      setNewUser({ username: '', email: '', password: '', role: 'user' });
      setUserModalOpened(false);

      notifications.show({
        title: 'Success',
        message: 'User created successfully',
        color: 'green',
        icon: <IconCheck size={16} />,
      });
    } catch (error) {
      notifications.show({
        title: 'Error',
        message: 'Failed to create user',
        color: 'red',
      });
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteUser = async (userId: string) => {
    if (userId === '1') {
      notifications.show({
        title: 'Error',
        message: 'Cannot delete the admin user',
        color: 'red',
      });
      return;
    }

    setUsers(prev => prev.filter(user => user.id !== userId));
    notifications.show({
      title: 'Success',
      message: 'User deleted successfully',
      color: 'green',
    });
  };

  return (
    <Container size="xl">
      <Stack gap="md">


        {/* Settings Tabs */}
        <Tabs value={activeTab} onChange={(value) => setActiveTab(value || 'llm')}>
          <Tabs.List style={{ flexWrap: 'nowrap', overflowX: 'auto' }}>
            <Tabs.Tab value="llm" leftSection={<IconRobot size={16} />}>
              LLM Configuration
            </Tabs.Tab>
            <Tabs.Tab value="oauth" leftSection={<IconBrandOauth size={16} />}>
              OAuth & Authentication
            </Tabs.Tab>
            <Tabs.Tab value="users" leftSection={<IconUsers size={16} />}>
              User Management
            </Tabs.Tab>
            <Tabs.Tab value="knowledge" leftSection={<IconMessage size={16} />}>
              Knowledge Base
            </Tabs.Tab>
            <Tabs.Tab value="environment" leftSection={<IconSettings size={16} />}>
              Environment Variables
            </Tabs.Tab>
            <Tabs.Tab value="services" leftSection={<IconServer size={16} />}>
              Platform Services
            </Tabs.Tab>
            <Tabs.Tab value="global-templates" leftSection={<IconFileText size={16} />}>
              Global Document Templates
            </Tabs.Tab>
          </Tabs.List>

          {/* LLM Configuration Tab */}
          <Tabs.Panel value="llm" pt="md">
            <Card shadow="sm" p="lg" radius="md" withBorder>
              <Stack gap="lg">
                <Group justify="space-between">
                  <div>
                    <Text size="lg" fw={600}>
                      Large Language Model Configuration
                    </Text>
                    <Text size="sm" c="dimmed">
                      Configure AI model settings for document analysis and chat features
                    </Text>
                  </div>
                </Group>

                <Divider />

                <TextInput
                  label="Configuration Name"
                  placeholder="e.g., 'Production OpenAI GPT-4', 'Development Claude', etc."
                  value={llmSettings.name}
                  onChange={(event) => setLlmSettings(prev => ({ ...prev, name: event.currentTarget.value }))}
                  description="Give this configuration a unique name to identify it easily"
                  required
                />

                <Select
                  label="LLM Provider"
                  placeholder="Select provider"
                  value={llmSettings.provider}
                  onChange={(value) => {
                    // Reset model and API key when provider changes
                    setLlmSettings(prev => ({
                      ...prev,
                      provider: value || 'openai',
                      model: '', // Reset model
                      api_key: '' // Reset API key
                    }));
                    setAvailableModels([]); // Clear dynamic models
                  }}
                  data={[
                    { value: 'openai', label: 'OpenAI' },
                    { value: 'azure', label: 'Azure OpenAI' },
                    { value: 'anthropic', label: 'Anthropic Claude' },
                    { value: 'gemini', label: 'Google Gemini' },
                    { value: 'ollama', label: 'Ollama (Local)' },
                    { value: 'custom', label: 'Custom Endpoint' },
                  ]}
                  disabled={!llmSettings.name} // Enable only after name is entered
                  description={!llmSettings.name ? "Enter configuration name first" : "Select your LLM provider"}
                  required
                />

                <PasswordInput
                  label={llmSettings.provider === 'ollama' ? 'API Key (Optional)' : 'API Key'}
                  placeholder={llmSettings.provider === 'ollama' ? 'Optional for local Ollama' : 'Enter your API key to load models'}
                  value={llmSettings.api_key}
                  onChange={(event) => {
                    const newApiKey = event.currentTarget.value;
                    setLlmSettings(prev => ({ ...prev, api_key: newApiKey }));

                    // Trigger model loading for dynamic providers
                    if (newApiKey && (llmSettings.provider === 'openai' || llmSettings.provider === 'gemini')) {
                      loadModelsForProvider(llmSettings.provider, newApiKey);
                    } else {
                      setAvailableModels([]);
                    }
                  }}
                  disabled={!llmSettings.provider} // Enable only after provider is selected
                  description={!llmSettings.provider ? "Select provider first" :
                    (llmSettings.provider === 'openai' || llmSettings.provider === 'gemini') ?
                      "Enter API key to load available models dynamically" :
                      "API key for authentication"
                  }
                  required={llmSettings.provider !== 'ollama'}
                />

                <Select
                  label="Model"
                  placeholder={loadingModels ? "Loading models from API..." :
                    !llmSettings.api_key && (llmSettings.provider === 'openai' || llmSettings.provider === 'gemini') ?
                      "Enter API key first to load models" : "Select model"
                  }
                  value={llmSettings.model}
                  onChange={(value) => setLlmSettings(prev => ({ ...prev, model: value || '' }))}
                  data={availableModels.length > 0 ?
                    availableModels.map(model => ({
                      value: model.id,
                      label: `${model.name} - ${model.description}`
                    })) :
                    getModelOptions(llmSettings.provider)
                  }
                  disabled={loadingModels || !llmSettings.provider ||
                    (!llmSettings.api_key && (llmSettings.provider === 'openai' || llmSettings.provider === 'gemini'))
                  }
                  rightSection={loadingModels ? <Loader size="xs" /> : null}
                  description={availableModels.length > 0 ?
                    `✅ ${availableModels.length} models loaded from ${llmSettings.provider.toUpperCase()} API` :
                    loadingModels ? "Loading models from API..." :
                    (llmSettings.provider === 'openai' || llmSettings.provider === 'gemini') && !llmSettings.api_key ?
                      "Enter API key above to load available models" :
                      "Using static model list"
                  }
                  required
                />



                {/* Azure OpenAI specific fields */}
                {llmSettings.provider === 'azure' && (
                  <TextInput
                    label="Base URL"
                    placeholder="https://your-resource.openai.azure.com"
                    value={llmSettings.base_url}
                    onChange={(event) => setLlmSettings(prev => ({ ...prev, base_url: event.currentTarget.value }))}
                    required
                  />
                )}

                {/* Gemini specific fields */}
                {llmSettings.provider === 'gemini' && (
                  <TextInput
                    label="Google Cloud Project ID"
                    placeholder="your-project-id"
                    value={llmSettings.gemini_project_id}
                    onChange={(event) => setLlmSettings(prev => ({ ...prev, gemini_project_id: event.currentTarget.value }))}
                    required
                  />
                )}

                {/* Ollama specific fields */}
                {llmSettings.provider === 'ollama' && (
                  <TextInput
                    label="Ollama Host"
                    placeholder="http://localhost:11434"
                    value={llmSettings.ollama_host}
                    onChange={(event) => setLlmSettings(prev => ({ ...prev, ollama_host: event.currentTarget.value }))}
                    required
                  />
                )}

                {/* Custom endpoint specific fields */}
                {llmSettings.provider === 'custom' && (
                  <TextInput
                    label="Custom Endpoint URL"
                    placeholder="https://your-custom-endpoint.com/v1"
                    value={llmSettings.custom_endpoint}
                    onChange={(event) => setLlmSettings(prev => ({ ...prev, custom_endpoint: event.currentTarget.value }))}
                    required
                  />
                )}

                <Grid>
                  <Grid.Col span={6}>
                    <NumberInput
                      label="Temperature"
                      placeholder="0.7"
                      value={llmSettings.temperature}
                      onChange={(value) => setLlmSettings(prev => ({ ...prev, temperature: Number(value) || 0.7 }))}
                      min={0}
                      max={2}
                      step={0.1}
                      decimalScale={1}
                    />
                  </Grid.Col>
                  <Grid.Col span={6}>
                    <NumberInput
                      label="Max Tokens"
                      placeholder="4000"
                      value={llmSettings.max_tokens}
                      onChange={(value) => setLlmSettings(prev => ({ ...prev, max_tokens: Number(value) || 4000 }))}
                      min={100}
                      max={32000}
                    />
                  </Grid.Col>
                </Grid>

                <Group justify="flex-end">
                  <Button
                    onClick={() => handleTestLLMConfiguration(llmSettings, 'current')}
                    loading={testingLLM === 'current'}
                    leftSection={<IconTestPipe size={16} />}
                    variant="outline"
                    color="blue"
                    disabled={!llmSettings.provider || !llmSettings.model || (!llmSettings.api_key && llmSettings.provider !== 'ollama')}
                  >
                    {testingLLM === 'current' ? 'Testing...' : 'Test LLM'}
                  </Button>
                  <Button
                    onClick={handleSaveLLMSettings}
                    loading={saving}
                    leftSection={<IconCheck size={16} />}
                    color="green"
                  >
                    {saving ? 'Saving...' : 'Save Configuration'}
                  </Button>
                </Group>

                {/* Saved Configurations Section */}
                {savedConfigurations.length > 0 && (
                  <>
                    <Divider />
                    <div>
                      <Text size="lg" fw={600} mb="md">
                        Saved Configurations
                      </Text>
                      <Text size="sm" c="dimmed" mb="md">
                        Previously saved LLM configurations. Click to load or delete.
                      </Text>
                      <Stack gap="xs">
                        {savedConfigurations.map((config, index) => {
                          const testId = config.id || `saved-${index}`;
                          const testResult = testResults[testId];

                          return (
                            <div key={config.id || index}>
                              <Card p="sm" withBorder>
                                <Group justify="space-between">
                                  <div style={{ marginLeft: '8px' }}>
                                    <Group gap="xs">
                                      <Text size="sm" fw={600}>
                                        {config.name || `${config.provider} ${config.model}`}
                                      </Text>
                                      <Badge color="blue" variant="light">
                                        {config.provider}
                                      </Badge>
                                      <Badge color="gray" variant="outline">
                                        {config.model}
                                      </Badge>
                                    </Group>
                                    <Text size="xs" c="dimmed">
                                      Created: {config.created_at ? new Date(config.created_at).toLocaleDateString() : 'Unknown'}
                                    </Text>
                                  </div>
                                  <Group gap="xs">
                                    <Button
                                      size="xs"
                                      variant="outline"
                                      color="blue"
                                      leftSection={<IconTestPipe size={12} />}
                                      onClick={() => handleTestLLMConfiguration(config, testId)}
                                      loading={testingLLM === testId}
                                      disabled={config.status === 'needs_key' && config.provider !== 'ollama'}
                                    >
                                      {testingLLM === testId ? 'Testing...' : 'Test'}
                                    </Button>
                                    <Button
                                      size="xs"
                                      variant="light"
                                      onClick={() => handleLoadConfiguration(config)}
                                    >
                                      Load
                                    </Button>
                                    <Button
                                      size="xs"
                                      variant="outline"
                                      color="orange"
                                      leftSection={<IconEdit size={12} />}
                                      onClick={() => handleEditConfiguration(config)}
                                    >
                                      Edit
                                    </Button>
                                    <ActionIcon
                                      size="sm"
                                      color="red"
                                      variant="light"
                                      onClick={() => handleDeleteConfiguration(config, index)}
                                    >
                                      <IconTrash size={14} />
                                    </ActionIcon>
                                  </Group>
                                </Group>
                              </Card>

                              {/* Inline Test Result Display - Fixed positioning */}
                              {testResult && (
                                <Card p="md" withBorder mt="xs" style={{
                                  backgroundColor: testResult.status === 'success' ? '#e8f5e8' : '#ffe8e8',
                                  marginLeft: '0px', // Ensure no left cutoff
                                  marginRight: '0px',
                                  width: '100%' // Full width
                                }}>
                                  <Stack gap="sm">
                                    <Group gap="xs">
                                      <Text size="sm" fw={600}>
                                        Test Result for {testResult.configName}:
                                      </Text>
                                      <Badge color={testResult.status === 'success' ? 'green' : 'red'}>
                                        {testResult.status === 'success' ? 'Success' : 'Failed'}
                                      </Badge>
                                      <Text size="xs" c="dimmed">
                                        at {testResult.timestamp}
                                      </Text>
                                    </Group>

                                    <div style={{ marginLeft: '0px', width: '100%' }}>
                                      <Text size="xs" c="dimmed" mb="xs">Query sent to LLM:</Text>
                                      <div style={{
                                        backgroundColor: '#f0f0f0',
                                        padding: '8px',
                                        borderRadius: '4px',
                                        fontFamily: 'monospace',
                                        fontSize: '12px',
                                        marginLeft: '0px',
                                        width: '100%',
                                        boxSizing: 'border-box'
                                      }}>
                                        {testResult.query}
                                      </div>
                                    </div>

                                    <div style={{ marginLeft: '0px', width: '100%' }}>
                                      <Text size="xs" c="dimmed" mb="xs">
                                        {testResult.status === 'success' ? 'Response received:' : 'Error message:'}
                                      </Text>
                                      <div style={{
                                        backgroundColor: testResult.status === 'success' ? '#e8f5e8' : '#ffe8e8',
                                        padding: '8px',
                                        borderRadius: '4px',
                                        fontFamily: 'monospace',
                                        fontSize: '12px',
                                        marginLeft: '0px',
                                        width: '100%',
                                        boxSizing: 'border-box',
                                        wordWrap: 'break-word'
                                      }}>
                                        {testResult.status === 'success' ? testResult.response : testResult.message}
                                      </div>
                                    </div>

                                    {testResult.status === 'success' && (
                                      <Text size="xs" c="green" fw={500} style={{ marginLeft: '0px' }}>
                                        ✅ LLM configuration is working correctly.
                                      </Text>
                                    )}

                                    {testResult.status === 'error' && (
                                      <Text size="xs" c="red" fw={500} style={{ marginLeft: '0px' }}>
                                        ❌ LLM configuration failed. Please check your API key and configuration.
                                      </Text>
                                    )}
                                  </Stack>
                                </Card>
                              )}
                            </div>
                          );
                        })}
                      </Stack>
                    </div>
                  </>
                )}
              </Stack>
            </Card>
          </Tabs.Panel>

          {/* OAuth Configuration Tab */}
          <Tabs.Panel value="oauth" pt="md">
            <Card shadow="sm" p="lg" radius="md" withBorder>
              <Stack gap="lg">
                <Group justify="space-between">
                  <div>
                    <Text size="lg" fw={600}>
                      OAuth & Authentication Settings
                    </Text>
                    <Text size="sm" c="dimmed">
                      Configure external authentication providers and SSO
                    </Text>
                  </div>
                  <Switch
                    label="Enable OAuth"
                    checked={oauthSettings.enabled}
                    onChange={(event) => setOauthSettings(prev => ({ ...prev, enabled: event.currentTarget.checked }))}
                  />
                </Group>

                <Divider />

                {oauthSettings.enabled && (
                  <Stack gap="md">
                    <Select
                      label="OAuth Provider"
                      placeholder="Select provider"
                      value={oauthSettings.provider}
                      onChange={(value) => setOauthSettings(prev => ({ ...prev, provider: value || 'azure' }))}
                      data={[
                        { value: 'azure', label: 'Azure Active Directory' },
                        { value: 'google', label: 'Google Workspace' },
                        { value: 'okta', label: 'Okta' },
                        { value: 'auth0', label: 'Auth0' },
                      ]}
                      required
                    />

                    <Grid>
                      <Grid.Col span={6}>
                        <TextInput
                          label="Client ID"
                          placeholder="Enter client ID"
                          value={oauthSettings.client_id}
                          onChange={(event) => setOauthSettings(prev => ({ ...prev, client_id: event.currentTarget.value }))}
                          required
                        />
                      </Grid.Col>
                      <Grid.Col span={6}>
                        <PasswordInput
                          label="Client Secret"
                          placeholder="Enter client secret"
                          value={oauthSettings.client_secret}
                          onChange={(event) => setOauthSettings(prev => ({ ...prev, client_secret: event.currentTarget.value }))}
                          required
                        />
                      </Grid.Col>
                    </Grid>

                    <TextInput
                      label="Redirect URI"
                      placeholder="https://your-domain.com/auth/callback"
                      value={oauthSettings.redirect_uri}
                      onChange={(event) => setOauthSettings(prev => ({ ...prev, redirect_uri: event.currentTarget.value }))}
                      required
                    />

                    <Alert icon={<IconAlertCircle size={16} />} color="blue">
                      <Text size="sm">
                        <strong>Configuration Steps:</strong>
                        <br />
                        1. Register your application with the OAuth provider
                        <br />
                        2. Configure the redirect URI in your OAuth app settings
                        <br />
                        3. Copy the Client ID and Client Secret from your OAuth app
                        <br />
                        4. Test the configuration before enabling for all users
                      </Text>
                    </Alert>
                  </Stack>
                )}

                <Group justify="flex-end">
                  <Button
                    onClick={handleSaveOAuthSettings}
                    loading={loading}
                    leftSection={<IconCheck size={16} />}
                    disabled={!oauthSettings.enabled}
                  >
                    Save OAuth Settings
                  </Button>
                </Group>
              </Stack>
            </Card>
          </Tabs.Panel>

          {/* User Management Tab */}
          <Tabs.Panel value="users" pt="md">
            <Card shadow="sm" p="lg" radius="md" withBorder>
              <Stack gap="lg">
                <Group justify="space-between">
                  <div>
                    <Text size="lg" fw={600}>
                      User Management
                    </Text>
                    <Text size="sm" c="dimmed">
                      Manage local user accounts and permissions
                    </Text>
                  </div>
                  <Button
                    leftSection={<IconPlus size={16} />}
                    onClick={() => setUserModalOpened(true)}
                  >
                    Add User
                  </Button>
                </Group>

                <Divider />

                <Table striped highlightOnHover>
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th>Username</Table.Th>
                      <Table.Th>Email</Table.Th>
                      <Table.Th>Role</Table.Th>
                      <Table.Th>Status</Table.Th>
                      <Table.Th>Created</Table.Th>
                      <Table.Th>Actions</Table.Th>
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {users.map((user) => (
                      <Table.Tr key={user.id}>
                        <Table.Td>
                          <Text fw={500}>{user.username}</Text>
                        </Table.Td>
                        <Table.Td>{user.email}</Table.Td>
                        <Table.Td>
                          <Badge color={user.role === 'admin' ? 'red' : 'blue'} variant="light">
                            {user.role}
                          </Badge>
                        </Table.Td>
                        <Table.Td>
                          <Badge color={user.status === 'active' ? 'green' : 'gray'} variant="light">
                            {user.status}
                          </Badge>
                        </Table.Td>
                        <Table.Td>
                          <Text size="sm" c="dimmed">
                            {new Date(user.created_at).toLocaleDateString()}
                          </Text>
                        </Table.Td>
                        <Table.Td>
                          <Group gap="xs">
                            <ActionIcon
                              size="sm"
                              variant="subtle"
                              color="blue"
                              onClick={() => setEditingUser(user)}
                            >
                              <IconEdit size={14} />
                            </ActionIcon>
                            <ActionIcon
                              size="sm"
                              variant="subtle"
                              color="red"
                              onClick={() => handleDeleteUser(user.id)}
                              disabled={user.id === '1'}
                            >
                              <IconTrash size={14} />
                            </ActionIcon>
                          </Group>
                        </Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              </Stack>
            </Card>
          </Tabs.Panel>

          {/* Knowledge Base Tab */}
          <Tabs.Panel value="knowledge" pt="md">
            <Card shadow="sm" p="lg" radius="md" withBorder>
              <Stack gap="lg">
                <Group justify="space-between">
                  <div>
                    <Text size="lg" fw={600}>
                      Knowledge Base Chat Configuration
                    </Text>
                    <Text size="sm" c="dimmed">
                      Configure AI-powered knowledge base and chat features
                    </Text>
                  </div>
                </Group>

                <Divider />

                <Alert icon={<IconAlertCircle size={16} />} color="blue">
                  <Text size="sm">
                    <strong>🚧 Knowledge Base Chat - Coming Soon</strong>
                    <br />
                    This section will allow you to configure:
                    <br />
                    • RAG (Retrieval-Augmented Generation) settings
                    <br />
                    • Vector database configuration
                    <br />
                    • Document indexing preferences
                    <br />
                    • Chat response customization
                    <br />
                    • Knowledge base update schedules
                  </Text>
                </Alert>

                <Stack gap="md" style={{ opacity: 0.6 }}>
                  <Switch
                    label="Enable Knowledge Base Chat"
                    description="Allow users to chat with AI about project documents"
                    disabled
                  />

                  <Select
                    label="Vector Database"
                    placeholder="Select vector database"
                    data={[
                      { value: 'chroma', label: 'ChromaDB' },
                      { value: 'pinecone', label: 'Pinecone' },
                      { value: 'weaviate', label: 'Weaviate' },
                    ]}
                    disabled
                  />

                  <NumberInput
                    label="Chunk Size"
                    description="Size of text chunks for document processing"
                    placeholder="1000"
                    disabled
                  />

                  <NumberInput
                    label="Chunk Overlap"
                    description="Overlap between text chunks"
                    placeholder="200"
                    disabled
                  />
                </Stack>
              </Stack>
            </Card>
          </Tabs.Panel>

          {/* Environment Variables Tab */}
          <Tabs.Panel value="environment" pt="md">
            <EnvironmentVariablesPanel />
          </Tabs.Panel>

          {/* Platform Services Tab */}
          <Tabs.Panel value="services" pt="md">
            <ServiceStatusPanel />
          </Tabs.Panel>

          {/* Global Document Templates Tab */}
          <Tabs.Panel value="global-templates" pt="md">
            <GlobalDocumentTemplates />
          </Tabs.Panel>
        </Tabs>

        {/* Add User Modal */}
        <Modal
          opened={userModalOpened}
          onClose={() => setUserModalOpened(false)}
          title="Add New User"
          size="md"
        >
          <Stack gap="md">
            <TextInput
              label="Username"
              placeholder="Enter username"
              value={newUser.username}
              onChange={(event) => setNewUser(prev => ({ ...prev, username: event.currentTarget.value }))}
              required
            />

            <TextInput
              label="Email"
              placeholder="Enter email address"
              value={newUser.email}
              onChange={(event) => setNewUser(prev => ({ ...prev, email: event.currentTarget.value }))}
              required
            />

            <PasswordInput
              label="Password"
              placeholder="Enter password"
              value={newUser.password}
              onChange={(event) => setNewUser(prev => ({ ...prev, password: event.currentTarget.value }))}
              required
            />

            <Select
              label="Role"
              placeholder="Select role"
              value={newUser.role}
              onChange={(value) => setNewUser(prev => ({ ...prev, role: value || 'user' }))}
              data={[
                { value: 'user', label: 'User' },
                { value: 'admin', label: 'Administrator' },
              ]}
              required
            />

            <Group justify="flex-end" mt="md">
              <Button variant="subtle" onClick={() => setUserModalOpened(false)}>
                Cancel
              </Button>
              <Button onClick={handleCreateUser} loading={loading}>
                Create User
              </Button>
            </Group>
          </Stack>
        </Modal>
      </Stack>
    </Container>
  );
};

export default SettingsView;
