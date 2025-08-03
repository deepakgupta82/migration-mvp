import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Paper,
  Text,
  Stack,
  Group,
  SegmentedControl,
  Button,
  Select,
  TextInput,
  Badge,
  Accordion,
  Switch,
  Divider,
  Box,
  ScrollArea,
  Loader,
  Alert,
  ActionIcon,
  Tooltip,
  Card,
  Grid,
  Progress,
  Code,
  Collapse,
  Timeline,
  Avatar,
  Menu,
  UnstyledButton,
} from '@mantine/core';
import {
  IconRobot,
  IconUsers,
  IconTool,
  IconSearch,
  IconFilter,
  IconDownload,
  IconCopy,
  IconChevronDown,
  IconChevronRight,
  IconClock,
  IconCoin,
  IconAlertCircle,
  IconCheck,
  IconX,
  IconRefresh,
  IconSettings,
  IconEye,
  IconEyeOff,
  IconBrain,
  IconMessageCircle,
  IconDatabase,
  IconWorld,
  IconFile,
  IconActivity,
} from '@tabler/icons-react';
// import { FixedSizeList as List } from 'react-window'; // Will implement virtual scrolling later
import { notifications } from '@mantine/notifications';

// Types
interface CrewInteraction {
  id: string;
  project_id: string;
  task_id: string;
  conversation_id: string;
  timestamp: string;
  type: 'crew_start' | 'crew_complete' | 'agent_start' | 'agent_complete' |
        'tool_call' | 'tool_response' | 'function_call' | 'reasoning_step' |
        'agent_communication' | 'error' | 'retry';
  parent_id?: string;
  depth: number;
  sequence: number;

  // Crew/Agent/Tool Data
  crew_name?: string;
  crew_description?: string;
  crew_members?: string[];
  crew_goal?: string;

  agent_name?: string;
  agent_role?: string;
  agent_goal?: string;
  agent_backstory?: string;
  agent_id?: string;

  tool_name?: string;
  tool_description?: string;
  function_name?: string;

  // Content
  request_data?: any;
  response_data?: any;
  reasoning_step?: {
    thought: string;
    action: string;
    action_input?: any;
    observation?: string;
    final_answer?: string;
    scratchpad?: string;
  };

  // Communication
  request_text?: string;
  response_text?: string;
  message_type?: string;

  // Performance
  token_usage?: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
    estimated_cost: number;
    model: string;
    provider: string;
  };
  performance_metrics?: any;

  // Status
  status: 'pending' | 'running' | 'completed' | 'failed' | 'retrying' | 'cancelled';
  start_time?: string;
  end_time?: string;
  duration_ms?: number;
  error_message?: string;
  retry_count: number;

  // Metadata
  metadata?: any;
}

interface FilterOptions {
  mode: 'historic' | 'realtime';
  agent_types: string[];
  tools: string[];
  time_range?: { start: string; end: string };
  status: string[];
  search_query?: string;
  conversation_id?: string;
}

interface UserDisplayPreferences {
  show_token_usage: boolean;
  show_reasoning_steps: boolean;
  show_function_calls: boolean;
  show_timestamps: boolean;
  show_duration: boolean;
  show_costs: boolean;
  show_metadata: boolean;
  show_error_details: boolean;
  compact_mode: boolean;
  group_by_agent: boolean;
  group_by_tool: boolean;
}

interface InteractionStats {
  total_interactions: number;
  type_counts: Record<string, number>;
  status_counts: Record<string, number>;
  unique_agents: number;
  unique_tools: number;
  total_tokens: number;
  total_cost: number;
}

interface CrewInteractionViewerProps {
  projectId: string;
}

