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
    { name: 'Backend API', status: 'running', uptime: '2h 15m', cpu: 12.5, memory: 256, logs_enabled: false },
    { name: 'Project Service', status: 'running', uptime: '2h 15m', cpu: 8.2, memory: 128, logs_enabled: false },
    { name: 'Reporting Service', status: 'running', uptime: '2h 14m', cpu: 5.1, memory: 96, logs_enabled: false },
    { name: 'Frontend', status: 'running', uptime: '2h 16m', cpu: 3.2, memory: 64, logs_enabled: false },
  ]);

  const [containerStats, setContainerStats] = useState<ContainerStats[]>([
    { name: 'weaviate', status: 'running', cpu_percent: 15.2, memory_usage: '512MB', memory_limit: '1GB', network_io: '1.2MB/s', block_io: '0.5MB/s' },
    { name: 'neo4j', status: 'running', cpu_percent: 8.7, memory_usage: '256MB', memory_limit: '512MB', network_io: '0.8MB/s', block_io: '0.2MB/s' },
    { name: 'postgresql', status: 'running', cpu_percent: 5.3, memory_usage: '128MB', memory_limit: '256MB', network_io: '0.3MB/s', block_io: '0.1MB/s' },
    { name: 'minio', status: 'running', cpu_percent: 2.1, memory_usage: '64MB', memory_limit: '128MB', network_io: '0.1MB/s', block_io: '0.05MB/s' },
  ]);





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



  // Mock data updates (replace with real API calls)
  useEffect(() => {
    const interval = setInterval(() => {
      // Update service status
      setServiceStatus(prev => prev.map(service => ({
        ...service,
        cpu: Math.max(0, service.cpu + (Math.random() - 0.5) * 5),
        memory: Math.max(0, service.memory + (Math.random() - 0.5) * 20),
      })));

      // Update container stats
      setContainerStats(prev => prev.map(container => ({
        ...container,
        cpu_percent: Math.max(0, container.cpu_percent + (Math.random() - 0.5) * 3),
      })));
    }, 5000);

    return () => clearInterval(interval);
  }, []);

  return (
    <Card shadow="sm" p="xs" radius="md" withBorder style={{ width: '100%', maxWidth: 'none', marginTop: '4px' }}>
      <Tabs value={activeTab} onChange={(value) => setActiveTab(value || 'overview')}>
        <Tabs.List style={{ flexWrap: 'nowrap', gap: '2px', overflowX: 'auto', minWidth: '100%' }}>
          <Tabs.Tab value="overview" leftSection={<IconActivity size={16} />} style={{ minWidth: '120px', flexShrink: 0 }}>
            Overview
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
                  {serviceStatus.map((service, index) => (
                    <Group key={index} justify="space-between">
                      <Group gap="sm">
                        <Badge color={getStatusColor(service.status)} size="sm">
                          {service.status}
                        </Badge>
                        <Text size="sm" fw={500}>{service.name}</Text>
                      </Group>
                      <Group gap="sm">
                        <Text size="xs" c="dimmed">CPU: {Math.round(service.cpu)}%</Text>
                        <Text size="xs" c="dimmed">RAM: {Math.round(service.memory)}MB</Text>
                        <Text size="xs" c="dimmed">{service.uptime}</Text>
                      </Group>
                    </Group>
                  ))}
                </Stack>
              </Card>
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
