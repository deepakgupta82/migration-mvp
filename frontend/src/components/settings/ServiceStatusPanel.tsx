import React, { useState, useEffect } from 'react';
import {
  Card,
  Text,
  Group,
  Badge,
  Button,
  Stack,
  ActionIcon,
  Table,
  Modal,
  ScrollArea,
  Code,
  Alert,
  Loader,
  Progress,
  Divider,
  Box,
  Tooltip,
} from '@mantine/core';
import {
  IconCircleCheck,
  IconCircleX,
  IconCircle,
  IconRefresh,
  IconTerminal,
  IconPlayerPlay,
  IconPlayerStop,
  IconReload,
  IconExternalLink,
  IconClock,
} from '@tabler/icons-react';

interface ServiceInfo {
  name: string;
  url: string;
  port: number;
  status: 'healthy' | 'unhealthy' | 'starting' | 'stopped' | 'unknown';
  type: 'docker' | 'local';
  description: string;
  lastCheck: string;
  uptime?: string;
  version?: string;
  dependencies?: string[];
}

interface ServiceAction {
  service: string;
  action: 'start' | 'stop' | 'restart';
  status: 'idle' | 'running' | 'success' | 'error';
  logs: string[];
}

export const ServiceStatusPanel: React.FC = () => {
  const [services, setServices] = useState<ServiceInfo[]>([
    {
      name: 'Frontend',
      url: 'http://localhost:3000',
      port: 3000,
      status: 'healthy',
      type: 'local',
      description: 'React development server',
      lastCheck: new Date().toISOString(),
      uptime: '2h 15m',
      version: '0.1.0',
    },
    {
      name: 'Backend API',
      url: 'http://localhost:8000',
      port: 8000,
      status: 'healthy',
      type: 'local',
      description: 'FastAPI main service',
      lastCheck: new Date().toISOString(),
      uptime: '2h 10m',
      version: '1.0.0',
      dependencies: ['PostgreSQL', 'Weaviate', 'Neo4j'],
    },
    {
      name: 'Project Service',
      url: 'http://localhost:8002',
      port: 8002,
      status: 'healthy',
      type: 'local',
      description: 'Project management service',
      lastCheck: new Date().toISOString(),
      uptime: '2h 12m',
      dependencies: ['PostgreSQL'],
    },
    {
      name: 'PostgreSQL',
      url: 'localhost:5432',
      port: 5432,
      status: 'healthy',
      type: 'docker',
      description: 'Primary database',
      lastCheck: new Date().toISOString(),
      uptime: '2h 20m',
    },
    {
      name: 'Neo4j',
      url: 'http://localhost:7474',
      port: 7474,
      status: 'healthy',
      type: 'docker',
      description: 'Graph database',
      lastCheck: new Date().toISOString(),
      uptime: '2h 18m',
    },
    {
      name: 'Weaviate',
      url: 'http://localhost:8080',
      port: 8080,
      status: 'starting',
      type: 'docker',
      description: 'Vector database',
      lastCheck: new Date().toISOString(),
    },
    {
      name: 'MinIO',
      url: 'http://localhost:9001',
      port: 9001,
      status: 'healthy',
      type: 'docker',
      description: 'Object storage',
      lastCheck: new Date().toISOString(),
      uptime: '2h 19m',
    },
    {
      name: 'MegaParse',
      url: 'http://localhost:5001',
      port: 5001,
      status: 'healthy',
      type: 'docker',
      description: 'Document parsing service',
      lastCheck: new Date().toISOString(),
      uptime: '1h 45m',
    },
    {
      name: 'Reporting Service',
      url: 'http://localhost:8003',
      port: 8003,
      status: 'stopped',
      type: 'local',
      description: 'Report generation service',
      lastCheck: new Date().toISOString(),
    },
  ]);

  const [selectedService, setSelectedService] = useState<ServiceInfo | null>(null);
  const [serviceAction, setServiceAction] = useState<ServiceAction | null>(null);
  const [logsModalOpen, setLogsModalOpen] = useState(false);
  const [actionModalOpen, setActionModalOpen] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  // Mock service health check
  const checkServiceHealth = async (service: ServiceInfo): Promise<ServiceInfo['status']> => {
    // Simulate API call
    await new Promise(resolve => setTimeout(resolve, Math.random() * 1000));

    // Mock different statuses
    if (service.name === 'Weaviate') return 'starting';
    if (service.name === 'Reporting Service') return 'stopped';
    return Math.random() > 0.1 ? 'healthy' : 'unhealthy';
  };

  // Refresh all service statuses
  const refreshServices = async () => {
    setRefreshing(true);
    const updatedServices = await Promise.all(
      services.map(async (service) => ({
        ...service,
        status: await checkServiceHealth(service),
        lastCheck: new Date().toISOString(),
      }))
    );
    setServices(updatedServices);
    setRefreshing(false);
  };

  // Perform service action
  const performServiceAction = async (service: ServiceInfo, action: 'start' | 'stop' | 'restart') => {
    const newAction: ServiceAction = {
      service: service.name,
      action,
      status: 'running',
      logs: [`Starting ${action} operation for ${service.name}...`],
    };

    setServiceAction(newAction);
    setActionModalOpen(true);

    // Simulate action with logs
    const logMessages = [
      `Executing ${action} command...`,
      `Checking service dependencies...`,
      service.type === 'docker' ? 'Communicating with Docker daemon...' : 'Managing local process...',
      `${action === 'stop' ? 'Stopping' : 'Starting'} ${service.name}...`,
    ];

    for (let i = 0; i < logMessages.length; i++) {
      await new Promise(resolve => setTimeout(resolve, 1000));
      setServiceAction(prev => prev ? {
        ...prev,
        logs: [...prev.logs, logMessages[i]],
      } : null);
    }

    // Final result
    await new Promise(resolve => setTimeout(resolve, 1000));
    const success = Math.random() > 0.2; // 80% success rate

    setServiceAction(prev => prev ? {
      ...prev,
      status: success ? 'success' : 'error',
      logs: [...prev.logs, success ?
        `${action} completed successfully!` :
        `${action} failed. Check service logs for details.`
      ],
    } : null);

    // Update service status
    if (success) {
      setServices(prev => prev.map(s =>
        s.name === service.name ? {
          ...s,
          status: action === 'stop' ? 'stopped' : 'healthy',
          lastCheck: new Date().toISOString(),
        } : s
      ));
    }
  };

  const getStatusIcon = (status: ServiceInfo['status']) => {
    switch (status) {
      case 'healthy':
        return <IconCircleCheck size={16} color="#51cf66" />;
      case 'unhealthy':
        return <IconCircleX size={16} color="#ff6b6b" />;
      case 'starting':
        return <IconClock size={16} color="#ffd43b" />;
      case 'stopped':
        return <IconCircle size={16} color="#868e96" />;
      default:
        return <IconCircle size={16} color="#868e96" />;
    }
  };

  const getStatusColor = (status: ServiceInfo['status']) => {
    switch (status) {
      case 'healthy': return 'green';
      case 'unhealthy': return 'red';
      case 'starting': return 'yellow';
      case 'stopped': return 'gray';
      default: return 'gray';
    }
  };

  const canPerformAction = (service: ServiceInfo, action: string) => {
    if (action === 'start') return service.status === 'stopped';
    if (action === 'stop') return service.status === 'healthy' || service.status === 'unhealthy';
    if (action === 'restart') return service.status !== 'stopped';
    return false;
  };

  const healthyCount = services.filter(s => s.status === 'healthy').length;
  const totalCount = services.length;

  return (
    <Card shadow="sm" p="lg" radius="md" withBorder>
      <Group justify="space-between" mb="md">
        <Text size="lg" fw={600}>
          Platform Services Status
        </Text>
        <Group gap="sm">
          <Badge variant="light" color={healthyCount === totalCount ? 'green' : 'orange'}>
            {healthyCount}/{totalCount} Healthy
          </Badge>
          <ActionIcon
            variant="subtle"
            onClick={refreshServices}
            loading={refreshing}
          >
            <IconRefresh size={16} />
          </ActionIcon>
        </Group>
      </Group>

      <Progress
        value={(healthyCount / totalCount) * 100}
        color={healthyCount === totalCount ? 'green' : 'orange'}
        mb="md"
      />

      <Table striped highlightOnHover>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Service</Table.Th>
            <Table.Th>Status</Table.Th>
            <Table.Th>Type</Table.Th>
            <Table.Th>URL</Table.Th>
            <Table.Th>Actions</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {services.map((service) => (
            <Table.Tr key={service.name}>
              <Table.Td>
                <Stack gap="xs">
                  <Text fw={500} size="sm">{service.name}</Text>
                  <Text size="xs" c="dimmed">{service.description}</Text>
                </Stack>
              </Table.Td>
              <Table.Td>
                <Group gap="xs">
                  {getStatusIcon(service.status)}
                  <Badge size="sm" color={getStatusColor(service.status)}>
                    {service.status}
                  </Badge>
                </Group>
              </Table.Td>
              <Table.Td>
                <Badge size="sm" variant="light" color={service.type === 'docker' ? 'blue' : 'cyan'}>
                  {service.type}
                </Badge>
              </Table.Td>
              <Table.Td>
                <Group gap="xs">
                  <Text size="sm" style={{ fontFamily: 'monospace' }}>
                    {service.url}
                  </Text>
                  {service.status === 'healthy' && service.url.startsWith('http') && (
                    <ActionIcon
                      size="sm"
                      variant="subtle"
                      onClick={() => window.open(service.url, '_blank')}
                    >
                      <IconExternalLink size={12} />
                    </ActionIcon>
                  )}
                </Group>
              </Table.Td>
              <Table.Td>
                <Group gap="xs">
                  <Tooltip label="View Logs">
                    <ActionIcon
                      size="sm"
                      variant="subtle"
                      onClick={() => {
                        setSelectedService(service);
                        setLogsModalOpen(true);
                      }}
                    >
                      <IconTerminal size={14} />
                    </ActionIcon>
                  </Tooltip>

                  {canPerformAction(service, 'start') && (
                    <Tooltip label="Start Service">
                      <ActionIcon
                        size="sm"
                        variant="subtle"
                        color="green"
                        onClick={() => performServiceAction(service, 'start')}
                      >
                        <IconPlayerPlay size={14} />
                      </ActionIcon>
                    </Tooltip>
                  )}

                  {canPerformAction(service, 'stop') && (
                    <Tooltip label="Stop Service">
                      <ActionIcon
                        size="sm"
                        variant="subtle"
                        color="red"
                        onClick={() => performServiceAction(service, 'stop')}
                      >
                        <IconPlayerStop size={14} />
                      </ActionIcon>
                    </Tooltip>
                  )}

                  {canPerformAction(service, 'restart') && (
                    <Tooltip label="Restart Service">
                      <ActionIcon
                        size="sm"
                        variant="subtle"
                        color="orange"
                        onClick={() => performServiceAction(service, 'restart')}
                      >
                        <IconReload size={14} />
                      </ActionIcon>
                    </Tooltip>
                  )}
                </Group>
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>

      {/* Service Logs Modal */}
      <Modal
        opened={logsModalOpen}
        onClose={() => setLogsModalOpen(false)}
        title={`${selectedService?.name} Logs`}
        size="lg"
      >
        <ScrollArea h={400}>
          <Code block>
            {selectedService && `
[${new Date().toISOString()}] INFO Starting ${selectedService.name}...
[${new Date().toISOString()}] INFO Service initialized successfully
[${new Date().toISOString()}] INFO Listening on ${selectedService.url}
[${new Date().toISOString()}] DEBUG Health check passed
[${new Date().toISOString()}] INFO Ready to accept connections
            `.trim()}
          </Code>
        </ScrollArea>
      </Modal>

      {/* Service Action Modal */}
      <Modal
        opened={actionModalOpen}
        onClose={() => setActionModalOpen(false)}
        title={serviceAction ? `${serviceAction.action} ${serviceAction.service}` : ''}
        size="md"
      >
        {serviceAction && (
          <Stack gap="md">
            <Group gap="sm">
              {serviceAction.status === 'running' && <Loader size="sm" />}
              <Text fw={500}>
                {serviceAction.status === 'running' && 'Executing...'}
                {serviceAction.status === 'success' && 'Completed Successfully'}
                {serviceAction.status === 'error' && 'Failed'}
              </Text>
            </Group>

            <Divider />

            <ScrollArea h={200}>
              <Code block>
                {serviceAction.logs.join('\n')}
              </Code>
            </ScrollArea>

            {serviceAction.status !== 'running' && (
              <Button onClick={() => setActionModalOpen(false)}>
                Close
              </Button>
            )}
          </Stack>
        )}
      </Modal>
    </Card>
  );
};

export default ServiceStatusPanel;