const CrewInteractionViewer: React.FC<CrewInteractionViewerProps> = ({ projectId }) => {
  // State management
  const [mode, setMode] = useState<'historic' | 'realtime'>('realtime');
  const [interactions, setInteractions] = useState<CrewInteraction[]>([]);
  const [filteredInteractions, setFilteredInteractions] = useState<CrewInteraction[]>([]);
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState<InteractionStats | null>(null);
  const [websocket, setWebsocket] = useState<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);

  // Filters and preferences
  const [filters, setFilters] = useState<FilterOptions>({
    mode: 'realtime',
    agent_types: [],
    tools: [],
    status: [],
    search_query: '',
  });

  const [preferences, setPreferences] = useState<UserDisplayPreferences>({
    show_token_usage: true,
    show_reasoning_steps: true,
    show_function_calls: true,
    show_timestamps: true,
    show_duration: true,
    show_costs: true,
    show_metadata: false,
    show_error_details: true,
    compact_mode: false,
    group_by_agent: false,
    group_by_tool: false,
  });

  // UI state
  const [expandedItems, setExpandedItems] = useState<Set<string>>(new Set());
  const [autoScroll, setAutoScroll] = useState(true);
  const scrollAreaRef = useRef<HTMLDivElement>(null);

  // Available filter options (populated from data)
  const [availableAgents, setAvailableAgents] = useState<string[]>([]);
  const [availableTools, setAvailableTools] = useState<string[]>([]);

  // =====================================================================================
  // DATA FETCHING AND WEBSOCKET MANAGEMENT
  // =====================================================================================

  const fetchHistoricInteractions = useCallback(async () => {
    if (mode !== 'historic') return;

    setLoading(true);
    try {
      const params = new URLSearchParams({
        limit: '1000',
        offset: '0',
      });

      if (filters.search_query) params.append('search', filters.search_query);
      if (filters.agent_types.length > 0) params.append('agent_name', filters.agent_types[0]);
      if (filters.tools.length > 0) params.append('tool_name', filters.tools[0]);
      if (filters.status.length > 0) params.append('status', filters.status[0]);

      const response = await fetch(`http://localhost:8000/api/projects/${projectId}/crew-interactions?${params}`);
      if (response.ok) {
        const data = await response.json();
        setInteractions(data.interactions || []);

        // Extract unique agents and tools for filters
        const agents = new Set<string>();
        const tools = new Set<string>();

        data.interactions?.forEach((interaction: CrewInteraction) => {
          if (interaction.agent_name) agents.add(interaction.agent_name);
          if (interaction.tool_name) tools.add(interaction.tool_name);
        });

        setAvailableAgents(Array.from(agents));
        setAvailableTools(Array.from(tools));
      }
    } catch (error) {
      console.error('Failed to fetch historic interactions:', error);
      notifications.show({
        title: 'Error',
        message: 'Failed to load historic interactions',
        color: 'red',
      });
    } finally {
      setLoading(false);
    }
  }, [projectId, mode, filters]);

  const fetchStats = useCallback(async () => {
    try {
      const response = await fetch(`http://localhost:8000/api/projects/${projectId}/crew-interactions/stats`);
      if (response.ok) {
        const data = await response.json();
        setStats(data);
      }
    } catch (error) {
      console.error('Failed to fetch stats:', error);
    }
  }, [projectId]);

  const connectWebSocket = useCallback(() => {
    if (mode !== 'realtime' || websocket) return;

    const ws = new WebSocket(`ws://localhost:8000/ws/crew-interactions/${projectId}?mode=realtime`);

    ws.onopen = () => {
      setIsConnected(true);
      setWebsocket(ws);
      notifications.show({
        title: 'Connected',
        message: 'Real-time crew interaction monitoring started',
        color: 'green',
      });
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === 'connection_established') {
          console.log('WebSocket connection established');
        } else if (data.type === 'task_started') {
          // Register for this specific task
          ws.send(JSON.stringify({
            type: 'register_for_task',
            task_id: data.task_id
          }));
        } else {
          // This is an interaction update
          setInteractions(prev => {
            const newInteractions = [data, ...prev];

            // Auto-scroll to top for new interactions
            if (autoScroll && scrollAreaRef.current) {
              scrollAreaRef.current.scrollTop = 0;
            }

            return newInteractions;
          });

          // Update available filters
          if (data.agent_name && !availableAgents.includes(data.agent_name)) {
            setAvailableAgents(prev => [...prev, data.agent_name]);
          }
          if (data.tool_name && !availableTools.includes(data.tool_name)) {
            setAvailableTools(prev => [...prev, data.tool_name]);
          }
        }
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error);
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
      setWebsocket(null);
      console.log('WebSocket connection closed');
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      setIsConnected(false);
      notifications.show({
        title: 'Connection Error',
        message: 'Failed to connect to real-time monitoring. Check if backend is running.',
        color: 'red',
        autoClose: false,
      });
    };
  }, [projectId, mode, websocket, autoScroll]);

  const disconnectWebSocket = useCallback(() => {
    if (websocket) {
      websocket.close();
      setWebsocket(null);
      setIsConnected(false);
    }
  }, [websocket]);

  // =====================================================================================
  // EFFECTS
  // =====================================================================================

  useEffect(() => {
    if (mode === 'historic') {
      disconnectWebSocket();
      fetchHistoricInteractions();
    } else {
      connectWebSocket();
    }

    fetchStats();

    return () => {
      disconnectWebSocket();
    };
  }, [mode, projectId]);

  useEffect(() => {
    if (mode === 'historic') {
      fetchHistoricInteractions();
    }
  }, [filters, fetchHistoricInteractions]);

  // Filter interactions based on current filters
  useEffect(() => {
    let filtered = [...interactions];

    if (filters.agent_types.length > 0) {
      filtered = filtered.filter(i =>
        filters.agent_types.includes(i.agent_name || '')
      );
    }

    if (filters.tools.length > 0) {
      filtered = filtered.filter(i =>
        filters.tools.includes(i.tool_name || '')
      );
    }

    if (filters.status.length > 0) {
      filtered = filtered.filter(i =>
        filters.status.includes(i.status)
      );
    }

    if (filters.search_query) {
      const query = filters.search_query.toLowerCase();
      filtered = filtered.filter(i =>
        i.agent_name?.toLowerCase().includes(query) ||
        i.tool_name?.toLowerCase().includes(query) ||
        i.function_name?.toLowerCase().includes(query) ||
        i.request_text?.toLowerCase().includes(query) ||
        i.response_text?.toLowerCase().includes(query)
      );
    }

    setFilteredInteractions(filtered);
  }, [interactions, filters]);

  // =====================================================================================
  // UTILITY FUNCTIONS
  // =====================================================================================

  const getInteractionIcon = (interaction: CrewInteraction) => {
    switch (interaction.type) {
      case 'crew_start':
      case 'crew_complete':
        return <IconUsers size={16} color="#228be6" />;
      case 'agent_start':
      case 'agent_complete':
        return <IconRobot size={16} color="#40c057" />;
      case 'reasoning_step':
        return <IconBrain size={16} color="#fd7e14" />;
      case 'tool_call':
      case 'tool_response':
        return <IconTool size={16} color="#7c2d12" />;
      case 'function_call':
        return <IconDatabase size={16} color="#6741d9" />;
      case 'error':
        return <IconAlertCircle size={16} color="#e03131" />;
      case 'retry':
        return <IconRefresh size={16} color="#f59f00" />;
      default:
        return <IconActivity size={16} color="#868e96" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'green';
      case 'failed': return 'red';
      case 'running': return 'blue';
      case 'pending': return 'yellow';
      case 'retrying': return 'orange';
      case 'cancelled': return 'gray';
      default: return 'gray';
    }
  };

  const formatDuration = (ms?: number) => {
    if (!ms) return 'N/A';
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  };

  const formatTimestamp = (timestamp: string) => {
    return new Date(timestamp).toLocaleTimeString();
  };

  const toggleExpanded = (id: string) => {
    setExpandedItems(prev => {
      const newSet = new Set(prev);
      if (newSet.has(id)) {
        newSet.delete(id);
      } else {
        newSet.add(id);
      }
      return newSet;
    });
  };

  // =====================================================================================
  // RENDER FUNCTIONS
  // =====================================================================================

  const renderDisplayPreferences = () => (
    <Accordion>
      <Accordion.Item value="display-preferences">
        <Accordion.Control icon={<IconSettings size={16} />}>
          Display Preferences
        </Accordion.Control>
        <Accordion.Panel>
          <Stack gap="xs">
            <Group>
              <Switch
                label="Token Usage"
                checked={preferences.show_token_usage}
                onChange={(event) => setPreferences(prev => ({
                  ...prev,
                  show_token_usage: event.currentTarget.checked
                }))}
              />
              <Switch
                label="Reasoning Steps"
                checked={preferences.show_reasoning_steps}
                onChange={(event) => setPreferences(prev => ({
                  ...prev,
                  show_reasoning_steps: event.currentTarget.checked
                }))}
              />
              <Switch
                label="Function Calls"
                checked={preferences.show_function_calls}
                onChange={(event) => setPreferences(prev => ({
                  ...prev,
                  show_function_calls: event.currentTarget.checked
                }))}
              />
            </Group>
            <Group>
              <Switch
                label="Timestamps"
                checked={preferences.show_timestamps}
                onChange={(event) => setPreferences(prev => ({
                  ...prev,
                  show_timestamps: event.currentTarget.checked
                }))}
              />
              <Switch
                label="Duration"
                checked={preferences.show_duration}
                onChange={(event) => setPreferences(prev => ({
                  ...prev,
                  show_duration: event.currentTarget.checked
                }))}
              />
              <Switch
                label="Costs"
                checked={preferences.show_costs}
                onChange={(event) => setPreferences(prev => ({
                  ...prev,
                  show_costs: event.currentTarget.checked
                }))}
              />
            </Group>
            <Group>
              <Switch
                label="Metadata"
                checked={preferences.show_metadata}
                onChange={(event) => setPreferences(prev => ({
                  ...prev,
                  show_metadata: event.currentTarget.checked
                }))}
              />
              <Switch
                label="Error Details"
                checked={preferences.show_error_details}
                onChange={(event) => setPreferences(prev => ({
                  ...prev,
                  show_error_details: event.currentTarget.checked
                }))}
              />
              <Switch
                label="Compact Mode"
                checked={preferences.compact_mode}
                onChange={(event) => setPreferences(prev => ({
                  ...prev,
                  compact_mode: event.currentTarget.checked
                }))}
              />
            </Group>
          </Stack>
        </Accordion.Panel>
      </Accordion.Item>
    </Accordion>
  );

  const renderFilters = () => (
    <Group gap="md" align="end">
      <Select
        label="Agent Type"
        placeholder="All agents"
        data={availableAgents.map(agent => ({ value: agent, label: agent }))}
        value={filters.agent_types[0] || null}
        onChange={(value) => setFilters(prev => ({
          ...prev,
          agent_types: value ? [value] : []
        }))}
        clearable
        style={{ minWidth: 150 }}
      />

      <Select
        label="Tool"
        placeholder="All tools"
        data={availableTools.map(tool => ({ value: tool, label: tool }))}
        value={filters.tools[0] || null}
        onChange={(value) => setFilters(prev => ({
          ...prev,
          tools: value ? [value] : []
        }))}
        clearable
        style={{ minWidth: 150 }}
      />

      <Select
        label="Status"
        placeholder="All statuses"
        data={[
          { value: 'completed', label: 'Completed' },
          { value: 'failed', label: 'Failed' },
          { value: 'running', label: 'Running' },
          { value: 'pending', label: 'Pending' },
          { value: 'retrying', label: 'Retrying' },
        ]}
        value={filters.status[0] || null}
        onChange={(value) => setFilters(prev => ({
          ...prev,
          status: value ? [value] : []
        }))}
        clearable
        style={{ minWidth: 120 }}
      />

      <TextInput
        label="Search"
        placeholder="Search interactions..."
        leftSection={<IconSearch size={16} />}
        value={filters.search_query || ''}
        onChange={(event) => setFilters(prev => ({
          ...prev,
          search_query: event.currentTarget.value
        }))}
        style={{ minWidth: 200 }}
      />

      <Button
        variant="light"
        onClick={() => setFilters({
          mode: filters.mode,
          agent_types: [],
          tools: [],
          status: [],
          search_query: '',
        })}
      >
        Clear Filters
      </Button>
    </Group>
  );

  const renderStats = () => {
    if (!stats) return null;

    return (
      <Grid>
        <Grid.Col span={2}>
          <Paper p="sm" withBorder>
            <Text size="xs" c="dimmed">Total Interactions</Text>
            <Text size="lg" fw={700}>{stats.total_interactions.toLocaleString()}</Text>
          </Paper>
        </Grid.Col>
        <Grid.Col span={2}>
          <Paper p="sm" withBorder>
            <Text size="xs" c="dimmed">Agents</Text>
            <Text size="lg" fw={700}>{stats.unique_agents}</Text>
          </Paper>
        </Grid.Col>
        <Grid.Col span={2}>
          <Paper p="sm" withBorder>
            <Text size="xs" c="dimmed">Tools</Text>
            <Text size="lg" fw={700}>{stats.unique_tools}</Text>
          </Paper>
        </Grid.Col>
        <Grid.Col span={2}>
          <Paper p="sm" withBorder>
            <Text size="xs" c="dimmed">Total Tokens</Text>
            <Text size="lg" fw={700}>{stats.total_tokens.toLocaleString()}</Text>
          </Paper>
        </Grid.Col>
        <Grid.Col span={2}>
          <Paper p="sm" withBorder>
            <Text size="xs" c="dimmed">Total Cost</Text>
            <Text size="lg" fw={700}>${stats.total_cost.toFixed(4)}</Text>
          </Paper>
        </Grid.Col>
        <Grid.Col span={2}>
          <Paper p="sm" withBorder>
            <Text size="xs" c="dimmed">Success Rate</Text>
            <Text size="lg" fw={700}>
              {stats.status_counts.completed && stats.total_interactions > 0
                ? `${Math.round((stats.status_counts.completed / stats.total_interactions) * 100)}%`
                : 'N/A'
              }
            </Text>
          </Paper>
        </Grid.Col>
      </Grid>
    );
  };

  // This will be continued in the next part due to length...
  return (
    <Stack gap="md">
      {/* Header with Mode Toggle */}
      <Group justify="space-between">
        <Group>
          <SegmentedControl
            value={mode}
            onChange={(value) => setMode(value as 'historic' | 'realtime')}
            data={[
              { label: '📚 Historic', value: 'historic' },
              { label: '🔴 Real-time', value: 'realtime' }
            ]}
          />
          {mode === 'realtime' && (
            <Group gap="xs">
              <Badge color={isConnected ? 'green' : 'red'} variant="dot">
                {isConnected ? 'Connected' : 'Disconnected'}
              </Badge>
              <Switch
                label="Auto-scroll"
                checked={autoScroll}
                onChange={(event) => setAutoScroll(event.currentTarget.checked)}
                size="sm"
              />
            </Group>
          )}
        </Group>

        {renderDisplayPreferences()}
      </Group>

      {/* Filters */}
      {renderFilters()}

      {/* Stats */}
      {renderStats()}

      {/* Main Content */}
      {loading ? (
        <Group justify="center" p="xl">
          <Loader size="lg" />
          <Text>Loading interactions...</Text>
        </Group>
      ) : filteredInteractions.length === 0 ? (
        <Alert icon={<IconAlertCircle size={16} />} color="blue">
          {mode === 'realtime'
            ? 'No real-time interactions yet. Start a document generation or assessment to see live activity.'
            : 'No historic interactions found. Try adjusting your filters or generate some documents first.'
          }
        </Alert>
      ) : (
        <Paper p="md" withBorder style={{ height: 600 }}>
          <Text size="sm" c="dimmed" mb="md">
            Showing {filteredInteractions.length} interactions
          </Text>

          {/* Scrolled List */}
          <ScrollArea h={500} ref={scrollAreaRef}>
            <Stack gap="xs">
              {filteredInteractions.slice(0, 50).map((interaction) => (
                <Paper key={interaction.id} p="sm" withBorder>
                  <Group justify="space-between">
                    <Group gap="sm">
                      {getInteractionIcon(interaction)}
                      <div>
                        <Text size="sm" fw={500}>
                          {interaction.type.replace('_', ' ')}
                          {interaction.agent_name && ` - ${interaction.agent_name}`}
                          {interaction.tool_name && ` - ${interaction.tool_name}`}
                        </Text>
                        {preferences.show_timestamps && (
                          <Text size="xs" c="dimmed">
                            {formatTimestamp(interaction.timestamp)}
                          </Text>
                        )}
                      </div>
                    </Group>
                    <Group gap="xs">
                      <Badge size="xs" color={getStatusColor(interaction.status)}>
                        {interaction.status}
                      </Badge>
                      {preferences.show_duration && interaction.duration_ms && (
                        <Text size="xs" c="dimmed">
                          {formatDuration(interaction.duration_ms)}
                        </Text>
                      )}
                    </Group>
                  </Group>
                </Paper>
              ))}
            </Stack>
          </ScrollArea>
        </Paper>
      )}
    </Stack>
  );
};

export default CrewInteractionViewer;
