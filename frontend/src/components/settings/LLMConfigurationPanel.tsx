/**
 * LLM Configuration Panel - Complete LLM settings management
 * Extracted from SettingsView.tsx for modularity
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Stack,
  TextInput,
  PasswordInput,
  Select,
  Button,
  Divider,
  Alert,
  ActionIcon,
  NumberInput,
  Badge,
  Group,
  Grid,
  Card,
  Text,
  Loader,
  Tooltip,
} from '@mantine/core';
import {
  IconRobot,
  IconEdit,
  IconTrash,
  IconPlus,
  IconCheck,
  IconTestPipe,
  IconX,
  IconSearch,
  IconSortAscending,
  IconSortDescending,
} from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';
import { useLLMConfig } from '../../contexts/LLMConfigContext';
import { useNotificationInterceptor } from '../../hooks/useNotificationInterceptor';

// Utility function for debouncing
function debounce<T extends (...args: any[]) => void>(func: T, delay: number): T {
  let timeoutId: NodeJS.Timeout;
  return ((...args: any[]) => {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => func(...args), delay);
  }) as T;
}

interface LLMSettings {
  id?: string;
  provider: string;
  model: string;
  api_key?: string;
  temperature: number;
  max_tokens: number;
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

interface LLMConfigurationPanelProps {
  showAddForm?: boolean;
  setShowAddForm?: (show: boolean) => void;
}

export const LLMConfigurationPanel: React.FC<LLMConfigurationPanelProps> = ({ 
  showAddForm: externalShowAddForm, 
  setShowAddForm: externalSetShowAddForm 
}) => {
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deletingConfig, setDeletingConfig] = useState<string | null>(null);
  const { configurations: savedConfigurations, reloadConfigurations } = useLLMConfig();
  const [testingLLM, setTestingLLM] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<{[key: string]: any}>({});
  const { interceptLLMConfigSave, interceptLLMConfigTest } = useNotificationInterceptor();

  // Form visibility state - use external props if provided
  const [internalShowAddForm, setInternalShowAddForm] = useState(false);
  const [editingConfigId, setEditingConfigId] = useState<string | null>(null);
  
  const showAddForm = externalShowAddForm !== undefined ? externalShowAddForm : internalShowAddForm;
  const setShowAddForm = externalSetShowAddForm || setInternalShowAddForm;

  // Search and Sort State
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState<'name' | 'provider' | 'created_at'>('created_at');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');

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
  const [ollamaValidation, setOllamaValidation] = useState({
    testing: false,
    status: 'unknown' as 'unknown' | 'connecting' | 'success' | 'error',
    message: '',
    models: [] as string[]
  });

  const getProviderOptions = () => [
    { value: 'openai', label: 'OpenAI' },
    { value: 'anthropic', label: 'Anthropic (Claude)' },
    { value: 'gemini', label: 'Google Gemini' },
    { value: 'azure', label: 'Azure OpenAI' },
    { value: 'ollama', label: 'Ollama' },
    { value: 'custom', label: 'Custom Endpoint' },
  ];

  const getModelOptions = (provider: string) => {
    const modelMap: { [key: string]: { value: string; label: string }[] } = {
      openai: [
        { value: 'gpt-4o', label: 'GPT-4o' },
        { value: 'gpt-4o-mini', label: 'GPT-4o Mini' },
        { value: 'gpt-4-turbo', label: 'GPT-4 Turbo' },
        { value: 'gpt-4', label: 'GPT-4' },
        { value: 'gpt-3.5-turbo', label: 'GPT-3.5 Turbo' },
      ],
      anthropic: [
        { value: 'claude-3-5-sonnet-20241022', label: 'Claude 3.5 Sonnet' },
        { value: 'claude-3-haiku-20240307', label: 'Claude 3 Haiku' },
      ],
      gemini: [
        { value: 'gemini-2.0-flash-exp', label: 'Gemini 2.0 Flash (Experimental)' },
        { value: 'gemini-1.5-pro', label: 'Gemini 1.5 Pro' },
        { value: 'gemini-1.5-flash', label: 'Gemini 1.5 Flash' },
      ],
      azure: [
        { value: 'gpt-4o', label: 'GPT-4o' },
        { value: 'gpt-4-turbo', label: 'GPT-4 Turbo' },
        { value: 'gpt-4', label: 'GPT-4' },
        { value: 'gpt-35-turbo', label: 'GPT-3.5 Turbo' },
      ],
      ollama: [],
      custom: [
        { value: 'custom-model', label: 'Custom Model' },
      ],
    };
    return modelMap[provider] || [];
  };

  // Debounced validation for Ollama endpoint
  const validateOllamaEndpoint = useCallback(
    debounce(async (ollamaHost: string) => {
      if (!ollamaHost || ollamaHost.trim() === '') {
        setOllamaValidation(prev => ({ ...prev, status: 'unknown', message: '' }));
        return;
      }

      setOllamaValidation(prev => ({ ...prev, testing: true, status: 'connecting', message: 'Testing connection...' }));

      try {
        const testResponse = await fetch('http://localhost:8000/api/ollama/test-endpoint', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ base_url: ollamaHost.trim() }),
        });

        if (testResponse.ok) {
          const result = await testResponse.json();
          setOllamaValidation({
            testing: false,
            status: 'success',
            message: result.message || `Connected successfully. Found ${result.models?.length || 0} models.`,
            models: result.models || []
          });
          if (llmSettings.provider === 'ollama') {
            setAvailableModels(result.models || []);
          }
        } else {
          const error = await testResponse.json();
          throw new Error(error.detail || 'Failed to connect to Ollama endpoint');
        }
      } catch (error: any) {
        setOllamaValidation({
          testing: false,
          status: 'error',
          message: error.message || 'Failed to connect to Ollama. Make sure Ollama is running.',
          models: []
        });
      }
    }, 1000),
    [llmSettings.provider]
  );

  // Fetch max tokens when model is selected
  const fetchMaxTokensForModel = async (provider: string, model: string, apiKey?: string) => {
    if (!provider || !model) return;
    
    try {
      const queryParams = apiKey ? `?api_key=${encodeURIComponent(apiKey)}` : '';
      const response = await fetch(`http://localhost:8000/api/llm/models/${provider}/${model}/max-tokens${queryParams}`);
      
      if (response.ok) {
        const result = await response.json();
        if (result.max_tokens) {
          setLlmSettings(prev => ({ ...prev, max_tokens: result.max_tokens }));
          console.log(`Auto-updated max tokens for ${provider}/${model}: ${result.max_tokens}`);
        }
      }
    } catch (error) {
      console.warn(`Failed to fetch max tokens for ${provider}/${model}:`, error);
    }
  };

  // Load available models for a provider
  const loadModelsForProvider = async (provider: string, apiKey?: string) => {
    if (!provider) {
      setAvailableModels([]);
      return;
    }

    if (provider === 'ollama') {
      setLoadingModels(true);
      try {
        const ollamaHost = llmSettings.ollama_host || 'http://localhost:11434';
        const testResponse = await fetch('http://localhost:8000/api/ollama/test-endpoint', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ base_url: ollamaHost }),
        });

        if (testResponse.ok) {
          const result = await testResponse.json();
          setAvailableModels(result.models || []);
          setOllamaValidation({
            testing: false,
            status: 'success',
            message: result.message || `Connected to ${ollamaHost}`,
            models: result.models || []
          });
        }
      } catch (error: any) {
        setOllamaValidation({
          testing: false,
          status: 'error',
          message: error.message || 'Failed to connect to Ollama',
          models: []
        });
        setAvailableModels([]);
      } finally {
        setLoadingModels(false);
      }
      return;
    }

    if (provider === 'anthropic') {
      setAvailableModels(['claude-3-5-sonnet-20241022', 'claude-3-haiku-20240307']);
      return;
    }

    // For providers that support dynamic fetching (OpenAI, Gemini, Azure)
    if (!apiKey && (provider === 'openai' || provider === 'gemini' || provider === 'azure')) {
      // If no API key, try to get cached models first, then fallback to static
      setLoadingModels(true);
      try {
        const response = await fetch(`http://localhost:8000/api/llm/models/${provider}`);
        if (response.ok) {
          const result = await response.json();
          if (result.models && result.models.length > 0) {
            setAvailableModels(result.models);
            if (result.cached) {
              console.log(`Using cached models for ${provider}`);
            }
          } else {
            // Fallback to static models if no cache available
            const staticModels = getModelOptions(provider).map(m => m.value);
            setAvailableModels(staticModels);
          }
        } else {
          // Fallback to static models on API error
          const staticModels = getModelOptions(provider).map(m => m.value);
          setAvailableModels(staticModels);
        }
      } catch (error) {
        console.warn(`Failed to fetch cached models for ${provider}, using static fallback:`, error);
        const staticModels = getModelOptions(provider).map(m => m.value);
        setAvailableModels(staticModels);
      } finally {
        setLoadingModels(false);
      }
      return;
    }

    setLoadingModels(true);
    try {
      const response = await fetch(`http://localhost:8000/api/llm/models/${provider}?api_key=${encodeURIComponent(apiKey || '')}`);
      if (response.ok) {
        const result = await response.json();
        if (result.models && result.models.length > 0) {
          setAvailableModels(result.models);
          if (result.cached) {
            console.log(`Using cached models for ${provider} (with API key validation)`);
          } else {
            console.log(`Fetched fresh models for ${provider} from API`);
          }
        } else {
          // Fallback to static models if API returns empty
          const staticModels = getModelOptions(provider).map(m => m.value);
          setAvailableModels(staticModels);
        }
      } else {
        // Fallback to static models on API error
        const staticModels = getModelOptions(provider).map(m => m.value);
        setAvailableModels(staticModels);
      }
    } catch (error) {
      console.warn(`Failed to fetch dynamic models for ${provider}, using static fallback:`, error);
      // Fallback to static models
      const staticModels = getModelOptions(provider).map(m => m.value);
      setAvailableModels(staticModels);
    } finally {
      setLoadingModels(false);
    }
  };

  const handleSaveLLMSettings = async () => {
    setSaving(true);
    try {
      const isEditing = editingConfigId !== null;
      const configName = llmSettings.name || `${llmSettings.provider}/${llmSettings.model}`;
      
      // Use notification interceptor for enterprise-grade tracking
      const { result, error, correlationId } = await interceptLLMConfigSave(
        async () => {
          const method = isEditing ? 'PUT' : 'POST';
          const url = isEditing 
            ? `http://localhost:8000/api/llm/configurations/${editingConfigId}`
            : 'http://localhost:8000/api/llm/configurations';

          const response = await fetch(url, {
            method,
            headers: {
              'Content-Type': 'application/json',
              'Authorization': 'Bearer service-backend-token',
              'X-Correlation-ID': `ui-llm-save-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
            },
            body: JSON.stringify(llmSettings),
            signal: AbortSignal.timeout(30000) // 30 second timeout
          });

          if (!response.ok) {
            const errorText = await response.text();
            console.error(`Save failed: ${response.status} ${response.statusText}`, errorText);
            throw new Error(`HTTP ${response.status}: ${errorText || response.statusText}`);
          }
          
          return response.json();
        },
        configName,
        llmSettings.provider,
        llmSettings.model,
        {
          metadata: {
            configName,
            provider: llmSettings.provider,
            model: llmSettings.model,
            isEditing,
            configId: editingConfigId || undefined
          },
          showToast: false // We'll handle our own notifications
        }
      );

      if (result) {
        await reloadConfigurations();
        notifications.show({
          title: isEditing ? 'Configuration Updated' : 'Configuration Saved',
          message: `LLM configuration "${configName}" ${isEditing ? 'updated' : 'saved'} successfully (ID: ${correlationId.slice(-8)})`,
          color: 'green',
          icon: <IconCheck size={16} />,
        });
        
        // Reset form
        resetForm();
      } else if (error) {
        const errorMessage = error.name === 'TimeoutError' 
          ? 'Request timed out. Please check if the backend services are running.' 
          : error.message || 'Unknown error occurred';
        
        notifications.show({
          title: `${isEditing ? 'Update' : 'Save'} Failed`,
          message: `Failed to ${isEditing ? 'update' : 'save'} configuration: ${errorMessage} (ID: ${correlationId.slice(-8)})`,
          color: 'red',
        });
      }
    } catch (error: any) {
      console.error('Save LLM configuration failed:', error);
      const errorMessage = error.name === 'TimeoutError' 
        ? 'Request timed out. Please check if the backend services are running.' 
        : error.message || 'Unknown error occurred';
      
      notifications.show({
        title: `${editingConfigId ? 'Update' : 'Save'} Failed`,
        message: `Failed to ${editingConfigId ? 'update' : 'save'} configuration: ${errorMessage}`,
        color: 'red',
      });
    } finally {
      setSaving(false);
    }
  };

  const handleTestLLMConfiguration = async (config: LLMSettings, configId?: string) => {
    const testId = configId || config.id || `${config.provider}-${config.model}`;
    setTestingLLM(testId);

    try {
      const configName = config.name || `${config.provider}/${config.model}`;
      
      // Use notification interceptor for enterprise-grade tracking
      const { result, error, correlationId } = await interceptLLMConfigTest(
        async () => {
          const testResponse = await fetch('http://localhost:8000/api/llm/test-llm-config', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': 'Bearer service-backend-token',
              'X-Correlation-ID': `ui-llm-test-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
            },
            body: JSON.stringify({
              config_id: config.id,
              provider: config.provider,
              model: config.model,
              api_key: config.api_key,
              temperature: config.temperature || 0.1,
              max_tokens: 100,
              query: 'TEST REQUEST: Please respond with "TEST SUCCESSFUL - LLM is working correctly" to confirm connectivity.'
            }),
            signal: AbortSignal.timeout(60000) // 60 second timeout for LLM tests
          });

          if (!testResponse.ok) {
            const errorText = await testResponse.text();
            console.error(`LLM test failed: ${testResponse.status} ${testResponse.statusText}`, errorText);
            throw new Error(`HTTP ${testResponse.status}: ${errorText || testResponse.statusText}`);
          }

          return testResponse.json();
        },
        configName,
        config.provider,
        config.model,
        {
          metadata: {
            configName,
            provider: config.provider,
            model: config.model,
            configId: config.id
          },
          showToast: false // We'll handle our own notifications
        }
      );

      if (result) {
        setTestResults(prev => ({
          ...prev,
          [testId]: {
            ...result,
            timestamp: new Date().toLocaleTimeString(),
            configName,
            provider: config.provider,
            model: config.model,
            correlationId
          }
        }));

        notifications.show({
          title: result.status === 'success' ? 'Test Successful' : 'Test Failed',
          message: `${result.message || result.response || 'Test completed'} (ID: ${correlationId.slice(-8)})`,
          color: result.status === 'success' ? 'green' : 'red',
        });
      } else if (error) {
        const errorMessage = error.name === 'TimeoutError' 
          ? 'Test timed out. The LLM service may be unavailable or the API key might be invalid.' 
          : error.message || 'Unknown error occurred';
        
        setTestResults(prev => ({
          ...prev,
          [testId]: {
            status: 'error',
            message: errorMessage,
            timestamp: new Date().toLocaleTimeString(),
            configName,
            provider: config.provider,
            model: config.model,
            correlationId
          }
        }));
        
        notifications.show({
          title: 'Test Failed',
          message: `${errorMessage} (ID: ${correlationId.slice(-8)})`,
          color: 'red',
        });
      }
    } catch (error: any) {
      console.error('Test LLM configuration failed:', error);
      const errorMessage = error.name === 'TimeoutError' 
        ? 'Test timed out. The LLM service may be unavailable or the API key might be invalid.' 
        : error.message || 'Unknown error occurred';
      
      setTestResults(prev => ({
        ...prev,
        [testId]: {
          status: 'error',
          message: errorMessage,
          timestamp: new Date().toLocaleTimeString(),
          configName: config.name || `${config.provider}/${config.model}`,
          provider: config.provider,
          model: config.model
        }
      }));
      
      notifications.show({
        title: 'Test Failed',
        message: errorMessage,
        color: 'red',
      });
    } finally {
      setTestingLLM(null);
    }
  };

  const handleDeleteConfiguration = async (config: LLMSettings, index: number) => {
    const configId = config.id || `${config.provider}-${config.model}`;
    setDeletingConfig(configId);
    
    try {
      if (config.id) {
        const deleteResponse = await fetch(`http://localhost:8000/api/llm/configurations/${config.id}`, {
          method: 'DELETE',
          headers: {
            'Authorization': 'Bearer service-backend-token',
            'X-Correlation-ID': `ui-llm-delete-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
          },
          signal: AbortSignal.timeout(10000) // 10 second timeout for deletes
        });

        if (!deleteResponse.ok) {
          const errorText = await deleteResponse.text();
          console.error(`Delete failed: ${deleteResponse.status} ${deleteResponse.statusText}`, errorText);
          throw new Error(`HTTP ${deleteResponse.status}: ${errorText || deleteResponse.statusText}`);
        }
      }

      await reloadConfigurations();

      notifications.show({
        title: 'Configuration Deleted',
        message: `${config.name || config.provider + '/' + config.model} removed successfully`,
        color: 'orange',
        icon: <IconTrash size={16} />,
      });

    } catch (error: any) {
      console.error('Delete LLM configuration failed:', error);
      const errorMessage = error.name === 'TimeoutError' 
        ? 'Delete request timed out. Please try again.' 
        : error.message || 'Unknown error occurred';
      
      notifications.show({
        title: 'Delete Failed',
        message: `Failed to delete configuration: ${errorMessage}`,
        color: 'red',
      });
    } finally {
      setDeletingConfig(null);
    }
  };

  const handleLoadConfiguration = (config: LLMSettings) => {
    setLlmSettings({
      ...config,
      api_key: config.api_key || '',
      temperature: config.temperature ?? 0.7,
      max_tokens: config.max_tokens ?? 4000
    });

    loadModelsForProvider(config.provider, config.api_key);

    notifications.show({
      title: 'Configuration Loaded for Editing',
      message: `${config.name || config.provider + '/' + config.model} loaded`,
      color: 'blue',
      icon: <IconEdit size={16} />,
    });
  };

  // New function to handle editing
  const handleEditConfiguration = (config: LLMSettings) => {
    console.log('🔧 Edit Configuration clicked:', config);
    console.log('🔧 Config ID:', config.id);
    console.log('🔧 Config Provider:', config.provider);
    console.log('🔧 Config Model:', config.model);
    
    setEditingConfigId(config.id || null);
    setLlmSettings({
      ...config,
      api_key: config.api_key || '',
      temperature: config.temperature ?? 0.7,
      max_tokens: config.max_tokens ?? 4000
    });
    setShowAddForm(true);
    
    // Load models for the selected provider
    if (config.provider) {
      console.log('🔧 Loading models for provider:', config.provider);
      loadModelsForProvider(config.provider, config.api_key);
    }

    notifications.show({
      title: 'Editing Configuration',
      message: `Editing ${config.name || config.provider + '/' + config.model}`,
      color: 'blue',
    });
  };

  // Function to reset form
  const resetForm = () => {
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
    setEditingConfigId(null);
    setShowAddForm(false);
  };

  // Filtered and sorted configurations
  const filteredAndSortedConfigurations = useMemo(() => {
  const safeConfigurations = Array.isArray(savedConfigurations) ? [...savedConfigurations] : [];

  let filtered = safeConfigurations.filter(config => {
      if (!searchQuery) return true;
      
      const searchLower = searchQuery.toLowerCase();
      const name = (config.name || '').toLowerCase();
      const provider = (config.provider || '').toLowerCase();
      const model = (config.model || '').toLowerCase();
      const description = (config.description || '').toLowerCase();
      
      return name.includes(searchLower) || 
             provider.includes(searchLower) || 
             model.includes(searchLower) ||
             description.includes(searchLower);
    });

  // Sort configurations (copy already made above)
  filtered.sort((a, b) => {
      let aValue: string | number = '';
      let bValue: string | number = '';

      switch (sortBy) {
        case 'name':
          aValue = (a.name || `${a.provider} ${a.model}`).toLowerCase();
          bValue = (b.name || `${b.provider} ${b.model}`).toLowerCase();
          break;
        case 'provider':
          aValue = a.provider.toLowerCase();
          bValue = b.provider.toLowerCase();
          break;
        case 'created_at':
          // Handle created_at field for date sorting
          aValue = a.created_at ? new Date(a.created_at).getTime() : 0;
          bValue = b.created_at ? new Date(b.created_at).getTime() : 0;
          break;
        default:
          return 0;
      }

      if (sortDirection === 'asc') {
        return aValue < bValue ? -1 : aValue > bValue ? 1 : 0;
      } else {
        return aValue > bValue ? -1 : aValue < bValue ? 1 : 0;
      }
    });

    return filtered;
  }, [savedConfigurations, searchQuery, sortBy, sortDirection]);

  // Handle sort toggle
  const handleSortToggle = (field: 'name' | 'provider' | 'created_at') => {
    if (sortBy === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortDirection('desc');
    }
  };

  // Load models when provider or API key changes
  useEffect(() => {
    console.log('useEffect triggered - provider:', llmSettings.provider, 'api_key length:', llmSettings.api_key?.length || 0);
    
    if (llmSettings.provider) {
      // Always trigger for Ollama and Anthropic (they don't need API key for basic models)
      if (llmSettings.provider === 'ollama' || llmSettings.provider === 'anthropic') {
        console.log('Loading models for', llmSettings.provider, '(no API key required)');
        loadModelsForProvider(llmSettings.provider, llmSettings.api_key);
      }
      // For providers that need API key, trigger when API key is present
      else if (llmSettings.api_key && ['openai', 'gemini', 'azure', 'custom'].includes(llmSettings.provider)) {
        console.log('Loading models for', llmSettings.provider, 'with API key');
        loadModelsForProvider(llmSettings.provider, llmSettings.api_key);
      }
      // If no API key but provider selected, try to get cached models
      else if (!llmSettings.api_key && ['openai', 'gemini', 'azure'].includes(llmSettings.provider)) {
        console.log('Loading cached models for', llmSettings.provider, '(no API key)');
        loadModelsForProvider(llmSettings.provider, undefined);
      }
    }
  }, [llmSettings.provider, llmSettings.api_key]);

  // Fetch max tokens when model is selected
  useEffect(() => {
    if (llmSettings.provider && llmSettings.model && 
        (llmSettings.api_key || ['ollama', 'anthropic'].includes(llmSettings.provider))) {
      fetchMaxTokensForModel(llmSettings.provider, llmSettings.model, llmSettings.api_key);
    }
  }, [llmSettings.model, llmSettings.provider, llmSettings.api_key]);

  return (
    <Stack gap="xl">

      {/* New/Edit Configuration Form */}
      {showAddForm && (
        <Card p="lg" withBorder>
          <Stack gap="md">
            <Group justify="space-between" align="center">
              <Text size="lg" fw={600}>
                {editingConfigId ? 'Edit LLM Configuration' : 'Add New LLM Configuration'}
              </Text>
              <Group gap="xs">
                <IconRobot size="1.5rem" />
                <ActionIcon 
                  variant="subtle" 
                  onClick={resetForm}
                  title="Cancel"
                >
                  <IconX size={16} />
                </ActionIcon>
              </Group>
            </Group>

          <TextInput
            label="Configuration Name"
            placeholder="e.g., Production GPT-4"
            value={llmSettings.name}
            onChange={(event) => setLlmSettings(prev => ({ ...prev, name: event.currentTarget.value }))}
            description="Optional: Give this configuration a memorable name"
          />

          <Select
            label="Provider"
            placeholder="Select LLM provider"
            data={getProviderOptions()}
            value={llmSettings.provider}
            onChange={(value) => {
              setLlmSettings(prev => ({ ...prev, provider: value || 'openai', model: '' }));
              setAvailableModels([]);
            }}
            required
          />

          {(llmSettings.provider === 'openai' || llmSettings.provider === 'gemini' || llmSettings.provider === 'azure' || llmSettings.provider === 'custom') && (
            <PasswordInput
              label="API Key"
              placeholder="Enter your API key"
              value={llmSettings.api_key}
              onChange={(event) => setLlmSettings(prev => ({ ...prev, api_key: event.currentTarget.value }))}
              required
            />
          )}

          <Select
            label="Model"
            placeholder="Select model"
            value={llmSettings.model}
            onChange={(value) => setLlmSettings(prev => ({ ...prev, model: value || '' }))}
            data={
              availableModels.length > 0
                ? availableModels
                    .filter((m: any) =>
                      (typeof m === 'string' && !!m) ||
                      (m && (m.id != null || m.name))
                    )
                    .map((model: any) => {
                      if (typeof model === 'string') {
                        const val = String(model);
                        return { value: val, label: val };
                      } else {
                        const val = String(model.id ?? model.name);
                        const labelBase = model.name ? String(model.name) : val;
                        const label = model.description
                          ? `${labelBase} - ${String(model.description)}`
                          : labelBase;
                        return { value: val, label };
                      }
                    })
                : getModelOptions(llmSettings.provider)
            }
            disabled={loadingModels || !llmSettings.provider ||
              (!llmSettings.api_key && (llmSettings.provider === 'openai' || llmSettings.provider === 'gemini'))
            }
            rightSection={loadingModels ? <Loader size="xs" /> : null}
            required
          />

          {/* Provider-specific fields */}
          {llmSettings.provider === 'azure' && (
            <TextInput
              label="Base URL"
              placeholder="https://your-resource.openai.azure.com"
              value={llmSettings.base_url}
              onChange={(event) => setLlmSettings(prev => ({ ...prev, base_url: event.currentTarget.value }))}
              required
            />
          )}

          {llmSettings.provider === 'gemini' && (
            <TextInput
              label="Google Cloud Project ID"
              placeholder="your-project-id"
              value={llmSettings.gemini_project_id}
              onChange={(event) => setLlmSettings(prev => ({ ...prev, gemini_project_id: event.currentTarget.value }))}
              required
            />
          )}

          {llmSettings.provider === 'ollama' && (
            <Stack gap="xs">
              <TextInput
                label="Ollama Host"
                placeholder="http://localhost:11434"
                description="Enter the URL where Ollama is running"
                value={llmSettings.ollama_host}
                onChange={(event) => {
                  const newHost = event.currentTarget.value;
                  setLlmSettings(prev => ({ ...prev, ollama_host: newHost }));
                  validateOllamaEndpoint(newHost);
                }}
                required
                rightSection={
                  ollamaValidation.testing ? (
                    <Loader size="xs" />
                  ) : ollamaValidation.status === 'success' ? (
                    <IconCheck size={16} color="green" />
                  ) : ollamaValidation.status === 'error' ? (
                    <IconX size={16} color="red" />
                  ) : null
                }
              />
              {ollamaValidation.message && (
                <Text 
                  size="xs" 
                  color={
                    ollamaValidation.status === 'success' ? 'green' : 
                    ollamaValidation.status === 'error' ? 'red' : 'blue'
                  }
                >
                  {ollamaValidation.message}
                </Text>
              )}
            </Stack>
          )}

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
                onChange={(value) => setLlmSettings(prev => ({ ...prev, temperature: Number(value) ?? 0.7 }))}
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

          {/* Test Result for current config */}
          {testResults['current'] && (
            <Card p="md" withBorder style={{
              backgroundColor: testResults['current'].status === 'success' ? '#e8f5e8' : '#ffe8e8',
            }}>
              <Group justify="space-between" align="center">
                <Group gap="xs">
                  <Text fw={600}>LLM Test Result</Text>
                  <Badge color={testResults['current'].status === 'success' ? 'green' : 'red'}>
                    {testResults['current'].status === 'success' ? 'Success' : 'Failed'}
                  </Badge>
                </Group>
                <ActionIcon
                  size="sm"
                  variant="subtle"
                  onClick={() => setTestResults(prev => {
                    const next = { ...prev };
                    delete next['current'];
                    return next;
                  })}
                >
                  <IconX size={14} />
                </ActionIcon>
              </Group>
              <Text size="sm" mt="sm">
                {testResults['current'].message}
              </Text>
            </Card>
          )}
        </Stack>
      </Card>
      )}

      {/* Saved Configurations */}
      {savedConfigurations.length > 0 && (
        <Card p="lg" withBorder>
          <Group justify="space-between" align="center" mb="md">
            <Text size="lg" fw={600}>
              Saved Configurations ({filteredAndSortedConfigurations.length})
            </Text>
          </Group>

          {/* Search and Sort Controls */}
          <Group gap="md" mb="lg">
            <TextInput
              placeholder="Search configurations..."
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.currentTarget.value)}
              leftSection={<IconSearch size={16} />}
              style={{ flex: 1 }}
            />
            <Group gap="xs">
              <Text size="sm" c="dimmed">Sort by:</Text>
              <Tooltip label={`Sort by name ${sortBy === 'name' ? (sortDirection === 'asc' ? '(A-Z)' : '(Z-A)') : ''}`}>
                <Button
                  size="xs"
                  variant={sortBy === 'name' ? 'filled' : 'outline'}
                  onClick={() => handleSortToggle('name')}
                  rightSection={
                    sortBy === 'name' ? (
                      sortDirection === 'asc' ? <IconSortAscending size={12} /> : <IconSortDescending size={12} />
                    ) : null
                  }
                >
                  Name
                </Button>
              </Tooltip>
              <Tooltip label={`Sort by provider ${sortBy === 'provider' ? (sortDirection === 'asc' ? '(A-Z)' : '(Z-A)') : ''}`}>
                <Button
                  size="xs"
                  variant={sortBy === 'provider' ? 'filled' : 'outline'}
                  onClick={() => handleSortToggle('provider')}
                  rightSection={
                    sortBy === 'provider' ? (
                      sortDirection === 'asc' ? <IconSortAscending size={12} /> : <IconSortDescending size={12} />
                    ) : null
                  }
                >
                  Provider
                </Button>
              </Tooltip>
              <Tooltip label={`Sort by date ${sortBy === 'created_at' ? (sortDirection === 'asc' ? '(Oldest first)' : '(Newest first)') : ''}`}>
                <Button
                  size="xs"
                  variant={sortBy === 'created_at' ? 'filled' : 'outline'}
                  onClick={() => handleSortToggle('created_at')}
                  rightSection={
                    sortBy === 'created_at' ? (
                      sortDirection === 'asc' ? <IconSortAscending size={12} /> : <IconSortDescending size={12} />
                    ) : null
                  }
                >
                  Date
                </Button>
              </Tooltip>
            </Group>
          </Group>

          {filteredAndSortedConfigurations.length === 0 ? (
            <Text size="sm" c="dimmed" ta="center" py="xl">
              {searchQuery ? 'No configurations match your search.' : 'No saved configurations found.'}
            </Text>
          ) : (
            <Stack gap="xs">
              {filteredAndSortedConfigurations.map((config, index) => {
                const testId = config.id || `saved-${index}`;
                const testResult = testResults[testId];

                return (
                  <div key={config.id || index}>
                    <Card p="sm" withBorder>
                      <Group justify="space-between">
                        <div>
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
                            Created: {config.created_at ? new Date(config.created_at).toLocaleDateString() + ' ' + new Date(config.created_at).toLocaleTimeString() : 'Unknown'} by {(config as any).creator || 'System'}
                          </Text>
                        </div>
                        <Group gap="xs">
                          <ActionIcon
                            size="sm"
                            color="blue"
                            variant="light"
                            onClick={() => handleTestLLMConfiguration({
                              ...config,
                              api_key: config.api_key || '',
                              temperature: config.temperature ?? 0.7,
                              max_tokens: config.max_tokens ?? 4000
                            }, testId)}
                            loading={testingLLM === testId}
                            disabled={config.status === 'needs_key' && config.provider !== 'ollama'}
                            title="Test Configuration"
                          >
                            <IconTestPipe size={14} />
                          </ActionIcon>
                          <ActionIcon
                            size="sm"
                            color="green"
                            variant="light"
                            onClick={() => handleEditConfiguration({
                              ...config,
                              api_key: config.api_key || '',
                              temperature: config.temperature ?? 0.7,
                              max_tokens: config.max_tokens ?? 4000
                            })}
                            title="Edit Configuration"
                          >
                            <IconEdit size={14} />
                          </ActionIcon>
                          <ActionIcon
                            size="sm"
                            color="red"
                            variant="light"
                            loading={deletingConfig === (config.id || `${config.provider}-${config.model}`)}
                            onClick={() => handleDeleteConfiguration({
                              ...config,
                              api_key: config.api_key || '',
                              temperature: config.temperature ?? 0.7,
                              max_tokens: config.max_tokens ?? 4000
                            }, index)}
                            title="Delete Configuration"
                          >
                            <IconTrash size={14} />
                          </ActionIcon>
                        </Group>
                      </Group>
                    </Card>

                    {testResult && (
                      <Card p="md" withBorder mt="xs" style={{
                        backgroundColor: testResult.status === 'success' ? '#e8f5e8' : '#ffe8e8',
                      }}>
                        <Group justify="space-between" align="center">
                          <Group gap="xs">
                            <Text size="sm" fw={600}>
                              Test Result for {testResult.configName}:
                            </Text>
                            <Badge color={testResult.status === 'success' ? 'green' : 'red'}>
                              {testResult.status === 'success' ? 'Success' : 'Failed'}
                            </Badge>
                          </Group>
                          <ActionIcon
                            size="sm"
                            variant="subtle"
                            onClick={() => setTestResults(prev => {
                              const newResults = { ...prev };
                              delete newResults[testId];
                              return newResults;
                            })}
                          >
                            <IconX size={14} />
                          </ActionIcon>
                        </Group>
                        <Text size="sm" mt="sm">
                          {testResult.message}
                        </Text>
                      </Card>
                    )}
                  </div>
                );
              })}
            </Stack>
          )}
        </Card>
      )}
    </Stack>
  );
};
