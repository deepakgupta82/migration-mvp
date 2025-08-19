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
      const resp = await fetch('/api/health', { method: 'GET' } as any);
      if (!resp.ok) {
        throw new Error(`Backend health endpoint returned ${resp.status}`);
      }
      const data = await resp.json();
      const servicesRaw = data.services as Record<string, any>;
      // Normalize backend payload into name -> connected/error
      const services: Record<string, string> = {};
      Object.entries(servicesRaw || {}).forEach(([name, value]) => {
        const v = typeof value === 'string' ? value : (value?.status || value?.state || 'unknown');
        const norm = ['healthy', 'up', 'present', 'ok', 'connected'].includes(String(v).toLowerCase()) ? 'connected' : (String(v).toLowerCase().includes('error') ? 'error' : 'unknown');
        services[name] = norm;
      });

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
        icon={<Loader size={14} />}
        color="blue"
        style={{ padding: '4px 12px', fontSize: '13px' }}
      >
        Checking system health...
      </Alert>
    );
  }

  if (!health) {
    return null;
  }

  const ServiceDetails = () => (
    <div style={{ marginTop: 6 }}>
      {Object.entries(health.services)
        // Filter out version/module details from display
        .filter(([name]) => !name.endsWith('_version') && !name.endsWith('_modules'))
        .map(([name, value]) => {
          // Normalize value to simple status
          const normalized = value === 'connected' ? 'connected' : (value === 'error' ? 'error' : 'unknown');
          return (
            <Group key={name} gap="xs" style={{ marginTop: 2 }}>
              <Badge size="xs" variant="light" color={normalized === 'connected' ? 'green' : normalized === 'error' ? 'red' : 'gray'}>
                {normalized === 'connected' ? 'OK' : normalized === 'error' ? 'ERR' : 'UNK'}
              </Badge>
              <Text size="xs" c="dimmed">{name}</Text>
            </Group>
          );
        })}
    </div>
  );

  const banner = (
    <Alert
      icon={health.status === 'healthy' ? <IconCheck size={14} /> : health.status === 'degraded' ? <IconExclamationMark size={14} /> : <IconX size={14} />}
      color={health.status === 'healthy' ? 'green' : health.status === 'degraded' ? 'orange' : 'red'}
      style={{ padding: '4px 12px', fontSize: '13px' }}
    >
      <Group justify="space-between">
        <Text size="xs">
          {health.status === 'healthy' && 'All systems are running smoothly.'}
          {health.status === 'degraded' && 'Some services are experiencing issues. Performance may be degraded.'}
          {health.status === 'unhealthy' && 'Critical system issues detected. Multiple services are unavailable.'}
        </Text>
        <Group gap="xs">
          <ActionIcon variant="subtle" onClick={() => checkServiceHealth()} title="Refresh all service statuses">
            <IconRefresh size={14} />
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
