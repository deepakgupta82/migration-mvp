import React, { useState, useEffect, useRef } from 'react';
import {
  Card,
  Text,
  Button,
  Group,
  Stack,
  ScrollArea,
  Badge,
  ActionIcon,
  Switch,
  Select,
  Paper,
  Grid,
  Progress,
  Alert,
  Code,
  Divider,
  SegmentedControl,
} from '@mantine/core';
import ModernConsole from './ModernConsole';
import { LogsView } from '../../views/LogsView';
import {
  IconPlayerPlay,
  IconPlayerStop,
  IconTrash,
  IconDownload,
  IconRefresh,
  IconTerminal,
  IconServer,
  IconDatabase,
  IconRobot,
  IconContainer,
  IconActivity,
  IconAlertTriangle,
  IconCheck,
  IconX,
  IconCode,
  IconList,
} from '@tabler/icons-react';

interface LogEntry {
  timestamp: string;
  level: 'INFO' | 'WARNING' | 'ERROR' | 'DEBUG';
  service: string;
  message: string;
  details?: any;
}

interface ServiceStatus {
  name: string;
  status: 'running' | 'stopped' | 'error';
  uptime: string;
  cpu: number;
  memory: number;
  logs_enabled: boolean;
}

interface ContainerStats {
  name: string;
  status: 'running' | 'exited' | 'restarting';
  cpu_percent: number;
  memory_usage: string;
  memory_limit: string;
  network_io: string;
  block_io: string;
}

