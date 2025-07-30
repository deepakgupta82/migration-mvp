import React, { useState, useEffect } from 'react';
import {
  Modal,
  Select,
  Button,
  Text,
  Group,
  Stack,
  Badge,
  Alert,
  LoadingOverlay
} from '@mantine/core';
import { IconAlertCircle, IconCheck, IconX } from '@tabler/icons-react';
import { apiService } from '../services/api';

interface LLMConfig {
  id: string;
  name: string;
  provider: string;
  model: string;
  status: 'configured' | 'needs_key';
}

interface LLMConfigSelectorProps {
  opened: boolean;
  onClose: () => void;
  onSelect: (configId: string) => void;
  title?: string;
  description?: string;
}

export const LLMConfigSelector: React.FC<LLMConfigSelectorProps> = ({
  opened,
  onClose,
  onSelect,
  title = "Select LLM Configuration",
  description = "Choose which LLM configuration to use for processing:"
}) => {
  const [configs, setConfigs] = useState<LLMConfig[]>([]);
  const [selectedConfig, setSelectedConfig] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (opened) {
      fetchLLMConfigs();
    }
  }, [opened]);

  const fetchLLMConfigs = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch('http://localhost:8000/llm-configurations');
      if (response.ok) {
        const data = await response.json();
        setConfigs(data);

        // Auto-select first configured option
        const configuredOption = data.find((config: LLMConfig) => config.status === 'configured');
        if (configuredOption) {
          setSelectedConfig(configuredOption.id);
        }
      } else {
        setError('Failed to load LLM configurations');
      }
    } catch (err) {
      setError('Error loading LLM configurations');
      console.error('Error fetching LLM configs:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSelect = () => {
    if (selectedConfig) {
      onSelect(selectedConfig);
      onClose();
    }
  };

  const getStatusBadge = (status: string) => {
    if (status === 'configured') {
      return <Badge color="green" size="sm" leftSection={<IconCheck size={12} />}>Ready</Badge>;
    } else {
      return <Badge color="orange" size="sm" leftSection={<IconX size={12} />}>Needs API Key</Badge>;
    }
  };

  const configOptions = configs.map(config => ({
    value: config.id,
    label: `${config.name} (${config.provider} - ${config.model})`
  }));

  const selectedConfigData = configs.find(c => c.id === selectedConfig);
  const canProceed = selectedConfig && selectedConfigData?.status === 'configured';

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={title}
      size="md"
      centered
    >
      <LoadingOverlay visible={loading} />

      <Stack gap="md">
        <Text size="sm" c="dimmed">
          {description}
        </Text>

        {error && (
          <Alert icon={<IconAlertCircle size={16} />} color="red">
            {error}
          </Alert>
        )}

        {configs.length === 0 && !loading && !error && (
          <Alert icon={<IconAlertCircle size={16} />} color="yellow">
            No LLM configurations found. Please add an LLM configuration in Settings first.
          </Alert>
        )}

        {configs.length > 0 && (
          <>
            <Select
              label="LLM Configuration"
              placeholder="Select an LLM configuration"
              data={configOptions}
              value={selectedConfig}
              onChange={(value) => setSelectedConfig(value || '')}
              searchable
              clearable={false}
            />

            {selectedConfigData && (
              <Stack gap="xs" mt="sm">
                <Text size="sm" fw={500}>Selected Configuration:</Text>
                <Group gap="xs">
                  <Text size="sm" c="dimmed">Name:</Text>
                  <Text size="sm">{selectedConfigData.name}</Text>
                </Group>
                <Group gap="xs">
                  <Text size="sm" c="dimmed">Provider:</Text>
                  <Text size="sm">{selectedConfigData.provider}</Text>
                </Group>
                <Group gap="xs">
                  <Text size="sm" c="dimmed">Model:</Text>
                  <Text size="sm">{selectedConfigData.model}</Text>
                </Group>
                <Group gap="xs">
                  <Text size="sm" c="dimmed">Status:</Text>
                  {getStatusBadge(selectedConfigData.status)}
                </Group>
              </Stack>
            )}
          </>
        )}

        {selectedConfigData && selectedConfigData.status === 'needs_key' && (
          <Alert icon={<IconAlertCircle size={16} />} color="orange">
            This configuration needs an API key. Please update it in Settings &gt; LLM Configuration.
          </Alert>
        )}

        <Group justify="flex-end" gap="sm">
          <Button variant="light" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={handleSelect}
            disabled={!canProceed}
          >
            Start Processing
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
};
