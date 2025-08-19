import React, { useState, useEffect } from 'react';
import { Alert, Loader, Group, ActionIcon, Collapse, Badge, Text } from '@mantine/core';
import { IconCheck, IconExclamationMark, IconX, IconRefresh } from '@tabler/icons-react';

interface ServiceHealth {
  status: 'healthy' | 'degraded' | 'unhealthy';
  services: Record<string, string>;
}

// Canonical platform service keys in display order
const CANONICAL_SERVICES: { key: string; labels: string[] }[] = [
  { key: 'backend', labels: ['backend', 'api', 'gateway', 'api-gateway'] },
  { key: 'project', labels: ['project', 'project_service', 'project-service'] },
  { key: 'reporting', labels: ['reporting', 'reporting_service', 'reporting-service'] },
  { key: 'document', labels: ['document', 'document_service', 'document-service'] },
  { key: 'vector', labels: ['vector', 'vector_service', 'vector-service'] },
  { key: 'graph', labels: ['graph', 'graph_service', 'graph-service'] },
  { key: 'llm', labels: ['llm', 'llm_service', 'llm-service'] },
  { key: 'ai_agent', labels: ['ai_agent', 'ai-agent', 'ai_agent_service', 'ai-agent-service'] },
  { key: 'websocket', labels: ['websocket', 'websocket_service', 'websocket-service'] },
  { key: 'storage', labels: ['storage', 'storage_service', 'storage-service'] },
];

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
      const servicesRaw = (data.services as Record<string, any>) || {};
      // Normalize to canonical keys with simple connected/error/unknown statuses
      const normalized: Record<string, string> = {};
      const lowerKeyMap: Record<string, string> = {};
      Object.keys(servicesRaw).forEach((k) => (lowerKeyMap[k.toLowerCase()] = k));

      const asSimple = (val: any) => {
        const v = typeof val === 'string' ? val : (val?.status || val?.state || 'unknown');
        const s = String(v).toLowerCase();
        if (['healthy', 'up', 'present', 'ok', 'connected', 'available'].includes(s)) return 'connected';
        if (s.includes('error') || s.includes('down') || s.includes('failed')) return 'error';
        return 'unknown';
      };

      // Map known services first using label aliases
      for (const svc of CANONICAL_SERVICES) {
        let foundVal: any = undefined;
        for (const label of svc.labels) {
          const key = lowerKeyMap[label.toLowerCase()];
          if (key && servicesRaw[key] !== undefined) {
            foundVal = servicesRaw[key];
            break;
          }
        }
        normalized[svc.key] = asSimple(foundVal);
      }

      // Include any additional services not in canonical list
      Object.entries(servicesRaw).forEach(([name, value]) => {
        const already = CANONICAL_SERVICES.some(s => s.labels.includes(name) || s.key === name);
        if (!already) normalized[name] = asSimple(value);
      });

      // Determine overall health status
  const values = Object.values(normalized);
  const healthyCount = values.filter((v) => v === 'connected').length;
  const totalCount = values.length || CANONICAL_SERVICES.length;

      let status: ServiceHealth['status'];
      if (healthyCount === totalCount) {
        status = 'healthy';
      } else if (healthyCount >= Math.ceil(totalCount / 2)) {
        status = 'degraded';
      } else {
        status = 'unhealthy';
      }
  setHealth({ status, services: normalized });
    } catch (error) {
      console.error('Health check failed:', error);
  const fallback: Record<string, string> = {};
  for (const svc of CANONICAL_SERVICES) fallback[svc.key] = 'error';
  setHealth({ status: 'unhealthy', services: fallback });
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
      <Text size="xs" c="dimmed">{name.replace('_', '-')}</Text>
            </Group>
          );
        })}
    </div>
  );

  const banner = (
    <Alert
      icon={health.status === 'healthy' ? <IconCheck size={14} /> : health.status === 'degraded' ? <IconExclamationMark size={14} /> : <IconX size={14} />}
      color={health.status === 'healthy' ? 'green' : health.status === 'degraded' ? 'orange' : 'red'}
      style={{ 
        padding: '4px 12px', 
        fontSize: '13px',
        position: 'relative',
        zIndex: 1001
      }}
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
          <div style={{
            position: 'fixed',
            top: 63, // header height
            left: 0,
            right: 0,
            backgroundColor: 'white',
            border: '1px solid #e1e5e9',
            borderTop: 'none',
            borderRadius: '0 0 8px 8px',
            zIndex: 2000,
            boxShadow: '0 8px 24px rgba(0,0,0,0.18)',
            maxWidth: '100vw',
            minHeight: 120,
            padding: '16px 32px',
          }}>
            <ServiceDetails />
          </div>
      </Collapse>
    </Alert>
  );

  return banner;
};
