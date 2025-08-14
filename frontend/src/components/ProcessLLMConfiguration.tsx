import React, { useState, useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '../ui/card';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Alert, AlertDescription } from '../ui/alert';
import { Loader2, Settings, TestTube, Trash2, Save } from 'lucide-react';

const ProcessLLMConfiguration = ({ projectId }) => {
  const [configs, setConfigs] = useState({});
  const [recommendations, setRecommendations] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState({});
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const processTypes = [
    {
      key: 'entity_extraction',
      name: 'Entity Extraction',
      description: 'Extract infrastructure entities and relationships from documents',
      priority: 'High'
    },
    {
      key: 'crew_assessment',
      name: 'CrewAI Assessment',
      description: 'Multi-agent infrastructure assessment and migration planning',
      priority: 'High'
    },
    {
      key: 'crew_documentation',
      name: 'CrewAI Documentation',
      description: 'Generate professional documentation and reports',
      priority: 'Medium'
    },
    {
      key: 'rag_synthesis',
      name: 'RAG Synthesis',
      description: 'Synthesize search results into coherent responses',
      priority: 'Medium'
    },
    {
      key: 'hybrid_search',
      name: 'Hybrid Search',
      description: 'Generate Cypher queries for graph databases',
      priority: 'Low'
    }
  ];

  const providers = [
    { key: 'openai', name: 'OpenAI', models: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-3.5-turbo'] },
    { key: 'anthropic', name: 'Anthropic', models: ['claude-3-opus-20240229', 'claude-3-sonnet-20240229', 'claude-3-haiku-20240307'] },
    { key: 'gemini', name: 'Google Gemini', models: ['gemini-1.5-pro', 'gemini-1.5-flash', 'gemini-1.0-pro'] },
    { key: 'ollama', name: 'Ollama (Local)', models: ['llama3.1:70b', 'llama3.1:8b', 'mixtral:8x7b', 'codestral:22b'] }
  ];

  useEffect(() => {
    loadConfigurations();
  }, [projectId]);

  const loadConfigurations = async () => {
    try {
      setLoading(true);
      const response = await fetch(`/api/projects/${projectId}/llm-process-configs`);
      if (response.ok) {
        const data = await response.json();
        setConfigs(data);
      } else {
        throw new Error('Failed to load configurations');
      }
    } catch (err) {
      setError('Failed to load LLM configurations');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const loadRecommendations = async (processType) => {
    try {
      const response = await fetch(`/api/projects/recommendations/${processType}`);
      if (response.ok) {
        const data = await response.json();
        setRecommendations(prev => ({ ...prev, [processType]: data }));
      }
    } catch (err) {
      console.error(`Failed to load recommendations for ${processType}:`, err);
    }
  };

  const updateProcessConfig = (processType, config) => {
    setConfigs(prev => ({
      ...prev,
      [processType]: config
    }));
  };

  const saveConfigurations = async () => {
    try {
      setSaving(true);
      setError('');
      setSuccess('');

      const response = await fetch(`/api/projects/${projectId}/llm-process-configs`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(configs)
      });

      if (response.ok) {
        setSuccess('LLM configurations saved successfully');
        setTimeout(() => setSuccess(''), 3000);
      } else {
        throw new Error('Failed to save configurations');
      }
    } catch (err) {
      setError('Failed to save configurations');
      console.error(err);
    } finally {
      setSaving(false);
    }
  };

  const testProcessLLM = async (processType) => {
    try {
      setTesting(prev => ({ ...prev, [processType]: true }));
      
      const response = await fetch(`/api/projects/${projectId}/test-process-llm/${processType}`);
      const result = await response.json();
      
      if (result.status === 'success') {
        setSuccess(`${processType} LLM test successful`);
        setTimeout(() => setSuccess(''), 3000);
      } else {
        setError(`${processType} LLM test failed: ${result.message}`);
      }
    } catch (err) {
      setError(`Failed to test ${processType} LLM`);
      console.error(err);
    } finally {
      setTesting(prev => ({ ...prev, [processType]: false }));
    }
  };

  const deleteProcessConfig = async (processType) => {
    try {
      const response = await fetch(`/api/projects/${projectId}/llm-process-configs/${processType}`, {
        method: 'DELETE'
      });

      if (response.ok) {
        setConfigs(prev => {
          const updated = { ...prev };
          delete updated[processType];
          return updated;
        });
        setSuccess(`Deleted ${processType} configuration`);
        setTimeout(() => setSuccess(''), 3000);
      } else {
        throw new Error('Failed to delete configuration');
      }
    } catch (err) {
      setError(`Failed to delete ${processType} configuration`);
      console.error(err);
    }
  };

  const getPriorityColor = (priority) => {
    switch (priority) {
      case 'High': return 'bg-red-100 text-red-800';
      case 'Medium': return 'bg-yellow-100 text-yellow-800';
      case 'Low': return 'bg-green-100 text-green-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  if (loading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center p-8">
          <Loader2 className="animate-spin h-8 w-8 mr-2" />
          <span>Loading LLM configurations...</span>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold flex items-center">
            <Settings className="mr-2" />
            Process-Specific LLM Configuration
          </h2>
          <p className="text-gray-600 mt-1">
            Configure different LLM models for different AI processes to optimize cost and performance.
          </p>
        </div>
        <Button
          onClick={saveConfigurations}
          disabled={saving}
          className="flex items-center"
        >
          {saving ? (
            <Loader2 className="animate-spin h-4 w-4 mr-2" />
          ) : (
            <Save className="h-4 w-4 mr-2" />
          )}
          Save All Configurations
        </Button>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {success && (
        <Alert>
          <AlertDescription>{success}</AlertDescription>
        </Alert>
      )}

      <div className="grid gap-6">
        {processTypes.map((process) => (
          <Card key={process.key} className="border-l-4 border-l-blue-500">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="flex items-center">
                    {process.name}
                    <Badge className={`ml-2 ${getPriorityColor(process.priority)}`}>
                      {process.priority} Priority
                    </Badge>
                  </CardTitle>
                  <p className="text-sm text-gray-600 mt-1">{process.description}</p>
                </div>
                <div className="flex space-x-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => testProcessLLM(process.key)}
                    disabled={testing[process.key] || !configs[process.key]}
                  >
                    {testing[process.key] ? (
                      <Loader2 className="animate-spin h-4 w-4" />
                    ) : (
                      <TestTube className="h-4 w-4" />
                    )}
                  </Button>
                  {configs[process.key] && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => deleteProcessConfig(process.key)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <ProcessConfigForm
                processType={process.key}
                config={configs[process.key]}
                providers={providers}
                onConfigChange={(config) => updateProcessConfig(process.key, config)}
                onLoadRecommendations={() => loadRecommendations(process.key)}
                recommendations={recommendations[process.key]}
              />
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
};

const ProcessConfigForm = ({ 
  processType, 
  config, 
  providers, 
  onConfigChange, 
  onLoadRecommendations, 
  recommendations 
}) => {
  const [formData, setFormData] = useState(
    config || { 
      provider: '', 
      model: '', 
      api_key_id: '', 
      temperature: 0.1, 
      max_tokens: 4000 
    }
  );

  useEffect(() => {
    if (config) {
      setFormData(config);
    }
  }, [config]);

  useEffect(() => {
    onLoadRecommendations();
  }, [processType]);

  const handleChange = (field, value) => {
    const updated = { ...formData, [field]: value };
    setFormData(updated);
    onConfigChange(updated);
  };

  const selectedProvider = providers.find(p => p.key === formData.provider);

  return (
    <div className="space-y-4">
      {!config && (
        <div className="bg-gray-50 p-4 rounded-md">
          <p className="text-sm text-gray-600">
            No process-specific configuration. Will fall back to project default LLM.
          </p>
        </div>
      )}

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium mb-1">Provider</label>
          <select
            value={formData.provider}
            onChange={(e) => handleChange('provider', e.target.value)}
            className="w-full p-2 border rounded-md"
          >
            <option value="">Select Provider</option>
            {providers.map((provider) => (
              <option key={provider.key} value={provider.key}>
                {provider.name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Model</label>
          <select
            value={formData.model}
            onChange={(e) => handleChange('model', e.target.value)}
            className="w-full p-2 border rounded-md"
            disabled={!selectedProvider}
          >
            <option value="">Select Model</option>
            {selectedProvider?.models.map((model) => (
              <option key={model} value={model}>
                {model}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Temperature</label>
          <input
            type="number"
            min="0"
            max="2"
            step="0.1"
            value={formData.temperature}
            onChange={(e) => handleChange('temperature', parseFloat(e.target.value))}
            className="w-full p-2 border rounded-md"
          />
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Max Tokens</label>
          <input
            type="number"
            min="100"
            max="8000"
            value={formData.max_tokens}
            onChange={(e) => handleChange('max_tokens', parseInt(e.target.value))}
            className="w-full p-2 border rounded-md"
          />
        </div>
      </div>

      {recommendations && (
        <div className="bg-blue-50 p-4 rounded-md">
          <h4 className="font-medium text-blue-900 mb-2">Recommended Models:</h4>
          <div className="grid grid-cols-2 gap-4 text-sm">
            {Object.entries(recommendations.recommendations).map(([provider, models]) => (
              <div key={provider}>
                <span className="font-medium capitalize">{provider}:</span>
                <ul className="ml-2 text-blue-700">
                  {models.map((model) => (
                    <li key={model} className="cursor-pointer hover:underline"
                        onClick={() => {
                          handleChange('provider', provider);
                          handleChange('model', model);
                        }}>
                      • {model}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default ProcessLLMConfiguration;
