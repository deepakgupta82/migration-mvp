/**
 * Logs View - Comprehensive logging system for admins
 * Shows platform logs, service logs, and project-level logs
 */

import React, { useState, useEffect, useRef } from 'react';
import {
  Container,
  Grid,
  Card,
  Text,
  Group,
  Stack,
  Select,
  Button,
  Badge,
  Table,
  ScrollArea,
  ActionIcon,
  TextInput,
  Tabs,
  Alert,
  Code,
  Box,
  Title,
  Divider,
  Switch,
  NumberInput,
  JsonInput,
  Collapse,
  MultiSelect,
} from '@mantine/core';
import {
  IconRefresh,
  IconDownload,
  IconSearch,
  IconFilter,
  IconAlertCircle,
  IconInfoCircle,
  IconExclamationMark,
  IconBug,
  IconServer,
  IconDatabase,
  IconCloud,
  IconSettings,
} from '@tabler/icons-react';

// Types
interface LogEntry {
  id: string;
  timestamp: Date;
  level: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL';
  service: string;
  message: string;
  projectId?: string;
  projectName?: string;
  metadata?: Record<string, any>;
  stackTrace?: string;
}

interface AgentInteraction {
  id: string;
  timestamp: Date;
  sourceAgent: string;
  targetAgent: string;
  interactionType: 'REQUEST' | 'RESPONSE' | 'BROADCAST' | 'DELEGATION';
  payload: any;
  status: 'SUCCESS' | 'FAILED' | 'PENDING';
  duration?: number;
  projectId?: string;
  projectName?: string;
  metadata?: Record<string, any>;
}

interface LogFilter {
  level: string;
  service: string;
  projectId: string;
  timeRange: string;
  searchTerm: string;
  correlationId?: string;
  servicesMulti?: string[];
}

