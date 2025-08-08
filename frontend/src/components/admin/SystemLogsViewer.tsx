import React, { useState, useEffect, useRef } from 'react';
import {
  Card,
  Tabs,
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
  const [activeTab, setActiveTab] = useState<string>('overview');
  const [viewMode, setViewMode] = useState<Record<string, 'console' | 'logs'>>({});

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
      const resp = await fetch('http://localhost:8000/health');
      if (!resp.ok) throw new Error(String(resp.status));
      const data = await resp.json();
      setHealthStatus((data.status as 'healthy' | 'degraded') || 'unknown');
      setServicesHealth((data.services as Record<string, string>) || {});
    } catch (e) {
      setHealthStatus('unknown');
      setServicesHealth({});
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
          />
        )}
      </Stack>
    );
  };



  // Real updates: poll backend health for service status
  useEffect(() => {
    fetchSystemHealth();
    const interval = setInterval(() => fetchSystemHealth(), 15000);
    return () => clearInterval(interval);
  }, []);

  return (
    <Card shadow="sm" p="xs" radius="md" withBorder style={{ width: '100%', maxWidth: 'none', marginTop: '4px' }}>
      <Tabs value={activeTab} onChange={(value) => setActiveTab(value || 'overview')}>
        <Tabs.List style={{ flexWrap: 'nowrap', gap: '2px', overflowX: 'auto', minWidth: '100%' }}>
          <Tabs.Tab value="overview" leftSection={<IconActivity size={16} />} style={{ minWidth: '120px', flexShrink: 0 }}>
            System
          </Tabs.Tab>
          <Tabs.Tab value="backend" leftSection={<IconServer size={16} />} style={{ minWidth: '120px', flexShrink: 0 }}>
            Backend API
          </Tabs.Tab>
          <Tabs.Tab value="project_service" leftSection={<IconDatabase size={16} />} style={{ minWidth: '140px', flexShrink: 0 }}>
            Project Service
          </Tabs.Tab>
          <Tabs.Tab value="reporting_service" leftSection={<IconTerminal size={16} />} style={{ minWidth: '150px', flexShrink: 0 }}>
            Reporting Service
          </Tabs.Tab>
          <Tabs.Tab value="crews_agents" leftSection={<IconRobot size={16} />} style={{ minWidth: '140px', flexShrink: 0 }}>
            Crews & Agents
          </Tabs.Tab>
          <Tabs.Tab value="containers" leftSection={<IconContainer size={16} />} style={{ minWidth: '120px', flexShrink: 0 }}>
            Containers
          </Tabs.Tab>
        </Tabs.List>

        {/* Overview Tab */}
        <Tabs.Panel value="overview" pt="xs">
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
                  {containerStats.map((container, index) => (
                    <Group key={index} justify="space-between">
                      <Group gap="sm">
                        <Badge color={getStatusColor(container.status)} size="sm">
                          {container.status}
                        </Badge>
                        <Text size="sm" fw={500}>{container.name}</Text>
                      </Group>
                      <Group gap="sm">
                        <Text size="xs" c="dimmed">CPU: {Math.round(container.cpu_percent)}%</Text>
                        <Text size="xs" c="dimmed">RAM: {container.memory_usage}</Text>
                      </Group>
                    </Group>
                  ))}
                </Stack>
              </Card>
            </Grid.Col>
          </Grid>
        </Tabs.Panel>

        {/* Service Tabs */}
        <Tabs.Panel value="backend" pt="xs">
          {renderServiceTab('backend', <IconServer size={20} />, 'Backend API')}
        </Tabs.Panel>

        <Tabs.Panel value="project_service" pt="xs">
          {renderServiceTab('project_service', <IconDatabase size={20} />, 'Project Service')}
        </Tabs.Panel>

        <Tabs.Panel value="reporting_service" pt="xs">
          {renderServiceTab('reporting_service', <IconTerminal size={20} />, 'Reporting Service')}
        </Tabs.Panel>

        <Tabs.Panel value="crews_agents" pt="xs">
          {renderServiceTab('crews_agents', <IconRobot size={20} />, 'Crews & Agents')}
        </Tabs.Panel>

        {/* Containers Tab */}
        <Tabs.Panel value="containers" pt="xs">
          <Tabs defaultValue="overview">
            <Tabs.List style={{ flexWrap: 'nowrap', gap: '2px', overflowX: 'auto', minWidth: '100%' }}>
              <Tabs.Tab value="overview" leftSection={<IconContainer size={16} />} style={{ minWidth: '120px', flexShrink: 0 }}>
                Overview
              </Tabs.Tab>
              {containerStats.map((container) => (
                <Tabs.Tab key={container.name} value={container.name} leftSection={<IconTerminal size={16} />} style={{ minWidth: '140px', flexShrink: 0 }}>
                  {container.name}
                </Tabs.Tab>
              ))}
            </Tabs.List>

            {/* Container Overview Tab */}
            <Tabs.Panel value="overview" pt="xs">
              <Stack gap="sm">
                <Group justify="space-between">
                  <Group gap="sm">
                    <IconContainer size={20} />
                    <Text size="lg" fw={600}>Container Monitoring</Text>
                  </Group>
                  <Button
                    size="xs"
                    variant="light"
                    leftSection={<IconRefresh size={14} />}
                    onClick={() => {
                      // Refresh container stats
                      console.log('Refreshing container stats...');
                    }}
                  >
                    Refresh Stats
                  </Button>
                </Group>

                <Grid>
                  {containerStats.map((container, index) => (
                    <Grid.Col key={index} span={6}>
                      <Card withBorder p="md">
                        <Group justify="space-between" mb="sm">
                          <Group gap="sm">
                            <Text size="md" fw={600}>{container.name}</Text>
                            <Badge color={getStatusColor(container.status)}>
                              {container.status}
                            </Badge>
                          </Group>
                          <ActionIcon
                            size="sm"
                            variant="light"
                            color="blue"
                            onClick={() => {
                              // Switch to the container's log tab
                              console.log(`Switching to ${container.name} logs`);
                            }}
                          >
                            <IconTerminal size={14} />
                          </ActionIcon>
                        </Group>

                        <Stack gap="xs">
                          <Group justify="space-between">
                            <Text size="xs" c="dimmed">CPU Usage</Text>
                            <Text size="xs">{Math.round(container.cpu_percent)}%</Text>
                          </Group>
                          <Progress value={container.cpu_percent} size="sm" />

                          <Group justify="space-between">
                            <Text size="xs" c="dimmed">Memory</Text>
                            <Text size="xs">{container.memory_usage} / {container.memory_limit}</Text>
                          </Group>

                          <Group justify="space-between">
                            <Text size="xs" c="dimmed">Network I/O</Text>
                            <Text size="xs">{container.network_io}</Text>
                          </Group>

                          <Group justify="space-between">
                            <Text size="xs" c="dimmed">Block I/O</Text>
                            <Text size="xs">{container.block_io}</Text>
                          </Group>
                        </Stack>
                      </Card>
                    </Grid.Col>
                  ))}
                </Grid>
              </Stack>
            </Tabs.Panel>

            {/* Individual Container Log Tabs */}
            {containerStats.map((container) => (
              <Tabs.Panel key={container.name} value={container.name} pt="xs">
                {renderServiceTab(container.name, <IconContainer size={20} />, `${container.name}`)}
              </Tabs.Panel>
            ))}
          </Tabs>
        </Tabs.Panel>
      </Tabs>
    </Card>
  );
};

export default SystemLogsViewer;
