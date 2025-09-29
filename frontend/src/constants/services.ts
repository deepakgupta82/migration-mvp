// Centralized classification of services for UI filtering

export const INFRA_CONTAINER_KEYS = new Set<string>([
  'neo4j', 'minio', 'loki', 'promtail', 'redis', 'postgresql', 'weaviate'
]);

// Include canonical app service keys and common aliases used in health maps
const APPLICATION_ALIASES: string[] = [
  'backend',
  'project', 'project_service', 'project-service',
  'document', 'document_service', 'document-service',
  'vector', 'vector_service', 'vector-service',
  'graph', 'graph_service', 'graph-service',
  'llm', 'llm_service', 'llm-service',
  'ai_agent', 'ai_agent_service', 'ai-agent-service',
  'websocket', 'websocket_service', 'websocket-service',
  'storage', 'storage_service', 'storage-service',
  'service_registry', 'service-registry',
  'cloud_tools', 'cloud_tools_service', 'cloud-tools-service',
  'analytics', 'analytics_service', 'analytics-service',
  'security', 'security_service', 'security-service',
  'collaboration', 'collaboration_service', 'collaboration-service',
  'knowledge', 'knowledge_service', 'knowledge-service',
  'aws_data', 'aws_data_service', 'aws-data-service',
  'data_importer', 'data_importer_service', 'data-importer-service'
];

export const APPLICATION_SERVICE_KEYS = new Set<string>(APPLICATION_ALIASES);

export const normalizeKey = (name: string) => (name || '').toLowerCase();

export const isInfraContainer = (name: string) => INFRA_CONTAINER_KEYS.has(normalizeKey(name));

export const isApplicationService = (name: string) => APPLICATION_SERVICE_KEYS.has(normalizeKey(name));

// Polling interval helpers (enforce minimum 60s)
const parseMs = (val: string | undefined, fallbackMs: number) => {
  const n = Number(val);
  return Number.isFinite(n) && n > 0 ? n : fallbackMs;
};

export const HEALTH_POLL_INTERVAL_MS = Math.max(
  60000,
  parseMs(process.env.REACT_APP_HEALTH_POLL_INTERVAL_MS as any, 60000)
);

export const CONTAINERS_POLL_INTERVAL_MS = Math.max(
  60000,
  parseMs(process.env.REACT_APP_CONTAINERS_POLL_INTERVAL_MS as any, 60000)
);
