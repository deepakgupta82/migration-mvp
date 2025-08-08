import React, { useState, useEffect } from 'react';
import { Alert, Loader, Group, ActionIcon, Collapse, Badge, Text } from '@mantine/core';
import { IconCheck, IconExclamationMark, IconX, IconRefresh } from '@tabler/icons-react';

interface ServiceHealth {
  status: 'healthy' | 'degraded' | 'unhealthy';
  services: Record<string, string>;
}

export const ServiceHealthBanner: React.FC = () => {
  const [health, setHealth] = useState<ServiceHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(false);

  const checkServiceHealth = async () => {
    try {
      const resp = await fetch('http://localhost:8000/health', { method: 'GET' } as any);
      if (!resp.ok) {
        throw new Error(`Backend health endpoint returned ${resp.status}`);
      }
      const data = await resp.json();
      const services = data.services as Record<string, string>;

      // Determine overall health status
      const values = Object.values(services);
      const healthyCount = values.filter((v) => v === 'connected').length;
      const totalCount = values.length;

      let status: ServiceHealth['status'];
      if (healthyCount === totalCount) {
        status = 'healthy';
      } else if (healthyCount >= Math.ceil(totalCount / 2)) {
        status = 'degraded';
      } else {
        status = 'unhealthy';
      }

      setHealth({ status, services });
    } catch (error) {
      console.error('Health check failed:', error);
      setHealth({
        status: 'unhealthy',
        services: {
          backend: 'error',
          project_service: 'error',
          reporting_service: 'error',
        }
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    checkServiceHealth();
    // Check health every 30 seconds
    const interval = setInterval(checkServiceHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <Alert
        icon={<Loader size={18} />}
        color="blue"
        style={{ padding: '8px 16px', fontSize: '14px' }}
      >
        Checking system health...
      </Alert>
    );
  }

  if (!health) {
    return null;
  }

  const ServiceDetails = () => (
    <div style={{ marginTop: 8 }}>
      {Object.entries(health.services).map(([name, value]) => {
        const isInfoOnly = name === 'weaviate_version' || name === 'weaviate_modules';
        return (
          <Group key={name} gap="xs" style={{ marginTop: 4 }}>
            {!isInfoOnly && (
              <Badge size="xs" variant="light" color={value === 'connected' ? 'green' : 'red'}>
                {value === 'connected' ? 'OK' : 'ERR'}
              </Badge>
            )}
            <Text size="xs" c="dimmed">{name}</Text>
            <Text size="xs" c={isInfoOnly ? 'dimmed' : (value === 'connected' ? 'green' : 'red')}>
              {typeof value === 'string' ? value : JSON.stringify(value)}
            </Text>
          </Group>
        );
      })}
    </div>
  );

  const banner = (
    <Alert
      icon={health.status === 'healthy' ? <IconCheck size={18} /> : health.status === 'degraded' ? <IconExclamationMark size={18} /> : <IconX size={18} />}
      color={health.status === 'healthy' ? 'green' : health.status === 'degraded' ? 'orange' : 'red'}
      style={{ padding: '8px 16px', fontSize: '14px' }}
    >
      <Group justify="space-between">
        <Text size="sm">
          {health.status === 'healthy' && 'All systems are running smoothly.'}
          {health.status === 'degraded' && 'Some services are experiencing issues. Performance may be degraded.'}
          {health.status === 'unhealthy' && 'Critical system issues detected. Multiple services are unavailable.'}
        </Text>
        <Group gap="xs">
          <ActionIcon variant="subtle" onClick={() => checkServiceHealth()} title="Refresh all service statuses">
            <IconRefresh size={16} />
          </ActionIcon>
          <ActionIcon variant="subtle" onClick={() => setExpanded((e) => !e)} title="Details">
            {expanded ? '−' : '+'}
          </ActionIcon>
        </Group>
      </Group>
      <Collapse in={expanded}>
        <ServiceDetails />
      </Collapse>
    </Alert>
  );

  return banner;
};
still large number of errors in 