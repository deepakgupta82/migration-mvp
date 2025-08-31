import React, { useMemo, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Group, Title, Text, Button, Badge, Card, SimpleGrid, Loader, Alert, Collapse, ActionIcon, Stack, Modal, Select, Paper } from '@mantine/core';
import { IconTrash, IconRefresh, IconChevronRight, IconChevronDown, IconSettings } from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';
import { apiService, Project } from '../../services/api';
import { useProjectStats } from '../../hooks/useStatsWebSocket';

type EssentialsField = { label: string; value: string | React.ReactNode };

export const ProjectOverviewPage: React.FC = () => {
  const { projectId } = useParams();

  // Local state for real data
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [project, setProject] = useState<Project | null>(null);
  const [stats, setStats] = useState<any | null>(null);
  const [statsOpen, setStatsOpen] = useState<boolean>(true);

  // LLM Configuration Modal state
  const [llmConfigModalOpen, setLlmConfigModalOpen] = useState(false);
  const [llmConfigs, setLlmConfigs] = useState<any[]>([]);
  const [selectedLlmConfig, setSelectedLlmConfig] = useState('');
  const [testingLLM, setTestingLLM] = useState(false);
  const [testResult, setTestResult] = useState<any>(null);
  const [testQuery, setTestQuery] = useState('');
  const [selectedConfigName, setSelectedConfigName] = useState('');

  const loadData = async () => {
    if (!projectId) return;
    setLoading(true);
    setError(null);
    try {
  const p = await apiService.getProject(projectId);
  setProject(p);
    } catch (e: any) {
      setError(e?.message || 'Failed to load project overview');
    } finally {
      setLoading(false);
    }
  };

  // Load LLM configurations
  const loadLLMConfigurations = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/llm/configurations');
      if (response.ok) {
  const configs = await response.json();
  setLlmConfigs(Array.isArray(configs) ? configs : []);
        // Set current project's LLM config as selected only if we have project data
        if (project?.llm_api_key_id && configs.length > 0) {
          const configExists = configs.find((c: any) => c && c.id?.toString() === project.llm_api_key_id?.toString());
          if (configExists) {
            setSelectedLlmConfig(project.llm_api_key_id.toString());
          }
        }
      }
    } catch (error) {
      console.error('Failed to load LLM configurations:', error);
    }
  };

  // Test LLM configuration
  const testProjectLLM = async () => {
    if (!projectId || !project?.llm_api_key_id) return;

    setTestingLLM(true);
    setTestResult(null);

    try {
      const testQuery = "TEST REQUEST: Please respond with 'TEST SUCCESSFUL - LLM is working correctly' to confirm connectivity.";
      setTestQuery(testQuery);

      // Use unified GET test endpoint (server handles API key retrieval)
  const response = await fetch(`http://localhost:8000/api/llm/test-llm-config?config_id=${encodeURIComponent(project.llm_api_key_id.toString())}&test_query=${encodeURIComponent(testQuery)}`, {
        method: 'GET'
      });

      const result = await response.json();
      setTestResult({
        ...result,
        timestamp: new Date().toLocaleTimeString(),
        query: testQuery,
        configName: `${project.llm_provider}/${project.llm_model}`
      });

      if (response.ok && result.status === 'success') {
        notifications.show({
          title: 'LLM Test Successful',
          message: `${project?.llm_provider}/${project?.llm_model} is working correctly. Check details below.`,
          color: 'green',
        });
      } else {
        notifications.show({
          title: 'LLM Test Failed',
          message: result.message || 'Failed to connect to LLM. Check details below.',
          color: 'red',
        });
      }
    } catch (error) {
      setTestResult({
        status: 'error',
        message: `Test failed: ${error}`,
        timestamp: new Date().toLocaleTimeString(),
        query: "TEST REQUEST: Please respond with 'TEST SUCCESSFUL - LLM is working correctly' to confirm connectivity.",
        configName: `${project?.llm_provider || 'Unknown'}/${project?.llm_model || 'Unknown'}`
      });

      notifications.show({
        title: 'LLM Test Error',
        message: 'Failed to test LLM configuration. Check details below.',
        color: 'red',
      });
    } finally {
      setTestingLLM(false);
    }
  };

  // Test selected LLM configuration
  const testSelectedLLMConfig = async () => {
    if (!selectedLlmConfig || !projectId) return;

    setTestingLLM(true);
    setTestResult(null);

    try {
      const testQuery = "TEST REQUEST: Please respond with 'TEST SUCCESSFUL - LLM is working correctly' to confirm connectivity.";
      setTestQuery(testQuery);

      // Use unified GET test endpoint (server handles API key retrieval)
  const response = await fetch(`http://localhost:8000/api/llm/test-llm-config?config_id=${encodeURIComponent(selectedLlmConfig)}&test_query=${encodeURIComponent(testQuery)}`, {
        method: 'GET'
      });

      const result = await response.json();
      setTestResult({
        ...result,
        timestamp: new Date().toLocaleTimeString(),
        query: testQuery,
        configName: selectedConfigName
      });

      if (response.ok && result.status === 'success') {
        notifications.show({
          title: 'LLM Test Successful',
          message: `${selectedConfigName} is working correctly. You can now save this configuration.`,
          color: 'green',
        });
      } else {
        notifications.show({
          title: 'LLM Test Failed',
          message: result.message || 'Failed to connect to LLM. Check details below.',
          color: 'red',
        });
      }
    } catch (error) {
      setTestResult({
        status: 'error',
        message: `Test failed: ${error}`,
        timestamp: new Date().toLocaleTimeString(),
        query: testQuery,
        configName: selectedConfigName
      });

      notifications.show({
        title: 'LLM Test Error',
        message: 'Failed to test LLM configuration. Check details below.',
        color: 'red',
      });
    } finally {
      setTestingLLM(false);
    }
  };

  // Save project LLM configuration
  const saveProjectLLM = async () => {
    if (!projectId || !selectedLlmConfig) return;

    try {
  const selectedConfig = llmConfigs.find(c => c && c.id?.toString() === selectedLlmConfig);
      if (!selectedConfig) return;

      setSelectedConfigName(selectedConfig.name);

      // Update the project with selected LLM configuration
      const updateResponse = await fetch(`http://localhost:8000/api/projects/${projectId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          llm_provider: selectedConfig.provider,
          llm_model: selectedConfig.model,
          llm_api_key_id: selectedConfig.id,
          llm_temperature: selectedConfig.temperature?.toString() || '0.1',
          llm_max_tokens: selectedConfig.max_tokens?.toString() || '4000'
        }),
      });

      if (updateResponse.ok) {
        notifications.show({
          title: 'LLM Configuration Saved',
          message: `Project now uses ${selectedConfig.name}`,
          color: 'green',
        });

        setLlmConfigModalOpen(false);

        // Refresh project data instead of full page reload
        if (projectId) {
          await loadData();
        }
      } else {
        throw new Error('Failed to update project');
      }
    } catch (error) {
      notifications.show({
        title: 'Save Failed',
        message: 'Failed to save LLM configuration',
        color: 'red',
      });
    }
  };

  useEffect(() => {
    if (projectId) {
      loadData();
    }
  }, [projectId]);

  // Load LLM configurations when component mounts and when modal opens
  useEffect(() => {
    if (project) {
      loadLLMConfigurations();
    }
  }, [project]);

  // Set selected config when both project and configs are available
  useEffect(() => {
    if (project?.llm_api_key_id && llmConfigs.length > 0 && !selectedLlmConfig) {
      const configExists = llmConfigs.find(c => c && c.id?.toString() === project.llm_api_key_id?.toString());
      if (configExists) {
        setSelectedLlmConfig(project.llm_api_key_id.toString());
      }
    }
  }, [project, llmConfigs, selectedLlmConfig]);

  useEffect(() => {
    if (llmConfigModalOpen) {
      loadLLMConfigurations();
    }
  }, [llmConfigModalOpen]);

  const projectName = project?.name || projectId || '—';
  // Live stats via WebSocket (fallback already inside the hook)
  const { stats: wsStats, refreshStats } = useProjectStats(projectId || '');
  useEffect(() => {
    if (wsStats) setStats(wsStats);
  }, [wsStats]);

  // Normalize stats from either stats-service or websocket-like shapes
  const filesCount = (stats?.files_count) ?? stats?.data?.files_count ?? stats?.data?.documents?.total ?? 0;
  const embeddingsCount = (stats?.embeddings_count) ?? stats?.data?.embeddings_count ?? stats?.data?.embeddings?.total ?? 0;
  const graphNodes = (stats?.graph_nodes) ?? stats?.data?.graph_nodes ?? stats?.data?.graph?.nodes ?? 0;
  const graphRelationships = (stats?.graph_relationships) ?? stats?.data?.graph_relationships ?? stats?.data?.graph?.relationships ?? 0;
  const lastUpdated = stats?.last_updated || stats?.data?.last_updated || project?.updated_at;

  const essentials: EssentialsField[] = useMemo(() => [
    { label: 'Client', value: project?.client_name || '—' },
    { label: 'Status', value: project?.status || '—' },
    { label: 'Files', value: String(filesCount) },
    { label: 'Embeddings', value: String(embeddingsCount) },
    { label: 'Graph nodes', value: String(graphNodes) },
    { label: 'Graph edges', value: String(graphRelationships) },
    { label: 'Created', value: project?.created_at ? new Date(project.created_at).toLocaleString() : '—' },
    { label: 'Updated', value: lastUpdated ? new Date(lastUpdated).toLocaleString() : '—' },
    { label: 'Project ID', value: project?.id || projectId || '—' },
    { label: 'Description', value: project?.description || '—' },
  ], [project, filesCount, embeddingsCount, graphNodes, graphRelationships, lastUpdated, projectId]);

  return (
    <Stack gap="md">
      {loading && (
        <Group justify="center" p="md"><Loader /></Group>
      )}
      {error && (
        <Alert color="red" title="Failed to load overview">{error}</Alert>
      )}
      {/* LLM Configuration (compact section) */}
      <Card withBorder p="sm">
        <Group justify="space-between" align="center">
          <Group gap="xs" align="center">
            <IconSettings size={14} />
            <Text size="sm" fw={600}>LLM Configuration</Text>
            {project?.llm_provider && project?.llm_model && (
              <Badge variant="light" color="blue" size="xs">
                {project.llm_provider.toUpperCase()} / {project.llm_model}
              </Badge>
            )}
          </Group>
          <Button
            size="xs"
            variant="light"
            leftSection={<IconSettings size={12} />}
            onClick={() => setLlmConfigModalOpen(true)}
          >
            Configure
          </Button>
        </Group>
      </Card>

      {/* Stats (collapsible) */}
      <Card withBorder>
        <Group justify="space-between" mb="sm" align="center">
          <Group gap="xs" align="center" onClick={() => setStatsOpen((s) => !s)} style={{ cursor: 'pointer' }}>
            <ActionIcon variant="subtle" size="sm">
              {statsOpen ? <IconChevronDown size={16} /> : <IconChevronRight size={16} />}
            </ActionIcon>
            <Title order={4} m={0}>Stats</Title>
          </Group>
        </Group>
        <Collapse in={statsOpen}>
          <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md">
            {essentials.map((f) => (
              <div key={f.label}>
                <Text size="xs" c="dimmed" fw={600} tt="uppercase">{f.label}</Text>
                <Text>{f.value}</Text>
              </div>
            ))}
          </SimpleGrid>
        </Collapse>
      </Card>

      {/* LLM Configuration Modal */}
      <Modal
        opened={llmConfigModalOpen}
        onClose={() => setLlmConfigModalOpen(false)}
        title="Change LLM Configuration"
        size="md"
      >
        <Stack gap="md">
          <Text size="sm" c="dimmed">
            Select a different LLM configuration for this project. The LLM will be tested immediately after selection.
          </Text>

          <Select
            label="LLM Configuration"
            placeholder={llmConfigs.length === 0 ? "Loading configurations..." : "Select an LLM configuration"}
            value={selectedLlmConfig || ''}
            onChange={(value) => setSelectedLlmConfig((value as string) || '')}
            data={Array.isArray(llmConfigs)
              ? llmConfigs
                  .filter((config: any) => config && (config.id != null) && config.name)
                  .map((config: any) => ({
                    value: String(config.id),
                    label: `${String(config.name)} (${config.provider || 'unknown'}/${config.model || 'unknown'}) - ${config.status === 'configured' ? 'Ready' : 'Needs API Key'}`
                  }))
              : []}
            searchable
            disabled={llmConfigs.length === 0}
            rightSection={llmConfigs.length === 0 ? <Loader size="xs" /> : undefined}
          />

          {selectedLlmConfig && (
            <Paper p="sm" withBorder radius="md" style={{ backgroundColor: '#f8f9fa' }}>
              {(() => {
                const selectedConfig = llmConfigs.find(c => c && c.id?.toString() === selectedLlmConfig);
                return selectedConfig ? (
                  <div>
                    <Text size="sm" fw={600} mb="xs">Selected Configuration:</Text>
                    <Group gap="xs" mb="xs">
                      <Text size="sm" c="dimmed">Name:</Text>
                      <Text size="sm">{selectedConfig.name}</Text>
                    </Group>
                    <Group gap="xs" mb="xs">
                      <Text size="sm" c="dimmed">Provider:</Text>
                      <Text size="sm">{selectedConfig.provider}</Text>
                    </Group>
                    <Group gap="xs">
                      <Text size="sm" c="dimmed">Model:</Text>
                      <Text size="sm">{selectedConfig.model}</Text>
                    </Group>
                  </div>
                ) : null;
              })()}
            </Paper>
          )}

          {/* Test Results Display */}
          {testResult && (
            <Paper p="md" withBorder radius="md" style={{
              backgroundColor: testResult.status === 'success' ? '#e8f5e8' : '#ffe8e8',
              marginLeft: '0px' // Fix left cutoff
            }}>
              <Stack gap="sm">
                <Group gap="xs">
                  <Text size="sm" fw={600}>
                    Test Result for {selectedConfigName}:
                  </Text>
                  <Badge color={testResult.status === 'success' ? 'green' : 'red'}>
                    {testResult.status === 'success' ? 'Success' : 'Failed'}
                  </Badge>
                </Group>

                <div>
                  <Text size="xs" c="dimmed" mb="xs">Query sent to LLM:</Text>
                  <Paper p="xs" style={{ backgroundColor: '#f0f0f0', fontFamily: 'monospace', fontSize: '12px' }}>
                    {testQuery}
                  </Paper>
                </div>

                <div>
                  <Text size="xs" c="dimmed" mb="xs">
                    {testResult.status === 'success' ? 'Response received:' : 'Error message:'}
                  </Text>
                  <Paper p="xs" style={{
                    backgroundColor: testResult.status === 'success' ? '#e8f5e8' : '#ffe8e8',
                    fontFamily: 'monospace',
                    fontSize: '12px',
                    marginLeft: '0px' // Fix left cutoff
                  }}>
                    {testResult.status === 'success'
                      ? (typeof testResult.response === 'string' ? testResult.response : JSON.stringify(testResult.response, null, 2))
                      : (typeof testResult.message === 'string' ? testResult.message : JSON.stringify(testResult.message, null, 2))}
                  </Paper>
                </div>

                {testResult.status === 'success' && (
                  <Text size="xs" c="green" fw={500}>
                    ✅ LLM configuration is working correctly. Project will be updated.
                  </Text>
                )}

                {testResult.status === 'error' && (
                  <Text size="xs" c="red" fw={500}>
                    ❌ LLM configuration failed. Project will not be updated.
                  </Text>
                )}
              </Stack>
            </Paper>
          )}

          <Group justify="flex-end" gap="sm">
            <Button
              variant="subtle"
              onClick={() => setLlmConfigModalOpen(false)}
            >
              Cancel
            </Button>
            <Button
              onClick={() => testSelectedLLMConfig()}
              disabled={!selectedLlmConfig}
              loading={testingLLM}
              variant="outline"
              color="blue"
            >
              {testingLLM ? 'Testing...' : 'Test LLM'}
            </Button>
            <Button
              onClick={saveProjectLLM}
              disabled={!selectedLlmConfig}
            >
              Save LLM Configuration
            </Button>
          </Group>
        </Stack>
      </Modal>

    </Stack>
  );
};