// Agent Interaction Row Component
const AgentInteractionRow: React.FC<{ interaction: AgentInteraction }> = ({ interaction }) => {
  const [expanded, setExpanded] = useState(false);

  const getStatusColor = (status: AgentInteraction['status']) => {
    switch (status) {
      case 'SUCCESS':
        return 'green';
      case 'FAILED':
        return 'red';
      case 'PENDING':
        return 'yellow';
      default:
        return 'gray';
    }
  };

  const getTypeColor = (type: AgentInteraction['interactionType']) => {
    switch (type) {
      case 'REQUEST':
        return 'blue';
      case 'RESPONSE':
        return 'cyan';
      case 'BROADCAST':
        return 'purple';
      case 'DELEGATION':
        return 'orange';
      default:
        return 'gray';
    }
  };

  return (
    <>
      <Table.Tr style={{ cursor: 'pointer' }} onClick={() => setExpanded(!expanded)}>
        <Table.Td>
          <Text size="xs" ff="monospace" c="dimmed">
            {interaction.timestamp.toLocaleString()}
          </Text>
        </Table.Td>
        <Table.Td>
          <Badge size="sm" variant="light" color="blue">
            {interaction.sourceAgent}
          </Badge>
        </Table.Td>
        <Table.Td>
          <Badge size="sm" variant="light" color="green">
            {interaction.targetAgent}
          </Badge>
        </Table.Td>
        <Table.Td>
          <Badge size="sm" color={getTypeColor(interaction.interactionType)} variant="light">
            {interaction.interactionType}
          </Badge>
        </Table.Td>
        <Table.Td>
          <Badge size="sm" color={getStatusColor(interaction.status)} variant="light">
            {interaction.status}
          </Badge>
        </Table.Td>
        <Table.Td>
          <Text size="sm" c="dimmed">
            {interaction.duration ? `${interaction.duration}ms` : '-'}
          </Text>
        </Table.Td>
        <Table.Td>
          <Text size="sm" style={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {interaction.payload.type || 'Unknown'}
          </Text>
        </Table.Td>
        <Table.Td>
          {interaction.projectName ? (
            <Badge size="sm" variant="light" color="gray">
              {interaction.projectName}
            </Badge>
          ) : (
            <Text size="xs" c="dimmed">-</Text>
          )}
        </Table.Td>
      </Table.Tr>
      {expanded && (
        <Table.Tr>
          <Table.Td colSpan={8}>
            <Collapse in={expanded}>
              <Box p="md" style={{ backgroundColor: '#f8f9fa', borderRadius: '8px' }}>
                <Grid>
                  <Grid.Col span={6}>
                    <Text size="sm" fw={600} mb="xs">Payload Details:</Text>
                    <Code block style={{ fontSize: '11px', maxHeight: '200px', overflow: 'auto' }}>
                      {JSON.stringify(interaction.payload, null, 2)}
                    </Code>
                  </Grid.Col>
                  <Grid.Col span={6}>
                    <Text size="sm" fw={600} mb="xs">Metadata:</Text>
                    <Stack gap="xs">
                      <Group gap="xs">
                        <Text size="xs" c="dimmed">Request ID:</Text>
                        <Text size="xs" ff="monospace">{interaction.metadata?.requestId}</Text>
                      </Group>
                      <Group gap="xs">
                        <Text size="xs" c="dimmed">Correlation ID:</Text>
                        <Text size="xs" ff="monospace">{interaction.metadata?.correlationId}</Text>
                      </Group>
                      <Group gap="xs">
                        <Text size="xs" c="dimmed">Retry Count:</Text>
                        <Text size="xs">{interaction.metadata?.retryCount || 0}</Text>
                      </Group>
                      {interaction.duration && (
                        <Group gap="xs">
                          <Text size="xs" c="dimmed">Duration:</Text>
                          <Text size="xs">{interaction.duration}ms</Text>
                        </Group>
                      )}
                    </Stack>
                  </Grid.Col>
                </Grid>
              </Box>
            </Collapse>
          </Table.Td>
        </Table.Tr>
      )}
    </>
  );
};

export const LogsView: React.FC = () => {
  // State management
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [filteredLogs, setFilteredLogs] = useState<LogEntry[]>([]);
  const [agentInteractions, setAgentInteractions] = useState<AgentInteraction[]>([]);
  const [filteredInteractions, setFilteredInteractions] = useState<AgentInteraction[]>([]);
  const [loading, setLoading] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [refreshInterval, setRefreshInterval] = useState(5);
  const [activeTab, setActiveTab] = useState('platform');
  const [liveStream, setLiveStream] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const [projects, setProjects] = useState<{ id: string; name: string }[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string>('all');
  const [availableServices, setAvailableServices] = useState<string[]>([]);

  // Filter state
  const [filters, setFilters] = useState<LogFilter>({
    level: 'all',
    service: 'all',
    projectId: 'all',
    timeRange: '1h',
  searchTerm: '',
  correlationId: '',
  servicesMulti: [],
  });

  // Mock data generation
  const generateMockLogs = (): LogEntry[] => {
    const services = ['backend', 'project-service', 'reporting-service', 'megaparse-service', 'weaviate', 'neo4j'];
    const levels: LogEntry['level'][] = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'];
    const messages = [
      'Service started successfully',
      'Database connection established',
      'Processing file upload request',
      'Assessment workflow initiated',
      'LLM API call completed',
      'Report generation started',
      'Cache miss for key: project_data',
      'Authentication token validated',
      'Configuration loaded from environment',
      'Health check endpoint called',
      'WebSocket connection established',
      'Document parsing completed',
      'Graph data updated successfully',
      'RAG service initialized',
      'Memory usage: 85% of allocated',
      'Disk space warning: 90% full',
      'Network timeout on external API',
      'Database query took 2.5 seconds',
      'Failed to connect to external service',
      'Critical error in assessment pipeline',
    ];

    const mockLogs: LogEntry[] = [];
    const now = new Date();

    for (let i = 0; i < 200; i++) {
      const timestamp = new Date(now.getTime() - Math.random() * 24 * 60 * 60 * 1000); // Last 24 hours
      const service = services[Math.floor(Math.random() * services.length)];
      const level = levels[Math.floor(Math.random() * levels.length)];
      const message = messages[Math.floor(Math.random() * messages.length)];

      mockLogs.push({
        id: `log_${i}`,
        timestamp,
        level,
        service,
        message,
        projectId: Math.random() > 0.7 ? `project_${Math.floor(Math.random() * 5) + 1}` : undefined,
        projectName: Math.random() > 0.7 ? `Project ${Math.floor(Math.random() * 5) + 1}` : undefined,
        metadata: {
          userId: `user_${Math.floor(Math.random() * 10) + 1}`,
          requestId: `req_${Math.random().toString(36).substr(2, 9)}`,
          duration: Math.floor(Math.random() * 5000),
        },
        stackTrace: level === 'ERROR' || level === 'CRITICAL' ?
          `Error: ${message}\n    at Function.handler (/app/src/handlers/assessment.js:45:12)\n    at processRequest (/app/src/middleware/auth.js:23:8)` :
          undefined,
      });
    }

    return mockLogs.sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime());
  };

  // Generate mock agent interactions
  const generateMockAgentInteractions = (): AgentInteraction[] => {
    const agents = [
      'DocumentAnalyzer',
      'CodeParser',
      'DependencyMapper',
      'SecurityScanner',
      'CostEstimator',
      'ReportGenerator',
      'KnowledgeBase',
      'ChatAssistant',
      'WorkflowOrchestrator',
      'ValidationAgent'
    ];

    const interactionTypes: AgentInteraction['interactionType'][] = ['REQUEST', 'RESPONSE', 'BROADCAST', 'DELEGATION'];
    const statuses: AgentInteraction['status'][] = ['SUCCESS', 'FAILED', 'PENDING'];

    const payloadExamples = [
      { type: 'file_analysis', files: ['app.py', 'requirements.txt'], language: 'python' },
      { type: 'dependency_scan', dependencies: ['flask', 'sqlalchemy', 'redis'], vulnerabilities: 2 },
      { type: 'cost_calculation', resources: { cpu: 4, memory: '8GB', storage: '100GB' }, estimate: '$245/month' },
      { type: 'security_findings', issues: ['Security scan completed', 'Dependencies updated'], severity: 'low' },
      { type: 'report_section', section: 'infrastructure_analysis', status: 'completed', pages: 5 },
      { type: 'knowledge_query', question: 'What are the migration risks?', context: 'database_migration' },
      { type: 'workflow_status', step: 'document_parsing', progress: 75, eta: '2 minutes' },
      { type: 'validation_result', checks: ['syntax', 'dependencies', 'security'], passed: 8, failed: 2 }
    ];

    const mockInteractions: AgentInteraction[] = [];
    const now = new Date();

    for (let i = 0; i < 150; i++) {
      const timestamp = new Date(now.getTime() - Math.random() * 24 * 60 * 60 * 1000);
      const sourceAgent = agents[Math.floor(Math.random() * agents.length)];
      let targetAgent = agents[Math.floor(Math.random() * agents.length)];

      // Ensure source and target are different
      while (targetAgent === sourceAgent) {
        targetAgent = agents[Math.floor(Math.random() * agents.length)];
      }

      const interactionType = interactionTypes[Math.floor(Math.random() * interactionTypes.length)];
      const status = statuses[Math.floor(Math.random() * statuses.length)];
      const payload = payloadExamples[Math.floor(Math.random() * payloadExamples.length)];

      mockInteractions.push({
        id: `interaction_${i}`,
        timestamp,
        sourceAgent,
        targetAgent,
        interactionType,
        payload,
        status,
        duration: status === 'SUCCESS' ? Math.floor(Math.random() * 5000) : undefined,
        projectId: Math.random() > 0.7 ? `project_${Math.floor(Math.random() * 5) + 1}` : undefined,
        projectName: Math.random() > 0.7 ? `Project ${Math.floor(Math.random() * 5) + 1}` : undefined,
        metadata: {
          requestId: `req_${Math.random().toString(36).substr(2, 9)}`,
          correlationId: `corr_${Math.random().toString(36).substr(2, 9)}`,
          retryCount: Math.floor(Math.random() * 3),
        }
      });
    }

    return mockInteractions.sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime());
  };

// Fetch logs from backend (REST). Used for service=all or when live stream is off.
  const fetchLogs = async () => {
    setLoading(true);
    try {
      // Prefer new search endpoint when correlationId or searchTerm is provided
      const hasSearch = (filters.searchTerm && filters.searchTerm.trim().length > 0) || (filters.correlationId && filters.correlationId.trim().length > 0) || (filters.servicesMulti && filters.servicesMulti.length > 0) || (filters.service && filters.service !== 'all');
      let fetched: LogEntry[] = [];
      if (hasSearch) {
        const params = new URLSearchParams();
        if (filters.searchTerm) params.set('q', filters.searchTerm);
        if (filters.correlationId) params.set('cid', filters.correlationId);
        // Services: multi-select has priority; else use single service if not 'all'
        if (filters.servicesMulti && filters.servicesMulti.length > 0) {
          params.set('services', filters.servicesMulti.join(','));
        } else if (filters.service && filters.service !== 'all') {
          params.set('services', filters.service);
        }
        // Level
        if (filters.level && filters.level !== 'all') params.set('level', filters.level);
        // Project id
        if (selectedProjectId && selectedProjectId !== 'all') params.set('project_id', selectedProjectId);
        // Time range -> from=now - range
        const now = Date.now();
        const rangeMs = {
          '15m': 15 * 60 * 1000,
          '1h': 60 * 60 * 1000,
          '6h': 6 * 60 * 60 * 1000,
          '24h': 24 * 60 * 60 * 1000,
          '7d': 7 * 24 * 60 * 60 * 1000,
        }[filters.timeRange] || 60 * 60 * 1000;
        const fromTs = new Date(now - rangeMs).toISOString();
        params.set('from', fromTs);
        params.set('limit', '200');
    const resp = await fetch(`${process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000'}/api/logs/search?${params.toString()}`);
        const data = await resp.json();
        fetched = (data.entries || []).map((e: any, idx: number) => ({
          id: e.id || `log_${idx}`,
          timestamp: new Date(e.timestamp || new Date().toISOString()),
          level: (e.level || 'INFO') as LogEntry['level'],
          service: e.service || 'unknown',
          message: e.message || ''
        }));
      } else {
        const serviceParam = filters.service || 'all';
        const resp = await fetch(`http://localhost:8000/api/logs?service=${encodeURIComponent(serviceParam)}&tail=200`);
        const data = await resp.json();
        fetched = (data.entries || []).map((e: any, idx: number) => ({
          id: e.id || `log_${idx}`,
          timestamp: new Date(e.timestamp || new Date().toISOString()),
          level: (e.level || 'INFO') as LogEntry['level'],
          service: e.service || serviceParam,
          message: e.message || ''
        }));
      }
      setLogs(fetched);
    } catch (error) {
      console.error('Failed to fetch logs:', error);
    } finally {
      setLoading(false);
    }
  };

  // Fetch projects for project selector
  const fetchProjects = async () => {
    try {
      const resp = await fetch('http://localhost:8000/api/projects');
      const data = await resp.json();
      const proj = (data || []).map((p: any) => ({ id: p.id, name: p.name || p.id }));
      setProjects(proj);
    } catch (e) {
      console.error('Failed to fetch projects:', e);
    }
  };

  // Fetch list of services from backend
  const fetchServices = async () => {
    try {
      const resp = await fetch('http://localhost:8000/api/logs/services');
      const data = await resp.json();
      const list = Array.isArray(data.services) ? data.services : [];
      setAvailableServices(list);
    } catch (e) {
      console.error('Failed to fetch services:', e);
      setAvailableServices([]);
    }
  };

  // Fetch agent interactions for selected project (REST)
  const fetchAgentInteractions = async (projectId: string) => {
    if (!projectId || projectId === 'all') {
      setAgentInteractions([]);
      return;
    }
    try {
      const resp = await fetch(`http://localhost:8000/api/projects/${encodeURIComponent(projectId)}/crew-interactions?limit=200`);
      const data = await resp.json();
      const list = (data.interactions || []).map((it: any, idx: number) => ({
        id: it.id || `interaction_${idx}`,
        timestamp: new Date(it.timestamp || new Date().toISOString()),
        sourceAgent: it.agent_name || 'Agent',
        targetAgent: it.tool_name || it.function_name || 'N/A',
        interactionType: (it.type || 'REQUEST').toUpperCase(),
        payload: it.request_data || it.response_data || { text: it.request_text || it.response_text },
        status: (it.status || 'SUCCESS').toUpperCase(),
        duration: it.duration_ms || undefined,
        projectId: it.project_id,
        projectName: projects.find(p => p.id === it.project_id)?.name,
        metadata: it.metadata || {},
      }));
      setAgentInteractions(list);
    } catch (e) {
      console.error('Failed to fetch agent interactions:', e);
      setAgentInteractions([]);
    }
  };

  // Filter logs
  useEffect(() => {
    let filtered = [...logs];

    // Filter by level
    if (filters.level !== 'all') {
      filtered = filtered.filter(log => log.level === filters.level);
    }

    // Filter by service
    if (filters.service !== 'all') {
      filtered = filtered.filter(log => log.service === filters.service);
    }

    // Filter by project
    if (filters.projectId !== 'all') {
      filtered = filtered.filter(log => log.projectId === filters.projectId);
    }

    // Filter by time range
    const now = new Date();
    const timeRangeMs = {
      '15m': 15 * 60 * 1000,
      '1h': 60 * 60 * 1000,
      '6h': 6 * 60 * 60 * 1000,
      '24h': 24 * 60 * 60 * 1000,
      '7d': 7 * 24 * 60 * 60 * 1000,
    }[filters.timeRange] || 60 * 60 * 1000;

    filtered = filtered.filter(log =>
      now.getTime() - log.timestamp.getTime() <= timeRangeMs
    );

    // Filter by search term
  if (filters.searchTerm) {
      const searchLower = filters.searchTerm.toLowerCase();
      filtered = filtered.filter(log =>
        log.message.toLowerCase().includes(searchLower) ||
        log.service.toLowerCase().includes(searchLower) ||
        (log.projectName && log.projectName.toLowerCase().includes(searchLower))
      );
    }

    setFilteredLogs(filtered);
  }, [logs, filters]);

  // Filter agent interactions
  useEffect(() => {
    let filtered = [...agentInteractions];

    // Filter by time range
    const now = new Date();
    const timeRangeMs = {
      '15m': 15 * 60 * 1000,
      '1h': 60 * 60 * 1000,
      '6h': 6 * 60 * 60 * 1000,
      '24h': 24 * 60 * 60 * 1000,
      '7d': 7 * 24 * 60 * 1000,
    }[filters.timeRange] || 60 * 60 * 1000;

    filtered = filtered.filter(interaction =>
      now.getTime() - interaction.timestamp.getTime() <= timeRangeMs
    );

    // Filter by search term
    if (filters.searchTerm) {
      const searchLower = filters.searchTerm.toLowerCase();
      filtered = filtered.filter(interaction =>
        interaction.sourceAgent.toLowerCase().includes(searchLower) ||
        interaction.targetAgent.toLowerCase().includes(searchLower) ||
        interaction.interactionType.toLowerCase().includes(searchLower) ||
        JSON.stringify(interaction.payload).toLowerCase().includes(searchLower) ||
        (interaction.projectName && interaction.projectName.toLowerCase().includes(searchLower))
      );
    }

    setFilteredInteractions(filtered);
  }, [agentInteractions, filters]);

  // Auto-refresh (disabled when live stream is on)
  useEffect(() => {
    if (autoRefresh && !liveStream) {
      const interval = setInterval(fetchLogs, refreshInterval * 1000);
      return () => clearInterval(interval);
    }
  }, [autoRefresh, refreshInterval, liveStream, filters.service]);

  // WebSocket live stream for a specific service (not "all")
  useEffect(() => {
    // Close any existing socket first
    if (wsRef.current) {
      try { wsRef.current.close(); } catch {}
      wsRef.current = null;
    }

    if (!liveStream || !filters.service || filters.service === 'all') {
      return;
    }

    try {
      const ws = new WebSocket(`ws://localhost:8000/ws/logs/${encodeURIComponent(filters.service)}`);
      wsRef.current = ws;

      ws.onopen = () => {
        // Reset logs when starting live streaming for clarity
        setLogs([]);
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          const entry: LogEntry = {
            id: `${filters.service}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
            timestamp: new Date(msg.timestamp || new Date().toISOString()),
            level: (msg.level || 'INFO').toUpperCase(),
            service: msg.service || filters.service,
            message: msg.message || String(msg),
          } as LogEntry;
          setLogs(prev => {
            const next = [...prev, entry];
            // Cap to last 1000 entries
            return next.length > 1000 ? next.slice(next.length - 1000) : next;
          });
        } catch (e) {
          // Fallback: append raw text
          setLogs(prev => {
            const entry: LogEntry = {
              id: `${filters.service}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
              timestamp: new Date(),
              level: 'INFO',
              service: filters.service,
              message: typeof event.data === 'string' ? event.data : '[binary]'
            } as LogEntry;
            const next = [...prev, entry];
            return next.length > 1000 ? next.slice(next.length - 1000) : next;
          });
        }
      };

      ws.onerror = () => {
        console.error('WebSocket error');
      };
      ws.onclose = () => {
        // No-op; user can re-toggle live stream
      };
    } catch (e) {
      console.error('Failed to open WebSocket:', e);
    }

    return () => {
      if (wsRef.current) {
        try { wsRef.current.close(); } catch {}
        wsRef.current = null;
      }
    };
  }, [liveStream, filters.service]);

  // Initial load: fetch projects, logs, and interactions (if a project is selected)
  useEffect(() => {
  fetchProjects();
  fetchServices();
  fetchLogs();
  }, []);

  // When project selection changes, fetch interactions
  useEffect(() => {
    fetchAgentInteractions(selectedProjectId);
  }, [selectedProjectId]);

  // Initial load
  useEffect(() => {
    fetchLogs();
  }, []);

  // Helper functions
  const getLevelIcon = (level: LogEntry['level']) => {
    switch (level) {
      case 'DEBUG':
        return <IconBug size={14} color="#868e96" />;
      case 'INFO':
        return <IconInfoCircle size={14} color="#339af0" />;
      case 'WARNING':
        return <IconExclamationMark size={14} color="#ffd43b" />;
      case 'ERROR':
        return <IconAlertCircle size={14} color="#ff6b6b" />;
      case 'CRITICAL':
        return <IconAlertCircle size={14} color="#c92a2a" />;
      default:
        return <IconInfoCircle size={14} />;
    }
  };

  const getLevelColor = (level: LogEntry['level']) => {
    switch (level) {
      case 'DEBUG':
        return 'gray';
      case 'INFO':
        return 'blue';
      case 'WARNING':
        return 'yellow';
      case 'ERROR':
        return 'red';
      case 'CRITICAL':
        return 'red';
      default:
        return 'gray';
    }
  };

  const getServiceIcon = (service: string) => {
    if (service.includes('database') || service.includes('postgres')) {
      return <IconDatabase size={14} color="#339af0" />;
    }
    if (service.includes('service') || service.includes('backend')) {
      return <IconServer size={14} color="#51cf66" />;
    }
    if (service.includes('cloud') || service.includes('aws') || service.includes('azure')) {
      return <IconCloud size={14} color="#ffd43b" />;
    }
    return <IconSettings size={14} color="#868e96" />;
  };

  const exportLogs = () => {
    const csvContent = [
      'Timestamp,Level,Service,Message,Project,Request ID',
      ...filteredLogs.map(log =>
        `"${log.timestamp.toISOString()}","${log.level}","${log.service}","${log.message}","${log.projectName || ''}","${log.metadata?.requestId || ''}"`
      )
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `logs_${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <Container size="xl">
      <Stack gap="md">


        {/* Controls */}
        <Card shadow="sm" p="lg" radius="md" withBorder>
          <Grid>
            <Grid.Col span={12}>
              <Group justify="space-between" mb="md">
                <Group gap="md">
                  <Button
                    leftSection={<IconRefresh size={16} />}
                    onClick={fetchLogs}
                    loading={loading}
                    variant="light"
                  >
                    Refresh
                  </Button>

                  <Group gap="xs">
                    <Switch
                      label="Auto-refresh"
                      checked={autoRefresh}
                      onChange={(event) => setAutoRefresh(event.currentTarget.checked)}
                      size="sm"
                      disabled={liveStream}
                    />
                    {autoRefresh && !liveStream && (
                      <NumberInput
                        value={refreshInterval}
                        onChange={(value) => setRefreshInterval(Number(value) || 5)}
                        min={1}
                        max={60}
                        suffix="s"
                        size="xs"
                        w={80}
                      />
                    )}
                    <Switch
                      ml="md"
                      label="Live stream"
                      checked={liveStream}
                      onChange={(e) => setLiveStream(e.currentTarget.checked)}
                      size="sm"
                      disabled={filters.service === 'all'}
                    />
                  </Group>
                </Group>

                <Group gap="md">
                  <Badge variant="light" color="blue">
                    {filteredLogs.length} entries
                  </Badge>
                  <Button
                    leftSection={<IconDownload size={16} />}
                    onClick={exportLogs}
                    variant="subtle"
                    size="sm"
                  >
                    Export CSV
                  </Button>
                </Group>
              </Group>

              <Divider mb="md" />

              {/* Filters */}
              <Grid>
                <Grid.Col span={2}>
                  <Select
                    label="Level"
                    value={filters.level}
                    onChange={(value) => setFilters(prev => ({ ...prev, level: value || 'all' }))}
                    data={[
                      { value: 'all', label: 'All Levels' },
                      { value: 'DEBUG', label: 'Debug' },
                      { value: 'INFO', label: 'Info' },
                      { value: 'WARNING', label: 'Warning' },
                      { value: 'ERROR', label: 'Error' },
                      { value: 'CRITICAL', label: 'Critical' },
                    ]}
                    size="sm"
                  />
                </Grid.Col>

                <Grid.Col span={2}>
                  <Select
                    label="Service"
                    value={filters.service}
                    onChange={(value) => setFilters(prev => ({ ...prev, service: value || 'all' }))}
                    data={[{ value: 'all', label: 'All Services' }, ...availableServices.map(s => ({ value: s, label: s }))]}
                    size="sm"
                  />
                </Grid.Col>

                <Grid.Col span={3}>
                  <Select
                    label="Project (for agent interactions)"
                    placeholder="Select a project"
                    value={selectedProjectId}
                    onChange={(value) => setSelectedProjectId(value || 'all')}
                    data={[{ value: 'all', label: 'All Projects' }, ...projects
                      .filter((p) => p && p.id != null && p.name)
                      .map((p) => ({ value: String(p.id), label: String(p.name) }))]}
                    size="sm"
                    searchable
                  />
                </Grid.Col>

                <Grid.Col span={2}>
                  <Select
                    label="Time Range"
                    value={filters.timeRange}
                    onChange={(value) => setFilters(prev => ({ ...prev, timeRange: value || '1h' }))}
                    data={[
                      { value: '15m', label: 'Last 15 minutes' },
                      { value: '1h', label: 'Last hour' },
                      { value: '6h', label: 'Last 6 hours' },
                      { value: '24h', label: 'Last 24 hours' },
                      { value: '7d', label: 'Last 7 days' },
                    ]}
                    size="sm"
                  />
                </Grid.Col>

                <Grid.Col span={6}>
                  <TextInput
                    label="Search"
                    placeholder="Search logs..."
                    value={filters.searchTerm}
                    onChange={(event) => setFilters(prev => ({ ...prev, searchTerm: event.currentTarget.value }))}
                    leftSection={<IconSearch size={16} />}
                    size="sm"
                  />
                </Grid.Col>

                <Grid.Col span={3}>
                  <TextInput
                    label="Correlation ID"
                    placeholder="Enter correlation id"
                    value={filters.correlationId || ''}
                    onChange={(e) => setFilters(prev => ({ ...prev, correlationId: e.currentTarget.value }))}
                    size="sm"
                  />
                </Grid.Col>

                <Grid.Col span={5}>
                  <MultiSelect
                    label="Limit to services"
                    placeholder="Select one or more services"
                    data={availableServices.map(s => ({ value: s, label: s }))}
                    value={filters.servicesMulti || []}
                    onChange={(value) => setFilters(prev => ({ ...prev, servicesMulti: (value || []).map(String) }))}
                    searchable
                    clearable
                    size="sm"
                  />
                </Grid.Col>
              </Grid>
            </Grid.Col>
          </Grid>
        </Card>

        {/* Tabs for different log types */}
        <Tabs value={activeTab} onChange={(value) => setActiveTab(value || 'platform')}>
          <Tabs.List>
            <Tabs.Tab value="platform" leftSection={<IconServer size={16} />}>
              Platform Logs
            </Tabs.Tab>
            <Tabs.Tab value="agents" leftSection={<IconSettings size={16} />}>
              AI Agent Interactions
            </Tabs.Tab>
          </Tabs.List>

          {/* Platform Logs Tab */}
          <Tabs.Panel value="platform" pt="xl">
            <Card shadow="sm" p="lg" radius="md" withBorder>
          <ScrollArea h={600}>
            <Table striped highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Timestamp</Table.Th>
                  <Table.Th>Level</Table.Th>
                  <Table.Th>Service</Table.Th>
                  <Table.Th>Message</Table.Th>
                  <Table.Th>Project</Table.Th>
                  <Table.Th>Request ID</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {filteredLogs.map((log) => (
                  <Table.Tr key={log.id}>
                    <Table.Td>
                      <Text size="xs" ff="monospace" c="dimmed">
                        {log.timestamp.toLocaleString()}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      <Group gap="xs">
                        {getLevelIcon(log.level)}
                        <Badge size="xs" color={getLevelColor(log.level)} variant="light">
                          {log.level}
                        </Badge>
                      </Group>
                    </Table.Td>
                    <Table.Td>
                      <Group gap="xs">
                        {getServiceIcon(log.service)}
                        <Text size="sm" fw={500}>
                          {log.service}
                        </Text>
                      </Group>
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm" style={{ maxWidth: 400, wordBreak: 'break-word' }}>
                        {log.message}
                      </Text>
                      {log.stackTrace && (
                        <Code block mt="xs" style={{ maxWidth: 400, fontSize: '11px' }}>
                          {log.stackTrace}
                        </Code>
                      )}
                    </Table.Td>
                    <Table.Td>
                      {log.projectName ? (
                        <Badge size="sm" variant="light" color="blue">
                          {log.projectName}
                        </Badge>
                      ) : (
                        <Text size="xs" c="dimmed">-</Text>
                      )}
                    </Table.Td>
                    <Table.Td>
                      <Text size="xs" ff="monospace" c="dimmed">
                        {log.metadata?.requestId || '-'}
                      </Text>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </ScrollArea>
        </Card>
            </Tabs.Panel>

            {/* AI Agent Interactions Tab */}
            <Tabs.Panel value="agents" pt="xl">
              <Card shadow="sm" p="lg" radius="md" withBorder>
                <ScrollArea h={600}>
                  <Table striped highlightOnHover>
                    <Table.Thead>
                      <Table.Tr>
                        <Table.Th>Timestamp</Table.Th>
                        <Table.Th>Source Agent</Table.Th>
                        <Table.Th>Target Agent</Table.Th>
                        <Table.Th>Type</Table.Th>
                        <Table.Th>Status</Table.Th>
                        <Table.Th>Duration</Table.Th>
                        <Table.Th>Payload</Table.Th>
                        <Table.Th>Project</Table.Th>
                      </Table.Tr>
                    </Table.Thead>
                    <Table.Tbody>
                      {filteredInteractions.map((interaction) => (
                        <AgentInteractionRow key={interaction.id} interaction={interaction} />
                      ))}
                    </Table.Tbody>
                  </Table>
                </ScrollArea>
              </Card>
            </Tabs.Panel>
          </Tabs>

        {/* Summary Stats */}
        <Grid>
          <Grid.Col span={3}>
            <Card shadow="sm" p="md" radius="md" withBorder>
              <Group justify="space-between">
                <div>
                  <Text size="xs" tt="uppercase" fw={700} c="dimmed">
                    Total Logs
                  </Text>
                  <Text size="xl" fw={700}>
                    {filteredLogs.length}
                  </Text>
                </div>
                <IconInfoCircle size={24} color="#339af0" />
              </Group>
            </Card>
          </Grid.Col>

          <Grid.Col span={3}>
            <Card shadow="sm" p="md" radius="md" withBorder>
              <Group justify="space-between">
                <div>
                  <Text size="xs" tt="uppercase" fw={700} c="dimmed">
                    Errors
                  </Text>
                  <Text size="xl" fw={700} c="red">
                    {filteredLogs.filter(log => log.level === 'ERROR' || log.level === 'CRITICAL').length}
                  </Text>
                </div>
                <IconAlertCircle size={24} color="#ff6b6b" />
              </Group>
            </Card>
          </Grid.Col>

          <Grid.Col span={3}>
            <Card shadow="sm" p="md" radius="md" withBorder>
              <Group justify="space-between">
                <div>
                  <Text size="xs" tt="uppercase" fw={700} c="dimmed">
                    Warnings
                  </Text>
                  <Text size="xl" fw={700} c="yellow">
                    {filteredLogs.filter(log => log.level === 'WARNING').length}
                  </Text>
                </div>
                <IconExclamationMark size={24} color="#ffd43b" />
              </Group>
            </Card>
          </Grid.Col>

          <Grid.Col span={3}>
            <Card shadow="sm" p="md" radius="md" withBorder>
              <Group justify="space-between">
                <div>
                  <Text size="xs" tt="uppercase" fw={700} c="dimmed">
                    Services
                  </Text>
                  <Text size="xl" fw={700}>
                    {new Set(filteredLogs.map(log => log.service)).size}
                  </Text>
                </div>
                <IconServer size={24} color="#51cf66" />
              </Group>
            </Card>
          </Grid.Col>
        </Grid>
      </Stack>
    </Container>
  );
};

export default LogsView;
