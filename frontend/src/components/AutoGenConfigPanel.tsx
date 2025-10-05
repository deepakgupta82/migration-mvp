import React, { useState, useEffect } from 'react';
import {
  Paper,
  Title,
  Text,
  Stack,
  Group,
  NumberInput,
  Switch,
  Button,
  Alert,
  Divider,
  Badge,
  Loader,
  Tooltip,
} from '@mantine/core';
import { IconSettings, IconDeviceFloppy, IconRefresh, IconInfoCircle, IconAlertCircle, IconCheck } from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';
import { apiService } from '../services/api';

interface AutoGenConfig {
  vector_limit: number;
  graph_fact_limit: number;
  doc_insight_limit: number;
  context_rerank_enabled: boolean;
  timestamp: string;
}

export const AutoGenConfigPanel: React.FC = () => {
  const [config, setConfig] = useState<AutoGenConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);

  // Draft values for editing
  const [vectorLimit, setVectorLimit] = useState(5);
  const [graphFactLimit, setGraphFactLimit] = useState(8);
  const [docInsightLimit, setDocInsightLimit] = useState(5);
  const [contextRerankEnabled, setContextRerankEnabled] = useState(true);

  useEffect(() => {
    loadConfig();
  }, []);

  useEffect(() => {
    if (config) {
      const changed =
        vectorLimit !== config.vector_limit ||
        graphFactLimit !== config.graph_fact_limit ||
        docInsightLimit !== config.doc_insight_limit ||
        contextRerankEnabled !== config.context_rerank_enabled;
      setHasChanges(changed);
    }
  }, [vectorLimit, graphFactLimit, docInsightLimit, contextRerankEnabled, config]);

  const loadConfig = async () => {
    setLoading(true);
    try {
      const data = await apiService.getAutoGenConfig();
      setConfig(data);
      setVectorLimit(data.vector_limit);
      setGraphFactLimit(data.graph_fact_limit);
      setDocInsightLimit(data.doc_insight_limit);
      setContextRerankEnabled(data.context_rerank_enabled);
    } catch (error: any) {
      notifications.show({
        title: 'Error Loading Configuration',
        message: error.message || 'Failed to load AutoGen configuration',
        color: 'red',
      });
    } finally {
      setLoading(false);
    }
  };

  const saveConfig = async () => {
    setSaving(true);
    try {
      const updates: Partial<AutoGenConfig> = {};
      
      if (vectorLimit !== config?.vector_limit) updates.vector_limit = vectorLimit;
      if (graphFactLimit !== config?.graph_fact_limit) updates.graph_fact_limit = graphFactLimit;
      if (docInsightLimit !== config?.doc_insight_limit) updates.doc_insight_limit = docInsightLimit;
      if (contextRerankEnabled !== config?.context_rerank_enabled) updates.context_rerank_enabled = contextRerankEnabled;

      const data = await apiService.updateAutoGenConfig(updates);
      setConfig(data);
      setHasChanges(false);

      notifications.show({
        title: 'Configuration Updated',
        message: 'AutoGen settings have been updated successfully',
        color: 'green',
        icon: <IconCheck size={16} />,
      });
    } catch (error: any) {
      notifications.show({
        title: 'Error Saving Configuration',
        message: error.message || 'Failed to update AutoGen configuration',
        color: 'red',
        icon: <IconAlertCircle size={16} />,
      });
    } finally {
      setSaving(false);
    }
  };

  const resetToDefaults = () => {
    if (config) {
      setVectorLimit(config.vector_limit);
      setGraphFactLimit(config.graph_fact_limit);
      setDocInsightLimit(config.doc_insight_limit);
      setContextRerankEnabled(config.context_rerank_enabled);
      setHasChanges(false);
    }
  };

  if (loading) {
    return (
      <Paper p="md" radius="md" withBorder>
        <Group justify="center" p="xl">
          <Loader size="md" />
          <Text size="sm" c="dimmed">Loading configuration...</Text>
        </Group>
      </Paper>
    );
  }

  return (
    <Paper p="md" radius="md" withBorder>
      <Stack gap="md">
        <Group justify="space-between">
          <Group gap="sm">
            <IconSettings size={24} />
            <Title order={3}>AutoGen Configuration</Title>
          </Group>
          {config && (
            <Badge size="sm" variant="light" color="blue">
              Last updated: {new Date(config.timestamp).toLocaleString()}
            </Badge>
          )}
        </Group>

        <Alert icon={<IconInfoCircle size={16} />} color="blue" variant="light">
          <Text size="sm">
            These settings control context gathering limits for AutoGen discussions and chat.
            Changes apply immediately and persist until service restart.
          </Text>
        </Alert>

        <Divider />

        <Stack gap="lg">
          {/* Vector Search Limit */}
          <div>
            <Group gap="xs" mb="xs">
              <Text size="sm" fw={600}>Vector Search Snippets</Text>
              <Tooltip label="Maximum number of semantic search results to retrieve from vector database" withinPortal>
                <IconInfoCircle size={14} style={{ opacity: 0.5 }} />
              </Tooltip>
            </Group>
            <NumberInput
              value={vectorLimit}
              onChange={(val) => setVectorLimit(Number(val))}
              min={1}
              max={20}
              step={1}
              size="sm"
              description="Range: 1-20 (default: 5)"
            />
          </div>

          {/* Graph Facts Limit */}
          <div>
            <Group gap="xs" mb="xs">
              <Text size="sm" fw={600}>Knowledge Graph Facts</Text>
              <Tooltip label="Maximum number of facts to retrieve from knowledge graph" withinPortal>
                <IconInfoCircle size={14} style={{ opacity: 0.5 }} />
              </Tooltip>
            </Group>
            <NumberInput
              value={graphFactLimit}
              onChange={(val) => setGraphFactLimit(Number(val))}
              min={1}
              max={50}
              step={1}
              size="sm"
              description="Range: 1-50 (default: 8)"
            />
          </div>

          {/* Document Insights Limit */}
          <div>
            <Group gap="xs" mb="xs">
              <Text size="sm" fw={600}>Document Insights</Text>
              <Tooltip label="Maximum number of insights to retrieve from document analysis" withinPortal>
                <IconInfoCircle size={14} style={{ opacity: 0.5 }} />
              </Tooltip>
            </Group>
            <NumberInput
              value={docInsightLimit}
              onChange={(val) => setDocInsightLimit(Number(val))}
              min={1}
              max={20}
              step={1}
              size="sm"
              description="Range: 1-20 (default: 5)"
            />
          </div>

          {/* Context Re-ranking */}
          <div>
            <Group gap="xs" mb="xs">
              <Text size="sm" fw={600}>Context Re-ranking</Text>
              <Tooltip label="Enable semantic re-ranking of context results for better relevance" withinPortal>
                <IconInfoCircle size={14} style={{ opacity: 0.5 }} />
              </Tooltip>
            </Group>
            <Switch
              checked={contextRerankEnabled}
              onChange={(event) => setContextRerankEnabled(event.currentTarget.checked)}
              label="Enable context re-ranking"
              size="sm"
              description="Re-rank results by semantic relevance for improved accuracy"
            />
          </div>
        </Stack>

        <Divider />

        <Group justify="flex-end" gap="sm">
          <Button
            variant="subtle"
            color="gray"
            leftSection={<IconRefresh size={16} />}
            onClick={resetToDefaults}
            disabled={!hasChanges || saving}
          >
            Reset
          </Button>
          <Button
            color="blue"
            leftSection={<IconDeviceFloppy size={16} />}
            onClick={saveConfig}
            disabled={!hasChanges}
            loading={saving}
          >
            Save Changes
          </Button>
        </Group>

        {hasChanges && (
          <Alert icon={<IconAlertCircle size={16} />} color="yellow" variant="light">
            <Text size="sm">You have unsaved changes. Click "Save Changes" to apply them.</Text>
          </Alert>
        )}
      </Stack>
    </Paper>
  );
};
