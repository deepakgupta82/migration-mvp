import React, { useMemo, useEffect, useState, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { Group, Title, Text, Button, Badge, Card, SimpleGrid, Loader, Alert, Stack, Paper, ThemeIcon, Modal, Select } from '@mantine/core';
import { IconSettings, IconFile, IconTopologyStar, IconShare, IconDatabase, IconMessage, IconFolder, IconInfoCircle, IconRefresh } from '@tabler/icons-react';
import { apiService, Project } from '../../services/api';
import { useProjectStats } from '../../hooks/useStatsWebSocket';
import { notificationService } from '../../services/notificationService';

export const ProjectOverviewPage: React.FC = () => {
  const { projectId } = useParams();

  // Local state for real data
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [project, setProject] = useState<Project | null>(null);
  const [stats, setStats] = useState<any | null>(null);
  const [tokenUsage, setTokenUsage] = useState<number>(0);
  const [storageUsage, setStorageUsage] = useState<{total_size_mb?: number; total_files?: number} | null>(null);
  const [refreshing, setRefreshing] = useState<boolean>(false);

  // LLM Configuration Modal state
  const [llmConfigModalOpen, setLlmConfigModalOpen] = useState(false);
  const [llmConfigs, setLlmConfigs] = useState<any[]>([]);
  const [selectedLlmConfig, setSelectedLlmConfig] = useState('');
  const [testingLLM, setTestingLLM] = useState(false);
  const [testResult, setTestResult] = useState<any>(null);
  const [testQuery, setTestQuery] = useState('');
  const [selectedConfigName, setSelectedConfigName] = useState('');

  const loadData = useCallback(async () => {
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
  }, [projectId]);

  // Load token usage for the project
  const loadTokenUsage = useCallback(async () => {
    if (!projectId) return;
    try {
      const response = await fetch(`http://localhost:8002/api/usage/projects/${projectId}/token-usage`, {
        headers: {
          'Authorization': 'Bearer service-backend-token'
        }
      });
      if (response.ok) {
        const data = await response.json();
        setTokenUsage(data.total_tokens_used || 0);
      }
    } catch (error) {
      console.error('Failed to load token usage:', error);
      setTokenUsage(0);
    }
  }, [projectId]);

  // Load storage usage for the project
  const loadStorageUsage = useCallback(async () => {
    if (!projectId) return;
    try {
      const response = await fetch(`http://localhost:8002/api/usage/projects/${projectId}/storage-usage`, {
        headers: {
          'Authorization': 'Bearer service-backend-token'
        }
      });
      if (response.ok) {
        const data = await response.json();
        setStorageUsage(data.storage_usage || null);
      }
    } catch (error) {
      console.error('Failed to load storage usage:', error);
      setStorageUsage(null);
    }
  }, [projectId]);

  // Load LLM configurations
  const loadLLMConfigurations = useCallback(async () => {
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
  }, [project?.llm_api_key_id]);

  // Test selected LLM configuration
  const testSelectedLLMConfig = async () => {
    if (!selectedLlmConfig || !projectId) return;

    setTestingLLM(true);
    setTestResult(null);

    try {
      const testQuery = "TEST REQUEST: Please respond with 'TEST SUCCESSFUL - LLM is working correctly' to confirm connectivity.";
      setTestQuery(testQuery);

      // Find the selected configuration to get provider, model, and api_key
      const selectedConfig = llmConfigs.find(c => c && c.id?.toString() === selectedLlmConfig);
      if (!selectedConfig) {
        throw new Error('Selected configuration not found');
      }

      // Validate required fields
      if (!selectedConfig.provider || selectedConfig.provider.trim() === '') {
        throw new Error('LLM configuration is missing provider information');
      }
      if (!selectedConfig.model || selectedConfig.model.trim() === '') {
        throw new Error('LLM configuration is missing model information');
      }

      // Use POST endpoint to call LLM service (not direct backend testing)
      const response = await fetch('http://localhost:8000/api/llm/test-llm-config', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          config_id: selectedLlmConfig,
          provider: selectedConfig.provider.trim(),
          model: selectedConfig.model.trim(),
          api_key: selectedConfig.api_key,
          temperature: selectedConfig.temperature || 0.1,
          max_tokens: 100,
          query: testQuery
        }),
      });

      const result = await response.json();
      setTestResult({
        ...result,
        timestamp: new Date().toLocaleTimeString(),
        query: testQuery,
        configName: selectedConfigName
      });

      if (response.ok && result.status === 'success') {
        await notificationService.notifyLLMConfigTested(
          selectedConfigName,
          selectedConfig.provider,
          selectedConfig.model,
          true,
          {
            metadata: {
              projectId: projectId || '',
              projectName: project?.name || '',
              testResult: 'success',
              configId: selectedLlmConfig
            }
          }
        );
      } else {
        await notificationService.notifyLLMConfigTested(
          selectedConfigName,
          selectedConfig.provider,
          selectedConfig.model,
          false,
          {
            metadata: {
              projectId: projectId || '',
              projectName: project?.name || '',
              testResult: 'failed',
              error: result.message || 'Failed to connect to LLM',
              configId: selectedLlmConfig
            }
          }
        );
      }
    } catch (error) {
      setTestResult({
        status: 'error',
        message: `Test failed: ${error}`,
        timestamp: new Date().toLocaleTimeString(),
        query: testQuery,
        configName: selectedConfigName
      });

      await notificationService.notifyError(
        'LLM Configuration Test',
        `Test failed: ${error}`,
        {
          projectId: projectId || '',
          projectName: project?.name || '',
          operation: 'llm_test',
          configId: selectedLlmConfig
        }
      );
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
        await notificationService.notifyLLMConfigSaved(
          selectedConfig.name,
          selectedConfig.provider,
          selectedConfig.model,
          {
            metadata: {
              projectId: projectId || '',
              projectName: project?.name || '',
              configId: selectedConfig.id,
              operation: 'project_llm_update'
            }
          }
        );

        setLlmConfigModalOpen(false);

        // Refresh project data instead of full page reload
        if (projectId) {
          await loadData();
        }
      } else {
        throw new Error('Failed to update project');
      }
    } catch (error) {
      await notificationService.notifyError(
        'LLM Configuration Save',
        `Failed to save LLM configuration: ${error}`,
        {
          projectId: projectId || '',
          projectName: project?.name || '',
          operation: 'project_llm_save',
          configId: selectedLlmConfig
        }
      );
    }
  };

  useEffect(() => {
    if (projectId) {
      loadData();
    }
  }, [projectId, loadData]);

  // Load LLM configurations when component mounts and when modal opens
  useEffect(() => {
    if (project) {
      loadLLMConfigurations();
    }
  }, [project, loadLLMConfigurations]);

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
  }, [llmConfigModalOpen, loadLLMConfigurations]);

  // Load token and storage usage on mount and when project changes
  useEffect(() => {
    if (projectId) {
      loadTokenUsage();
      loadStorageUsage();
    }
  }, [projectId, loadTokenUsage, loadStorageUsage]);

  // Refresh all stats
  const refreshStats = useCallback(async () => {
    if (!projectId) return;
    setRefreshing(true);
    try {
      await Promise.all([
        loadTokenUsage(),
        loadStorageUsage()
      ]);
    } catch (error) {
      console.error('Failed to refresh stats:', error);
    } finally {
      setRefreshing(false);
    }
  }, [projectId, loadTokenUsage, loadStorageUsage]);

  // Live stats via WebSocket (fallback already inside the hook)
  const { stats: wsStats } = useProjectStats(projectId || '');
  useEffect(() => {
    if (wsStats) setStats(wsStats);
  }, [wsStats]);

  // Normalize stats from either stats-service or websocket-like shapes
  const filesCount = (stats?.files_count) ?? stats?.data?.files_count ?? stats?.data?.documents?.total ?? 0;
  const embeddingsCount = (stats?.embeddings_count) ?? stats?.data?.embeddings_count ?? stats?.data?.embeddings?.total ?? 0;
  const graphNodes = (stats?.graph_nodes) ?? stats?.data?.graph_nodes ?? stats?.data?.graph?.nodes ?? 0;
  const graphRelationships = (stats?.graph_relationships) ?? stats?.data?.graph_relationships ?? stats?.data?.graph?.relationships ?? 0;
  const deliverables = (stats?.deliverables) ?? stats?.data?.deliverables ?? 0;
  const lastUpdated = stats?.last_updated || stats?.data?.last_updated || project?.updated_at;

  // Stats badges data
  const statsBadges = useMemo(() => [
    {
      label: 'Files Uploaded',
      value: filesCount,
      icon: IconFile,
      color: 'blue'
    },
    {
      label: 'Graph Nodes',
      value: graphNodes,
      icon: IconShare,
      color: 'green'
    },
    {
      label: 'Embeddings',
      value: embeddingsCount,
      icon: IconTopologyStar,
      color: 'violet'
    },
    {
      label: 'Graph Edges',
      value: graphRelationships,
      icon: IconDatabase,
      color: 'orange'
    },
    {
      label: 'Tokens Used',
      value: tokenUsage,
      icon: IconMessage,
      color: 'teal'
    },
    {
      label: 'Documents Processed',
      value: filesCount, // Using files count as proxy
      icon: IconFile,
      color: 'cyan'
    },
    {
      label: 'Documents Created',
      value: deliverables,
      icon: IconFolder,
      color: 'pink'
    },
    {
      label: 'Space Used',
      value: storageUsage?.total_size_mb ? `${storageUsage.total_size_mb.toFixed(2)} MB` : '0.00 MB',
      icon: IconDatabase,
      color: 'gray'
    }
  ], [filesCount, embeddingsCount, graphNodes, graphRelationships, deliverables, tokenUsage, storageUsage]);

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
                {(() => {
                  const configName = llmConfigs.find(c => c && c.id?.toString() === project?.llm_api_key_id?.toString())?.name;
                  return configName ? `${configName} (${project.llm_provider.toUpperCase()} / ${project.llm_model})` : `${project.llm_provider.toUpperCase()} / ${project.llm_model}`;
                })()}
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

      {/* Stats Badges */}
      <Card withBorder p="lg">
        <Group justify="space-between" align="center" mb="md">
          <Title order={4} m={0}>Project Statistics</Title>
          <Button
            size="xs"
            variant="light"
            leftSection={<IconRefresh size={14} />}
            onClick={refreshStats}
            loading={refreshing}
          >
            {refreshing ? 'Refreshing...' : 'Refresh'}
          </Button>
        </Group>
        <SimpleGrid cols={3} spacing="md">
          {statsBadges.map((badge, index) => (
            <Card key={index} p="sm" radius="md" withBorder style={{ minHeight: '80px' }}>
              <Group justify="space-between" align="center" wrap="nowrap" h="100%">
                <Group gap="xs" align="center">
                  <ThemeIcon size={32} radius="md" variant="light" color={badge.color}>
                    <badge.icon size={16} />
                  </ThemeIcon>
                  <div>
                    <Text size="xs" fw={600} c="dimmed" tt="uppercase">
                      {badge.label}
                    </Text>
                    <Text size="lg" fw={700} c="dark.8">
                      {typeof badge.value === 'string' ? badge.value : badge.value.toLocaleString()}
                    </Text>
                  </div>
                </Group>
              </Group>
            </Card>
          ))}
        </SimpleGrid>
      </Card>

      {/* Info Panel */}
      <Card withBorder p="lg">
        <Group gap="xs" align="center" mb="md">
          <IconInfoCircle size={20} />
          <Title order={4} m={0}>Project Information</Title>
        </Group>
        <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md">
          <div>
            <Text size="xs" c="dimmed" fw={600} tt="uppercase">Created</Text>
            <Text>{project?.created_at ? new Date(project.created_at).toLocaleString() : '—'}</Text>
          </div>
          <div>
            <Text size="xs" c="dimmed" fw={600} tt="uppercase">Last Updated</Text>
            <Text>{lastUpdated ? new Date(lastUpdated).toLocaleString() : '—'}</Text>
          </div>
          <div>
            <Text size="xs" c="dimmed" fw={600} tt="uppercase">Project ID</Text>
            <Text style={{ wordBreak: 'break-all' }}>{project?.id || projectId || '—'}</Text>
          </div>
          <div>
            <Text size="xs" c="dimmed" fw={600} tt="uppercase">Status</Text>
            <Badge variant="light" color={project?.status === 'running' ? 'green' : 'gray'}>
              {project?.status || '—'}
            </Badge>
          </div>
        </SimpleGrid>
        <div style={{ marginTop: '16px' }}>
          <Text size="xs" c="dimmed" fw={600} tt="uppercase">Description</Text>
          <Text>{project?.description || 'No description available'}</Text>
        </div>
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