export const SystemLogsViewer: React.FC = () => {
  const [activeTab, setActiveTab] = useState<string>(typeof window !== 'undefined' && window.location.hash ? window.location.hash.substring(1) : 'overview');
  const [viewMode, setViewMode] = useState<Record<string, 'console' | 'logs'>>({});
  const [selectedContainer, setSelectedContainer] = useState<string>('neo4j');
  const [logTimeRange, setLogTimeRange] = useState<string>('1h');

  // Helper function to get view mode for a service (default to 'logs')
  const getViewMode = (service: string): 'console' | 'logs' => {
    return viewMode[service] || 'logs';
  };

  // Helper function to set view mode for a service
  const setServiceViewMode = (service: string, mode: 'console' | 'logs') => {
    setViewMode(prev => ({ ...prev, [service]: mode }));
  };

  const [serviceStatus, setServiceStatus] = useState<ServiceStatus[]>([
    { name: 'Backend API', status: 'running', uptime: '—', cpu: 0, memory: 0, logs_enabled: false },
    { name: 'Project Service', status: 'running', uptime: '—', cpu: 0, memory: 0, logs_enabled: false },
    { name: 'Reporting Service', status: 'running', uptime: '—', cpu: 0, memory: 0, logs_enabled: false },
    { name: 'Frontend', status: 'running', uptime: '—', cpu: 0, memory: 0, logs_enabled: false },
  ]);

  const [containerStats, setContainerStats] = useState<ContainerStats[]>([
    { name: 'neo4j', status: 'running', cpu_percent: 0, memory_usage: '—', memory_limit: '—', network_io: '—', block_io: '—' },
    { name: 'postgresql', status: 'running', cpu_percent: 0, memory_usage: '—', memory_limit: '—', network_io: '—', block_io: '—' },
    { name: 'minio', status: 'running', cpu_percent: 0, memory_usage: '—', memory_limit: '—', network_io: '—', block_io: '—' },
  ]);

  // Real system health from backend /health
  const [healthStatus, setHealthStatus] = useState<'healthy' | 'degraded' | 'unknown'>('unknown');
  const [servicesHealth, setServicesHealth] = useState<Record<string, string>>({});
  const fetchSystemHealth = async () => {
    try {
  const resp = await fetch('/api/health');
      if (!resp.ok) throw new Error(String(resp.status));
      const data = await resp.json();
      setHealthStatus((data.status as 'healthy' | 'degraded') || 'unknown');
      setServicesHealth((data.services as Record<string, string>) || {});
    } catch (e) {
      setHealthStatus('unknown');
      setServicesHealth({});
    }
  };

  // Container stats from separate endpoint for better performance
  const fetchContainerStats = async () => {
    try {
      // Prefer gateway path first
      let resp = await fetch('/api/health/containers');
      if (!resp.ok) {
        // Fallback to direct backend when alias route isn't available
        const base = typeof window !== 'undefined' ? `${window.location.protocol}//${window.location.hostname}:8000` : 'http://localhost:8000';
        resp = await fetch(`${base}/health/containers`);
      }
      if (!resp.ok) throw new Error(String(resp.status));
      const data = await resp.json();
      if (data.containers) {
        setContainerStats(data.containers);
      }
    } catch (e) {
      console.error('Container stats failed:', e);
    }
  };





  const getStatusColor = (status: string) => {
    switch (status) {
      case 'running': return 'green';
      case 'stopped': return 'gray';
      case 'error': return 'red';
      case 'exited': return 'orange';
      case 'restarting': return 'yellow';
      default: return 'gray';
    }
  };



  const renderServiceTab = (service: string, icon: React.ReactNode, title: string) => {
    const currentMode = getViewMode(service);

    return (
      <Stack gap="xs">
        {/* Console/Logs Toggle */}
        <Group justify="space-between" align="center" wrap="nowrap" style={{ minHeight: '32px' }}>
          <Group gap="sm" style={{ flex: 1, minWidth: 0 }}>
            {icon}
            <Text size="md" fw={600} style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{title}</Text>
          </Group>

          <SegmentedControl
            size="sm"
            value={currentMode}
            onChange={(value) => setServiceViewMode(service, value as 'console' | 'logs')}
            style={{ minWidth: '200px' }}
            data={[
              {
                label: (
                  <Group gap="xs" justify="center" wrap="nowrap" style={{ minWidth: '80px' }}>
                    <IconCode size={14} />
                    <Text size="xs" style={{ whiteSpace: 'nowrap' }}>Console</Text>
                  </Group>
                ),
                value: 'console'
              },
              {
                label: (
                  <Group gap="xs" justify="center" wrap="nowrap" style={{ minWidth: '80px' }}>
                    <IconList size={14} />
                    <Text size="xs" style={{ whiteSpace: 'nowrap' }}>Logs</Text>
                  </Group>
                ),
                value: 'logs'
              }
            ]}
          />
        </Group>

        {/* Console/Logs Content */}
    {currentMode === 'console' ? (
          <ModernConsole
            service={service}
            title=""
            icon={<IconCode size={20} />}
            mode="console"
          />
        ) : (
          <ModernConsole
            service={service}
            title=""
            icon={<IconList size={20} />}
      mode="logs"
      timeRange={logTimeRange as any}
          />
        )}
      </Stack>
    );
  };



  // Sync tab with URL hash changes
  useEffect(() => {
    const handler = () => {
      const tab = window.location.hash ? window.location.hash.substring(1) : 'overview';
      setActiveTab(tab || 'overview');
    };
    window.addEventListener('hashchange', handler);
    return () => window.removeEventListener('hashchange', handler);
  }, []);

  // Real updates: poll backend health for service status and container stats
  useEffect(() => {
    fetchSystemHealth();
    fetchContainerStats();
    const healthInterval = setInterval(() => fetchSystemHealth(), 120000);
    const containerInterval = setInterval(() => fetchContainerStats(), 60000);
    return () => {
      clearInterval(healthInterval);
      clearInterval(containerInterval);
    };
  }, []);

  const renderOverview = () => (
          <Grid>
            <Grid.Col span={6}>
              <Card withBorder>
                <Text size="md" fw={600} mb="md">Application Services</Text>
                <Stack gap="sm">
                  {Object.entries(servicesHealth).filter(([name]) => !name.startsWith('weaviate_')).map(([name, status]) => (
                    <Group key={name} justify="space-between">
                      <Group gap="sm">
                        <Badge color={status === 'connected' ? 'green' : 'red'} size="sm">
                          {status === 'connected' ? 'running' : 'error'}
                        </Badge>
                        <Text size="sm" fw={500}>{name}</Text>
                      </Group>
                      <Group gap="sm">
                        <Text size="xs" c="dimmed">Status: {String(status)}</Text>
                      </Group>
                    </Group>
                  ))}
                </Stack>

                <Divider my="sm" />

                <Text size="md" fw={600} mb="md">Vector Database (ChromaDB)</Text>
                <Stack gap="xs">
                  <Group justify="space-between">
                    <Text size="sm" fw={500}>Status</Text>
                    <Badge color={servicesHealth['chromadb'] === 'connected' ? 'green' : 'red'}>
                      {servicesHealth['chromadb'] === 'connected' ? 'Connected' : 'Error'}
                    </Badge>
                  </Group>
                  <Group justify="space-between">
                    <Text size="sm" fw={500}>Storage</Text>
                    <Text size="sm" c="dimmed">Local File System</Text>
                  </Group>
                  <Group justify="space-between">
                    <Text size="sm" fw={500}>Type</Text>
                    <Text size="sm" c="dimmed">Persistent Client</Text>
                  </Group>
                </Stack>
              </Card>
                <Divider my="sm" />
                <Text size="md" fw={600} mb="md">Databases</Text>
                <Stack gap="xs">
                  <Group justify="space-between">
                    <Text size="sm" fw={500}>PostgreSQL Version</Text>
                    <Badge variant="light">{servicesHealth['postgresql_version'] || 'unknown'}</Badge>
                  </Group>
                  <Group justify="space-between">
                    <Text size="sm" fw={500}>Neo4j Version</Text>
                    <Badge variant="light">{servicesHealth['neo4j_version'] || 'unknown'}</Badge>
                  </Group>
                </Stack>

            </Grid.Col>

            <Grid.Col span={6}>
              <Card withBorder>
                <Text size="md" fw={600} mb="md">Container Services</Text>
                <Stack gap="sm">
                  {containerStats.filter(container => container && container.name).map((container, index) => (
                    <Group key={index} justify="space-between">
                      <Group gap="sm">
                        <Badge color={getStatusColor(container.status)} size="sm">
                          {container.status}
                        </Badge>
                        <Text size="sm" fw={500}>{container.name}</Text>
                      </Group>
                      <Group gap="sm">
                        <Text size="xs" c="dimmed">CPU: {Math.round(container.cpu_percent || 0)}%</Text>
                        <Text size="xs" c="dimmed">RAM: {container.memory_usage || '—'}</Text>
                      </Group>
                    </Group>
                  ))}
                </Stack>
              </Card>
            </Grid.Col>
          </Grid>
  );

  const renderLogs = () => (
    <div style={{ paddingTop: 4 }}>
      <LogsView />
    </div>
  );

  const renderService = (key: string, icon: React.ReactNode, title: string) => (
    <div>{renderServiceTab(key, icon, title)}</div>
  );

  const renderContainers = () => (
    <div>
      <Stack gap="sm">
        <Group justify="space-between">
          <Group gap="sm">
            <IconContainer size={20} />
            <Text size="lg" fw={600}>Container Monitoring</Text>
          </Group>
          <Group gap="sm">
            <Button
              size="xs"
              variant="light"
              leftSection={<IconRefresh size={14} />}
              onClick={() => {
                fetchContainerStats();
              }}
            >
              Refresh Stats
            </Button>
          </Group>
        </Group>

        <Card withBorder p="sm">
          <ScrollArea h={220}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ backgroundColor: '#fafafa' }}>
                  <th style={{ textAlign: 'left', padding: '8px' }}>Container</th>
                  <th style={{ textAlign: 'left', padding: '8px' }}>Status</th>
                  <th style={{ textAlign: 'right', padding: '8px' }}>CPU%</th>
                  <th style={{ textAlign: 'right', padding: '8px' }}>Memory</th>
                  <th style={{ textAlign: 'right', padding: '8px' }}>Network I/O</th>
                  <th style={{ textAlign: 'right', padding: '8px' }}>Block I/O</th>
                  <th style={{ textAlign: 'right', padding: '8px' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {containerStats.filter(c => c && c.name).map((c) => (
                  <tr key={c.name} style={{ borderBottom: '1px solid #f0f0f0' }}>
                    <td style={{ padding: '8px' }}>
                      <Group gap="xs">
                        <IconContainer size={16} />
                        <Text size="sm" fw={500}>{c.name}</Text>
                      </Group>
                    </td>
                    <td style={{ padding: '8px' }}>
                      <Badge color={getStatusColor(c.status)} size="sm">{c.status}</Badge>
                    </td>
                    <td style={{ padding: '8px', textAlign: 'right' }}>{Math.round(c.cpu_percent || 0)}%</td>
                    <td style={{ padding: '8px', textAlign: 'right' }}>{c.memory_usage || '—'} / {c.memory_limit || '—'}</td>
                    <td style={{ padding: '8px', textAlign: 'right' }}>{c.network_io || '—'}</td>
                    <td style={{ padding: '8px', textAlign: 'right' }}>{c.block_io || '—'}</td>
                    <td style={{ padding: '8px', textAlign: 'right' }}>
                      <Group gap="xs" justify="right">
                        <ActionIcon size="sm" variant="light" color="blue" onClick={() => { setSelectedContainer(c.name); setServiceViewMode(c.name, 'console'); }} title="Console">
                          <IconCode size={14} />
                        </ActionIcon>
                        <ActionIcon size="sm" variant="light" color="gray" onClick={() => { setSelectedContainer(c.name); setServiceViewMode(c.name, 'logs'); }} title="Logs">
                          <IconList size={14} />
                        </ActionIcon>
                      </Group>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollArea>
        </Card>

        {/* Selector below the table to open a single panel */}
        <Group gap="sm" align="end">
          <Select
            label="Select service"
            placeholder="Choose a container"
            data={[...new Set([ 'neo4j', 'postgresql', 'minio', 'redis', 'loki', 'promtail', ...containerStats.filter(c=>c&&c.name).map(c=>c.name)])]
              .map(name => ({ value: name, label: name }))}
            value={selectedContainer}
            onChange={(v) => v && setSelectedContainer(v)}
            size="sm"
            w={240}
          />
          {getViewMode(selectedContainer) === 'logs' && (
            <Select
              label="Time"
              data={[
                { value: '15m', label: '15m' },
                { value: '1h', label: '1h' },
                { value: '6h', label: '6h' },
                { value: '24h', label: '24h' },
                { value: '7d', label: '7d' },
              ]}
              value={logTimeRange}
              onChange={(v)=> v && setLogTimeRange(v)}
              size="sm"
              w={100}
            />
          )}
        </Group>

        {/* Single dynamic panel */}
        <div style={{ marginTop: '8px' }}>
          {renderServiceTab(selectedContainer, <IconContainer size={20} />, `${selectedContainer}`)}
        </div>
      </Stack>
    </div>
  );

  const renderActiveContent = () => {
    switch (activeTab) {
      case 'overview':
        return renderOverview();
      case 'logs':
        return renderLogs();
      case 'backend':
        return renderService('backend', <IconServer size={20} />, 'Backend API');
      case 'project_service':
        return renderService('project_service', <IconDatabase size={20} />, 'Project Service');
      case 'reporting_service':
        return renderService('reporting_service', <IconTerminal size={20} />, 'Reporting Service');
      case 'document_service':
        return renderService('document_service', <IconDatabase size={20} />, 'Document Service');
      case 'vector_service':
        return renderService('vector_service', <IconDatabase size={20} />, 'Vector Service');
      case 'llm_service':
        return renderService('llm_service', <IconRobot size={20} />, 'LLM Service');
      case 'graph_service':
        return renderService('graph_service', <IconDatabase size={20} />, 'Graph Service');
      case 'ai_agent_service':
        return renderService('ai_agent_service', <IconRobot size={20} />, 'AI Agent Service');
      case 'websocket_service':
        return renderService('websocket_service', <IconTerminal size={20} />, 'WebSocket Service');
      case 'storage_service':
        return renderService('storage_service', <IconDatabase size={20} />, 'Storage Service');
      case 'chromadb':
        return renderService('chromadb', <IconDatabase size={20} />, 'ChromaDB');
      case 'containers':
        return renderContainers();
      default:
        return renderOverview();
    }
  };

  return (
    <Card shadow="sm" p={8} radius="md" withBorder style={{ width: '100%', maxWidth: 'none', marginTop: 2 }}>
      {renderActiveContent()}
    </Card>
  );
};

export default SystemLogsViewer;
