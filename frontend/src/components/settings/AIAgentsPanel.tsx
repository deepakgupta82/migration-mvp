/**
 * AI Agents Panel - Real-time crew configuration display
 * Shows actual data from crew_definitions.yaml via API
 */

import React, { useState, useEffect } from 'react';
import {
  Card,
  Text,
  Group,
  Stack,
  Button,
  Divider,
  Alert,
  Badge,
  Loader,
  Grid,
  ScrollArea,
  ActionIcon,
  Tooltip,
  Progress,
  Box,
  Modal,
  Textarea,
} from '@mantine/core';
import {
  IconRobot,
  IconAlertCircle,
  IconRefresh,
  IconCheck,
  IconX,
  IconExternalLink,
  IconSettings,
  IconTool,
  IconUsers,
  IconClipboardList,
} from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';
import { apiService, CrewConfiguration, CrewStatistics, ValidationResult } from '../../services/api';

export default function AIAgentsPanel() {
  const [configData, setConfigData] = useState<CrewConfiguration | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [wsConnected, setWsConnected] = useState(false);
  const [wsRef, setWsRef] = useState<WebSocket | null>(null);
  const [editing, setEditing] = useState(false);
  const [editContent, setEditContent] = useState('');
  const [saving, setSaving] = useState(false);
  const [initialTimeoutExpired, setInitialTimeoutExpired] = useState(false);
  const initialConfigReceivedRef = React.useRef(false);

  const loadCrewConfiguration = async (showRefreshNotification = false) => {
    try {
      setLoading(!configData); // Only show loading spinner on initial load
      setRefreshing(showRefreshNotification);
      
      const response = await apiService.getCrewDefinitions();
      setConfigData(response);
      setLastUpdated(new Date());
      
      if (showRefreshNotification) {
        notifications.show({
          title: 'Configuration Refreshed',
          message: 'Crew definitions loaded successfully',
          color: 'green',
          icon: <IconCheck size={16} />,
        });
      }
    } catch (error) {
      console.error('Error loading crew configuration:', error);
      notifications.show({
        title: 'Error',
        message: `Failed to load crew configuration: ${error}`,
        color: 'red',
        icon: <IconX size={16} />,
      });
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const handleRefresh = () => {
    loadCrewConfiguration(true);
  };

  const handleReloadFromFile = async () => {
    try {
      setRefreshing(true);
      await apiService.reloadCrewDefinitions();
      await loadCrewConfiguration();
      
      notifications.show({
        title: 'Configuration Reloaded',
        message: 'Crew definitions reloaded from YAML file',
        color: 'blue',
        icon: <IconRefresh size={16} />,
      });
    } catch (error) {
      notifications.show({
        title: 'Error',
        message: `Failed to reload configuration: ${error}`,
        color: 'red',
        icon: <IconX size={16} />,
      });
    } finally {
      setRefreshing(false);
    }
  };

  // Adjust WebSocket construction to dynamic backend host
  const resolveWebSocketUrl = () => {
    if (typeof window === 'undefined') return 'ws://localhost:8000/ws/crew-config?token=service-backend-token';
    const hostname = window.location.hostname;
    const port = window.location.port === '3000' ? '8000' : window.location.port || '8000';
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${protocol}//${hostname}:${port}/ws/crew-config?token=service-backend-token`;
  };

  const connectWebSocket = () => {
    try {
      const ws = new WebSocket(resolveWebSocketUrl());

      ws.onopen = () => {
        console.log('Connected to crew config WebSocket');
        setWsConnected(true);
        setWsRef(ws);
      };

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);

          if (message.type === 'initial_config' || message.type === 'crew_config_update') {
            // New backend format uses keys: config, stats, validation
            if (message.config) {
              const normalized = {
                agents: message.config.agents || [],
                tasks: message.config.tasks || [],
                crews: message.config.crews || [],
                available_tools: message.config.available_tools || [],
                statistics: message.stats,
                validation: message.validation
              };
              setConfigData(normalized);
            } else if (message.data) { // legacy fallback
              setConfigData(message.data);
            }
            setLastUpdated(new Date());
            initialConfigReceivedRef.current = true;

            if (message.type === 'crew_config_update') {
              notifications.show({
                title: 'Configuration Updated',
                message: 'Crew definitions have been updated',
                color: 'blue',
                icon: <IconRefresh size={16} />,
              });
            }
          }
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
        }
      };

      ws.onclose = () => {
        console.log('Disconnected from crew config WebSocket');
        setWsConnected(false);
        setWsRef(null);

        // Attempt to reconnect after 5 seconds
        setTimeout(connectWebSocket, 5000);
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        setWsConnected(false);
      };

      // Send ping every 30 seconds to keep connection alive
      const pingInterval = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send('ping');
        }
      }, 30000);

      return () => {
        clearInterval(pingInterval);
        ws.close();
      };
    } catch (error) {
      console.error('Failed to connect to WebSocket:', error);
      // Fallback to HTTP polling
      setTimeout(() => loadCrewConfiguration(), 1000);
    }
  };

  useEffect(() => {
    // Try WebSocket first, fallback to HTTP if it fails
    const cleanup = connectWebSocket();

    // Fallback HTTP polling if WebSocket fails
    const fallbackInterval = setInterval(() => {
      if (!wsConnected) {
        loadCrewConfiguration();
      }
    }, 30000);

    const timer = setTimeout(() => {
      if (!initialConfigReceivedRef.current) {
        setInitialTimeoutExpired(true);
        loadCrewConfiguration();
      }
    }, 7000);

    return () => {
      if (cleanup) cleanup();
      clearInterval(fallbackInterval);
      clearTimeout(timer);
      if (wsRef) {
        wsRef.close();
      }
    };
  }, []);

  if (loading && !configData) {
    return (
      <Card shadow="sm" p="lg" radius="md" withBorder>
        <Group justify="center" py="xl">
          <Loader size="lg" />
          <Text>Loading crew configuration...</Text>
        </Group>
      </Card>
    );
  }

  if (!configData) {
    return (
      <Card shadow="sm" p="lg" radius="md" withBorder>
        <Alert icon={<IconAlertCircle size={16} />} title="Error" color="red">
          Failed to load crew configuration. Please check if the backend service is running.
        </Alert>
      </Card>
    );
  }

  const statistics = configData.statistics || { agents_count: 0, tasks_count: 0, crews_count: 0, tools_count: 0 };
  const validation = configData.validation || { errors: [], warnings: [] };
  const hasErrors = validation.errors.length > 0;
  const hasWarnings = validation.warnings.length > 0;

  const handleEditOpen = () => {
    if (configData) {
      const exportObj = {
        agents: configData.agents,
        tasks: configData.tasks,
        crews: configData.crews,
        available_tools: configData.available_tools
      };
      setEditContent(JSON.stringify(exportObj, null, 2));
      setEditing(true);
    }
  };
  const handleSave = async () => {
    try {
      setSaving(true);
      let parsed;
      try {
        parsed = JSON.parse(editContent);
      } catch (e:any) {
        notifications.show({ title: 'Invalid JSON', message: e.message, color: 'red', icon: <IconX size={16} />});
        return;
      }
      if (!parsed.agents || !parsed.tasks || !parsed.crews || !parsed.available_tools) {
        notifications.show({ title: 'Missing Keys', message: 'agents, tasks, crews, available_tools required', color: 'red', icon: <IconX size={16} />});
        return;
      }
      await apiService.updateCrewDefinitions(parsed);
      notifications.show({ title: 'Saved', message: 'Crew configuration updated', color: 'green', icon: <IconCheck size={16} />});
      setEditing(false);
      await loadCrewConfiguration();
    } catch (error:any) {
      notifications.show({ title: 'Save Failed', message: String(error), color: 'red', icon: <IconX size={16} />});
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card shadow="sm" p="lg" radius="md" withBorder>
      <Stack gap="lg">
        <Group justify="space-between">
          <div>
            <Text size="lg" fw={600}>
              AI Agent Configuration
            </Text>
            <Text size="sm" c="dimmed">
              Manage AI agents, tasks, and crew workflows for migration assessments
            </Text>
            <Group gap="xs">
              {lastUpdated && (
                <Text size="xs" c="dimmed">
                  Last updated: {lastUpdated.toLocaleTimeString()}
                </Text>
              )}
              <Badge
                size="xs"
                color={wsConnected ? "green" : "gray"}
                variant="dot"
              >
                {wsConnected ? "Live" : "Offline"}
              </Badge>
            </Group>
          </div>
          <Group gap="xs">
            <Tooltip label="Refresh from memory">
              <ActionIcon
                variant="light"
                color="blue"
                onClick={handleRefresh}
                loading={refreshing}
              >
                <IconRefresh size={16} />
              </ActionIcon>
            </Tooltip>
            <Tooltip label="Reload from YAML file">
              <ActionIcon
                variant="light"
                color="green"
                onClick={handleReloadFromFile}
                loading={refreshing}
              >
                <IconSettings size={16} />
              </ActionIcon>
            </Tooltip>
            <Button
              component="a"
              href="/settings/agents"
              leftSection={<IconRobot size={16} />}
              variant="light"
              size="sm"
            >
              Open Agent Editor
            </Button>
            <Button
              variant="light"
              size="sm"
              color="violet"
              leftSection={<IconSettings size={16} />}
              onClick={handleEditOpen}
              disabled={!configData}
            >
              Edit JSON
            </Button>
          </Group>
        </Group>

        {initialTimeoutExpired && !wsConnected && (
          <Alert icon={<IconAlertCircle size={16} />} color="yellow" mt="sm">
            Live connection not established yet; showing latest cached configuration.
          </Alert>
        )}

        <Divider />

        {/* Configuration Status */}
        {(hasErrors || hasWarnings) && (
          <Alert 
            icon={<IconAlertCircle size={16} />} 
            color={hasErrors ? "red" : "yellow"}
            title={hasErrors ? "Configuration Errors" : "Configuration Warnings"}
          >
            <Stack gap="xs">
              {validation.errors.map((error, index) => (
                <Text key={index} size="sm">❌ {error}</Text>
              ))}
              {validation.warnings.map((warning, index) => (
                <Text key={index} size="sm">⚠️ {warning}</Text>
              ))}
            </Stack>
          </Alert>
        )}

        {/* Statistics Grid */}
        <Grid>
          <Grid.Col span={3}>
            <Card withBorder p="md" radius="md">
              <Group justify="space-between">
                <div>
                  <Text size="xs" tt="uppercase" fw={700} c="dimmed">
                    Active Agents
                  </Text>
                  <Text size="xl" fw={700}>
                    {statistics.agents_count}
                  </Text>
                </div>
                <IconUsers size={24} color="var(--mantine-color-blue-6)" />
              </Group>
            </Card>
          </Grid.Col>
          
          <Grid.Col span={3}>
            <Card withBorder p="md" radius="md">
              <Group justify="space-between">
                <div>
                  <Text size="xs" tt="uppercase" fw={700} c="dimmed">
                    Configured Tasks
                  </Text>
                  <Text size="xl" fw={700}>
                    {statistics.tasks_count}
                  </Text>
                </div>
                <IconClipboardList size={24} color="var(--mantine-color-green-6)" />
              </Group>
            </Card>
          </Grid.Col>
          
          <Grid.Col span={3}>
            <Card withBorder p="md" radius="md">
              <Group justify="space-between">
                <div>
                  <Text size="xs" tt="uppercase" fw={700} c="dimmed">
                    Assessment Crews
                  </Text>
                  <Text size="xl" fw={700}>
                    {statistics.crews_count}
                  </Text>
                </div>
                <IconRobot size={24} color="var(--mantine-color-purple-6)" />
              </Group>
            </Card>
          </Grid.Col>
          
          <Grid.Col span={3}>
            <Card withBorder p="md" radius="md">
              <Group justify="space-between">
                <div>
                  <Text size="xs" tt="uppercase" fw={700} c="dimmed">
                    Available Tools
                  </Text>
                  <Text size="xl" fw={700}>
                    {statistics.tools_count}
                  </Text>
                </div>
                <IconTool size={24} color="var(--mantine-color-orange-6)" />
              </Group>
            </Card>
          </Grid.Col>
        </Grid>

        {/* Configuration Health */}
        <Box>
          <Text size="sm" fw={500} mb="xs">Configuration Health</Text>
          <Progress
            value={hasErrors ? 25 : hasWarnings ? 75 : 100}
            color={hasErrors ? "red" : hasWarnings ? "yellow" : "green"}
            size="lg"
            radius="md"
          />
          <Text size="xs" c="dimmed" mt="xs">
            {hasErrors 
              ? "Configuration has errors that need attention"
              : hasWarnings 
                ? "Configuration has warnings but is functional"
                : "Configuration is healthy and fully functional"
            }
          </Text>
        </Box>

        {/* Quick Actions */}
        <Alert icon={<IconRobot size={16} />} color="blue">
          <Text size="sm">
            <strong>🤖 Dynamic AI Agent Management</strong>
            <br />
            Configure your AI assessment crew:
            <br />
            • Edit agent roles, goals, and backstories
            <br />
            • Assign tools and capabilities to agents
            <br />
            • Modify task descriptions and workflows
            <br />
            • Customize crew collaboration patterns
            <br />
            • Real-time configuration updates
          </Text>
        </Alert>

        <Modal opened={editing} onClose={() => setEditing(false)} title="Edit Crew Configuration (JSON)" size="80%">
          <Stack gap="sm">
            <Textarea autosize minRows={20} value={editContent} onChange={(e) => setEditContent(e.currentTarget.value)} />
            <Group justify="flex-end">
              <Button variant="default" onClick={() => setEditing(false)}>Cancel</Button>
              <Button loading={saving} onClick={handleSave} leftSection={<IconCheck size={16} />}>Save</Button>
            </Group>
          </Stack>
        </Modal>
      </Stack>
    </Card>
  );
}
