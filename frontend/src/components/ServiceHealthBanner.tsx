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
  // Infra containers
  { key: 'neo4j', labels: ['neo4j'] },
  { key: 'minio', labels: ['minio'] },
  { key: 'loki', labels: ['loki'] },
  { key: 'promtail', labels: ['promtail'] },
  { key: 'redis', labels: ['redis'] },
  { key: 'postgresql', labels: ['postgresql', 'postgres'] },
];

export const ServiceHealthBanner: React.FC = () => {
  const [health, setHealth] = useState<ServiceHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(false);
  const [closed, setClosed] = useState(false);

  const checkServiceHealth = async () => {
    try {
      // Use same base URL convention as api.ts
      const API_BASE = (process.env.REACT_APP_API_URL as string) ||
        (typeof window !== 'undefined' ? `${window.location.protocol}//${window.location.hostname}:8000` : 'http://localhost:8000');
      const resp = await fetch(`${API_BASE}/api/health`, { method: 'GET' } as any);
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
        // If val is an object, prefer val.status
        if (val && typeof val === 'object' && val.status) {
          const s = String(val.status).toLowerCase();
          if (['healthy', 'up', 'present', 'ok', 'connected', 'available'].includes(s)) return 'connected';
          if (s.includes('error') || s.includes('down') || s.includes('failed')) return 'error';
          return 'unknown';
        }
        // If val is a string, use previous logic
        const s = String(val).toLowerCase();
        if (['healthy', 'up', 'present', 'ok', 'connected', 'available'].includes(s)) return 'connected';
        if (s.includes('error') || s.includes('down') || s.includes('failed')) return 'error';
        // Heuristic: treat truthy non-empty values as connected, falsy as error
        if (val !== undefined && val !== null && String(val).trim() !== '') return 'connected';
        return 'error';
      };

      // Map known services first using label aliases
      for (const svc of CANONICAL_SERVICES) {
        let foundVal: any = undefined;
        let foundKey: string | undefined = undefined;
        for (const label of svc.labels) {
          const key = lowerKeyMap[label.toLowerCase()];
          if (key && servicesRaw[key] !== undefined) {
            foundVal = servicesRaw[key];
            foundKey = key;
            break;
          }
        }
        // Special case: treat top-level 'gateway' as 'backend' if present
        if (svc.key === 'backend' && foundVal === undefined) {
          const gw = (data && (data.gateway as any)) as any;
          if (gw !== undefined) {
            // gateway can be a string like 'operational' or an object
            const gwStatus = typeof gw === 'string' ? gw : (gw && gw.status);
            foundVal = { status: String(gwStatus || '').toLowerCase() === 'operational' ? 'healthy' : gwStatus || 'unknown' };
            foundKey = 'gateway';
          }
        }
        // If not found by label, try direct key match
        if (foundVal === undefined && servicesRaw[svc.key] !== undefined) {
          foundVal = servicesRaw[svc.key];
          foundKey = svc.key;
        }
        normalized[svc.key] = foundVal !== undefined ? asSimple(foundVal) : 'unknown';
      }

      // Include any additional services not in canonical list
      Object.entries(servicesRaw).forEach(([name, value]) => {
        const already = CANONICAL_SERVICES.some(s => s.labels.includes(name) || s.key === name);
        if (!already) normalized[name] = asSimple(value);
      });

  // Determine overall health status (ignore unknowns so missing services don't force 'unhealthy')
  const values = Object.values(normalized);
  const considered = values.filter(v => v !== 'unknown');
  const healthyCount = considered.filter((v) => v === 'connected').length;
  const totalCount = considered.length || values.length || CANONICAL_SERVICES.length;

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
    // Check health every 120 seconds
    const interval = setInterval(checkServiceHealth, 120000);
    return () => clearInterval(interval);
  }, []);


  if (closed) return null;
  if (loading) {
    return (
      <Alert
        icon={<Loader size={14} />}
        color="blue"
        style={{ padding: '4px 12px', fontSize: '13px', marginBottom: 0 }}
      >
        Checking system health...
      </Alert>
    );
  }
  if (!health) {
    return null;
  }

  const ServiceDetails = () => {
    // Prepare a list excluding versions/modules
    const items = Object.entries(health.services)
      .filter(([name]) => !name.endsWith('_version') && !name.endsWith('_modules'))
      .map(([name, value]) => {
        const normalized = value === 'connected' ? 'connected' : (value === 'error' ? 'error' : 'unknown');
        return { name, normalized } as { name: string; normalized: 'connected' | 'error' | 'unknown' };
      });

    // Split into 3 columns
    const columns = 3;
    const perCol = Math.ceil(items.length / columns) || 1;
    const cols: typeof items[] = [
      items.slice(0, perCol),
      items.slice(perCol, perCol * 2),
      items.slice(perCol * 2),
    ];

    return (
      <div style={{ marginTop: 6, display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
        {cols.map((col, ci) => (
          <div key={ci}>
            {col.map(({ name, normalized }) => (
              <Group key={name} gap="xs" style={{ marginTop: 2 }}>
                <Badge size="xs" variant="light" color={normalized === 'connected' ? 'green' : normalized === 'error' ? 'red' : 'gray'}>
                  {normalized === 'connected' ? 'OK' : normalized === 'error' ? 'ERR' : 'UNK'}
                </Badge>
                <Text size="xs" c="dimmed">{name.replace('_', '-')}</Text>
              </Group>
            ))}
          </div>
        ))}
      </div>
    );
  };

  const banner = (
  <div style={{ width: '100%', marginBottom: expanded ? 8 : 0 }}>
      <Alert
        icon={health.status === 'healthy' ? <IconCheck size={14} /> : health.status === 'degraded' ? <IconExclamationMark size={14} /> : <IconX size={14} />}
        color={health.status === 'healthy' ? 'green' : health.status === 'degraded' ? 'orange' : 'red'}
        style={{ padding: '4px 12px', fontSize: '13px', position: 'relative', marginBottom: 0 }}
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
            <ActionIcon variant="subtle" onClick={() => setClosed(true)} title="Close banner">
              <IconX size={14} />
            </ActionIcon>
          </Group>
        </Group>
        <Collapse in={expanded}>
          <div style={{
            backgroundColor: 'white',
            border: '1px solid #e1e5e9',
            borderTop: 'none',
            borderRadius: '0 0 8px 8px',
            boxShadow: '0 8px 24px rgba(0,0,0,0.08)',
            maxWidth: '100vw',
            minHeight: 120,
            padding: '8px 16px',
          }}>
            <ServiceDetails />
          </div>
        </Collapse>
      </Alert>
    </div>
  );

  return banner;
};
