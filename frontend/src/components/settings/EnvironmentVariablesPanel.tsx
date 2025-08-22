import React, { useState, useEffect } from 'react';
import {
  Card,
  Text,
  Group,
  Stack,
  TextInput,
  Button,
  Accordion,
  Badge,
  ActionIcon,
  Modal,
  Textarea,
  Select,
  Switch,
  Alert,
  Divider,
  Code,
  Tooltip,
  Box,
  Collapse,
  Paper,
} from '@mantine/core';
import {
  IconSearch,
  IconEdit,
  IconTrash,
  IconPlus,
  IconEye,
  IconEyeOff,
  IconInfoCircle,
  IconDatabase,
  IconCloud,
  IconRobot,
  IconServer,
  IconKey,
  IconSettings,
  IconRefresh,
  IconDownload,
  IconUpload,
} from '@tabler/icons-react';

interface EnvironmentVariable {
  key: string;
  value: string;
  description: string;
  category: string;
  type: 'string' | 'number' | 'boolean' | 'password' | 'url' | 'json';
  required: boolean;
  sensitive: boolean;
  defaultValue?: string;
  validation?: string;
  example?: string;
  restartRequired?: boolean;
}

interface EnvironmentCategory {
  name: string;
  icon: React.ReactNode;
  description: string;
  variables: EnvironmentVariable[];
}

import { API_BASE_URL } from '../../services/api';

export const EnvironmentVariablesPanel: React.FC = () => {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [selectedVariable, setSelectedVariable] = useState<EnvironmentVariable | null>(null);
  const [showSensitive, setShowSensitive] = useState<Record<string, boolean>>({});
  const [expandedCategories, setExpandedCategories] = useState<string[]>(['database', 'llm']);
  const [showRestartNotice, setShowRestartNotice] = useState<boolean>(false);
  const CONFIG_URL = `${API_BASE_URL}/config/config.local.json`;
  
  // Bindings map from UI keys to config.local.json paths and metadata
  type Binding = {
    key: string;
    path: string[]; // nested path in config
    category: string;
    description: string;
    type: EnvironmentVariable['type'];
    required?: boolean;
    sensitive?: boolean;
    defaultValue?: string;
    example?: string;
  restartRequired?: boolean;
  };

  const BINDINGS: Binding[] = [
    // Backend (API Gateway)
    { key: 'BACKEND_STATS_REFRESH_INTERVAL_SEC', path: ['backend','stats_refresh_interval_sec'], category: 'services', description: 'Backend periodic stats refresh interval in seconds', type: 'number', defaultValue: '300', example: '60, 300, 600' },
    { key: 'DISABLE_WS_AUTH', path: ['backend','disable_ws_auth'], category: 'services', description: 'Disable WebSocket auth (1=yes, 0=no) for local debugging', type: 'boolean', defaultValue: '0' },
    { key: 'SERVICE_AUTH_TOKEN', path: ['backend','service_auth_token'], category: 'security', description: 'Legacy service-to-service token', type: 'password', defaultValue: 'service-backend-token', sensitive: true },
  { key: 'PORT', path: ['backend','port'], category: 'services', description: 'Backend service port', type: 'number', defaultValue: '8000', restartRequired: true },
  { key: 'WARMUP_STATS_CONCURRENCY', path: ['backend','warmup_stats_concurrency'], category: 'services', description: 'Concurrency for startup stats warmup', type: 'number', defaultValue: '6', restartRequired: true },
  { key: 'WARMUP_STATS_LIMIT', path: ['backend','warmup_stats_limit'], category: 'services', description: 'Max projects to warm on startup', type: 'number', defaultValue: '50', restartRequired: true },
  { key: 'CORS_ORIGINS', path: ['backend','cors_origins'], category: 'services', description: 'Allowed CORS origins (comma-separated)', type: 'string', defaultValue: 'http://localhost:3000', restartRequired: true },

    // Project Service
  { key: 'DATABASE_URL', path: ['project_service','database_url'], category: 'database', description: 'Primary Postgres URL for Project Service', type: 'url', required: true, sensitive: true, example: 'postgresql://user:password@host:5432/db', restartRequired: true },
  { key: 'SECRET_KEY', path: ['project_service','secret_key'], category: 'security', description: 'Fallback secret used by auth', type: 'password', sensitive: true, restartRequired: true },
  { key: 'JWT_SECRET_KEY', path: ['project_service','jwt_secret_key'], category: 'security', description: 'JWT signing secret key', type: 'password', sensitive: true, restartRequired: true },
  { key: 'JWT_ALGORITHM', path: ['project_service','jwt_algorithm'], category: 'security', description: 'JWT signing algorithm', type: 'string', defaultValue: 'HS256', restartRequired: true },
  { key: 'JWT_ACCESS_TOKEN_EXPIRE_MINUTES', path: ['project_service','jwt_access_token_expire_minutes'], category: 'security', description: 'JWT access token expiry (minutes)', type: 'number', defaultValue: '30', restartRequired: true },
  { key: 'JWT_REFRESH_TOKEN_EXPIRE_DAYS', path: ['project_service','jwt_refresh_token_expire_days'], category: 'security', description: 'JWT refresh token expiry (days)', type: 'number', defaultValue: '7', restartRequired: true },
  { key: 'JWT_SERVICE_TOKEN_EXPIRE_HOURS', path: ['project_service','jwt_service_token_expire_hours'], category: 'security', description: 'Service token expiry (hours)', type: 'number', defaultValue: '24', restartRequired: true },
    { key: 'PROJECT_SERVICE_SERVICE_AUTH_TOKEN', path: ['project_service','service_auth_token'], category: 'security', description: 'Project service legacy service token', type: 'password', sensitive: true, defaultValue: 'service-backend-token' },

    // Document Service
  { key: 'CHUNKING_STRATEGY', path: ['document_service','chunking_strategy'], category: 'services', description: 'Document chunking strategy (semantic | paragraph | rule_based)', type: 'string', defaultValue: 'semantic' },
  { key: 'CHUNK_METHOD', path: ['document_service','chunking_strategy'], category: 'services', description: 'Alias: semantic | paragraph | words', type: 'string', defaultValue: 'semantic' },
    { key: 'SEMANTIC_MAX_CHUNK', path: ['document_service','semantic_max_chunk'], category: 'services', description: 'Max semantic chunk size', type: 'number', defaultValue: '2000' },
    { key: 'SEMANTIC_OVERLAP', path: ['document_service','semantic_overlap'], category: 'services', description: 'Chunk overlap', type: 'number', defaultValue: '200' },
    { key: 'SEMANTIC_MODEL', path: ['document_service','semantic_model'], category: 'services', description: 'Embedding model', type: 'string', defaultValue: 'all-MiniLM-L6-v2' },
    { key: 'ENABLE_LLM_ENRICHMENT', path: ['document_service','enable_llm_enrichment'], category: 'services', description: 'Enable enrichment using LLM', type: 'boolean', defaultValue: 'false' },
    { key: 'DOCUMENT_SERVICE_SERVICE_AUTH_TOKEN', path: ['document_service','service_auth_token'], category: 'security', description: 'Document service legacy token', type: 'password', sensitive: true, defaultValue: 'service-backend-token' },
  { key: 'DOCUMENT_HTTP_TIMEOUT_SEC', path: ['document_service','http_timeout_sec'], category: 'services', description: 'HTTP timeout for storage/vector/graph calls (seconds)', type: 'number', defaultValue: '30' },
  { key: 'SEMANTIC_WORDS_PER_CHUNK', path: ['document_service','semantic_words_per_chunk'], category: 'services', description: 'Words per chunk when CHUNKING_STRATEGY=words', type: 'number', defaultValue: '300' },
  { key: 'SEMANTIC_WORDS_OVERLAP', path: ['document_service','semantic_words_overlap'], category: 'services', description: 'Overlap (words) between chunks for words strategy', type: 'number', defaultValue: '50' },

    // Vector Service
  { key: 'CHROMA_DB_PATH', path: ['vector_service','chroma_db_path'], category: 'services', description: 'Chroma DB path', type: 'string', defaultValue: '../../data/chroma_db', restartRequired: true },
    { key: 'DEBUG_VECTOR_LOGS', path: ['vector_service','debug_vector_logs'], category: 'services', description: 'Enable verbose vector logs', type: 'boolean', defaultValue: 'false' },
  { key: 'VECTOR_ADD_TIMEOUT_SEC', path: ['vector_service','add_timeout_sec'], category: 'services', description: 'Timeout for Chroma add operations (seconds)', type: 'number', defaultValue: '60' },
  { key: 'VECTOR_ADD_MAX_RETRIES', path: ['vector_service','add_max_retries'], category: 'services', description: 'Max retries for add_documents on timeout', type: 'number', defaultValue: '3' },
  { key: 'VECTOR_ADD_INITIAL_BACKOFF_SEC', path: ['vector_service','add_initial_backoff_sec'], category: 'services', description: 'Initial backoff between retries (seconds)', type: 'number', defaultValue: '1.0' },
  { key: 'VECTOR_ADD_MAX_BACKOFF_SEC', path: ['vector_service','add_max_backoff_sec'], category: 'services', description: 'Max backoff between retries (seconds)', type: 'number', defaultValue: '10.0' },
  { key: 'VECTOR_EMBED_BATCH_SIZE', path: ['vector_service','embed_batch_size'], category: 'services', description: 'Batch size for embedding generation', type: 'number', defaultValue: '32' },
  { key: 'VECTOR_CHROMA_BATCH_SIZE', path: ['vector_service','chroma_batch_size'], category: 'services', description: 'Batch size for Chroma add operations', type: 'number', defaultValue: '128' },
    { key: 'VECTOR_ADD_TIMEOUT_SEC', path: ['vector_service','add_timeout_sec'], category: 'services', description: 'Timeout (seconds) for vector add_documents', type: 'number', defaultValue: '60' },
    { key: 'VECTOR_ADD_MAX_RETRIES', path: ['vector_service','add_max_retries'], category: 'services', description: 'Max retries for transient add_documents failures', type: 'number', defaultValue: '3' },
    { key: 'VECTOR_ADD_INITIAL_BACKOFF_SEC', path: ['vector_service','add_initial_backoff_sec'], category: 'services', description: 'Initial backoff (seconds) between retries', type: 'number', defaultValue: '1.0' },
    { key: 'VECTOR_ADD_MAX_BACKOFF_SEC', path: ['vector_service','add_max_backoff_sec'], category: 'services', description: 'Max backoff (seconds) between retries', type: 'number', defaultValue: '10.0' },
    { key: 'VECTOR_EMBED_BATCH_SIZE', path: ['vector_service','embed_batch_size'], category: 'services', description: 'Embedding batch size', type: 'number', defaultValue: '32' },
    { key: 'VECTOR_CHROMA_BATCH_SIZE', path: ['vector_service','chroma_batch_size'], category: 'services', description: 'Chroma add batch size', type: 'number', defaultValue: '128' },

    // Graph Service
  { key: 'NEO4J_URI', path: ['graph_service','neo4j_uri'], category: 'database', description: 'Neo4j URI', type: 'url', example: 'bolt://localhost:7687', restartRequired: true },
  { key: 'NEO4J_USER', path: ['graph_service','neo4j_user'], category: 'database', description: 'Neo4j username', type: 'string', defaultValue: 'neo4j', restartRequired: true },
  { key: 'NEO4J_PASSWORD', path: ['graph_service','neo4j_password'], category: 'database', description: 'Neo4j password', type: 'password', sensitive: true, defaultValue: 'password', restartRequired: true },
  { key: 'REDIS_HOST', path: ['graph_service','redis_host'], category: 'database', description: 'Redis host', type: 'string', defaultValue: 'localhost', restartRequired: true },
  { key: 'REDIS_PORT', path: ['graph_service','redis_port'], category: 'database', description: 'Redis port', type: 'number', defaultValue: '6379', restartRequired: true },
  { key: 'REDIS_DB', path: ['graph_service','redis_db'], category: 'database', description: 'Redis DB index', type: 'number', defaultValue: '5', restartRequired: true },
    { key: 'GRAPH_LLM_SERVICE_URL', path: ['graph_service','llm_service_url'], category: 'services', description: 'LLM service URL for Graph', type: 'url', defaultValue: 'http://localhost:8007' },
  { key: 'DEBUG_GRAPH_ENTITY_LOGS', path: ['graph_service','debug_entity_logs'], category: 'services', description: 'Enable detailed entity and relationship debug logs in graph-service', type: 'boolean', defaultValue: 'false', restartRequired: true },
    { key: 'GRAPH_SERVICE_AUTH_TOKEN', path: ['graph_service','service_auth_token'], category: 'security', description: 'Graph service legacy token', type: 'password', sensitive: true, defaultValue: 'service-backend-token' },

    // LLM Service
    { key: 'OPENAI_API_KEY', path: ['llm_service','openai_api_key'], category: 'llm', description: 'OpenAI API key', type: 'password', sensitive: true },
    { key: 'ANTHROPIC_API_KEY', path: ['llm_service','anthropic_api_key'], category: 'llm', description: 'Anthropic API key', type: 'password', sensitive: true },
    { key: 'AZURE_OPENAI_ENDPOINT', path: ['llm_service','azure_openai_endpoint'], category: 'llm', description: 'Azure OpenAI endpoint', type: 'url' },
    { key: 'AZURE_OPENAI_API_KEY', path: ['llm_service','azure_openai_api_key'], category: 'llm', description: 'Azure OpenAI API key', type: 'password', sensitive: true },
    { key: 'DEBUG_LLM_LOGS', path: ['llm_service','debug_llm_logs'], category: 'llm', description: 'Enable LLM debug logs', type: 'boolean', defaultValue: 'false' },
    { key: 'LLM_SERVICE_AUTH_TOKEN', path: ['llm_service','service_auth_token'], category: 'security', description: 'LLM service legacy token', type: 'password', sensitive: true, defaultValue: 'service-backend-token' },

    // AI Agent Service
    { key: 'PROJECT_SERVICE_URL', path: ['ai_agent_service','project_service_url'], category: 'services', description: 'Project service URL', type: 'url', defaultValue: 'http://localhost:8002' },
    { key: 'VECTOR_SERVICE_URL', path: ['ai_agent_service','vector_service_url'], category: 'services', description: 'Vector service URL', type: 'url', defaultValue: 'http://localhost:8005' },
    { key: 'LLM_SERVICE_URL', path: ['ai_agent_service','llm_service_url'], category: 'services', description: 'LLM service URL', type: 'url', defaultValue: 'http://localhost:8007' },
    { key: 'STORAGE_SERVICE_URL', path: ['ai_agent_service','storage_service_url'], category: 'services', description: 'Storage service URL', type: 'url', defaultValue: 'http://localhost:8010' },
    { key: 'REPORTING_SERVICE_URL', path: ['ai_agent_service','reporting_service_url'], category: 'services', description: 'Reporting service URL', type: 'url', defaultValue: 'http://localhost:8003' },
    { key: 'AI_AGENT_SERVICE_AUTH_TOKEN', path: ['ai_agent_service','service_auth_token'], category: 'security', description: 'AI agent service legacy token', type: 'password', sensitive: true, defaultValue: 'service-backend-token' },

    // Storage Service
  { key: 'STORAGE_PROVIDER', path: ['storage_service','storage_provider'], category: 'storage', description: 'Object storage provider', type: 'string', defaultValue: 'minio', restartRequired: true },
  { key: 'STORAGE_BUCKET', path: ['storage_service','storage_bucket'], category: 'storage', description: 'Default storage bucket', type: 'string', defaultValue: 'agentimigrate', restartRequired: true },
  { key: 'STORAGE_ENDPOINT', path: ['storage_service','storage_endpoint'], category: 'storage', description: 'Storage endpoint', type: 'string', defaultValue: 'localhost:9000', restartRequired: true },
  { key: 'STORAGE_ACCESS_KEY', path: ['storage_service','storage_access_key'], category: 'storage', description: 'Storage access key', type: 'string', sensitive: true, defaultValue: 'minioadmin', restartRequired: true },
  { key: 'STORAGE_SECRET_KEY', path: ['storage_service','storage_secret_key'], category: 'storage', description: 'Storage secret key', type: 'password', sensitive: true, defaultValue: 'minioadmin', restartRequired: true },
  { key: 'STORAGE_SECURE', path: ['storage_service','storage_secure'], category: 'storage', description: 'Use TLS for storage', type: 'boolean', defaultValue: 'false', restartRequired: true },
  { key: 'UPLOAD_ROOT_TMP', path: ['storage_service','upload_root_tmp'], category: 'storage', description: 'Local temporary upload root', type: 'string', restartRequired: true },

    // Reporting Service
  { key: 'REPORTING_DATABASE_URL', path: ['reporting_service','database_url'], category: 'database', description: 'Reporting service DB URL', type: 'url', sensitive: true, restartRequired: true },
    { key: 'REPORTING_PROJECT_SERVICE_URL', path: ['reporting_service','project_service_url'], category: 'services', description: 'Project service URL', type: 'url', defaultValue: 'http://localhost:8002' },
    { key: 'OBJECT_STORAGE_ENDPOINT', path: ['reporting_service','object_storage_endpoint'], category: 'storage', description: 'Object storage endpoint', type: 'string', defaultValue: 'localhost:9000' },
    { key: 'OBJECT_STORAGE_ACCESS_KEY', path: ['reporting_service','object_storage_access_key'], category: 'storage', description: 'Object storage access key', type: 'string', sensitive: true, defaultValue: 'minioadmin' },
    { key: 'OBJECT_STORAGE_SECRET_KEY', path: ['reporting_service','object_storage_secret_key'], category: 'storage', description: 'Object storage secret key', type: 'password', sensitive: true, defaultValue: 'minioadmin' },
    { key: 'BACKEND_SERVICE_URL', path: ['reporting_service','backend_service_url'], category: 'services', description: 'Backend service URL', type: 'url', defaultValue: 'http://localhost:8000' },
    { key: 'REPORTING_SERVICE_AUTH_TOKEN', path: ['reporting_service','service_auth_token'], category: 'security', description: 'Reporting service legacy token', type: 'password', sensitive: true, defaultValue: 'service-backend-token' },

    // Frontend
  { key: 'REACT_APP_API_URL', path: ['frontend','react_app_api_url'], category: 'services', description: 'Frontend API base URL override', type: 'url', restartRequired: true },

    // Shared/Other
    { key: 'WEAVIATE_URL', path: ['shared','weaviate_url'], category: 'services', description: 'Weaviate endpoint', type: 'url', defaultValue: 'http://localhost:8080' },
    { key: 'MINIO_ENDPOINT', path: ['shared','minio_endpoint'], category: 'storage', description: 'MinIO endpoint (shared)', type: 'string', defaultValue: 'localhost:9000' },
    { key: 'MINIO_ACCESS_KEY', path: ['shared','minio_access_key'], category: 'storage', description: 'MinIO access key (shared)', type: 'string', sensitive: true, defaultValue: 'minioadmin' },
    { key: 'MINIO_SECRET_KEY', path: ['shared','minio_secret_key'], category: 'storage', description: 'MinIO secret key (shared)', type: 'password', sensitive: true, defaultValue: 'minioadmin' },
    { key: 'MINIO_BUCKET_NAME', path: ['shared','minio_bucket_name'], category: 'storage', description: 'MinIO bucket (shared)', type: 'string', defaultValue: 'agentimigrate' },
  ];

  const [environmentCategories, setEnvironmentCategories] = useState<EnvironmentCategory[]>([]);

  // Build categories from bindings + config
  const buildCategories = (cfg: any): EnvironmentCategory[] => {
    const catMap: Record<string, EnvironmentCategory> = {};
    const ensure = (name: string, icon: React.ReactNode, description: string) => {
      if (!catMap[name]) {
        catMap[name] = { name, icon, description, variables: [] };
      }
      return catMap[name];
    };

    const iconFor = (category: string) => {
      if (category === 'database') return <IconDatabase size={16} />;
      if (category === 'llm') return <IconRobot size={16} />;
      if (category === 'storage') return <IconCloud size={16} />;
      if (category === 'security') return <IconKey size={16} />;
      return <IconServer size={16} />;
    };

    // Group by high-level buckets for display
    const bucketDesc: Record<string, string> = {
      database: 'Database connection and configuration settings',
      llm: 'Large Language Model and AI service settings',
      storage: 'Object storage and file management settings',
      services: 'Core application and service configuration',
      security: 'Security, authentication, and encryption settings',
    };

    const getValueFromPath = (obj: any, path: string[]) => {
      return path.reduce((acc, k) => (acc && acc[k] !== undefined ? acc[k] : undefined), obj);
    };

    BINDINGS.forEach(b => {
      const rawVal = getValueFromPath(cfg, b.path);
      let value: string = '';
      if (rawVal === undefined || rawVal === null) {
        value = b.defaultValue ?? '';
      } else if (Array.isArray(rawVal)) {
        value = rawVal.join(',');
      } else {
        value = String(rawVal);
      }
      const bucket = ensure(b.category, iconFor(b.category), bucketDesc[b.category] || '');
      bucket.variables.push({
        key: b.key,
        value,
        description: b.description,
        category: b.category,
        type: b.type,
        required: !!b.required,
        sensitive: !!b.sensitive,
        defaultValue: b.defaultValue,
        example: b.example,
  restartRequired: !!b.restartRequired,
      });
    });

    return Object.values(catMap);
  };

  // Load config and build UI variables for all bindings
  useEffect(() => {
    const loadConfig = async () => {
      try {
        const res = await fetch(CONFIG_URL);
        const cfg = res.ok ? await res.json() : {};
        setEnvironmentCategories(buildCategories(cfg));
      } catch {
        // ignore if backend config not reachable
      }
    };
    loadConfig();
  }, []);

  const toggleSensitive = (key: string) => {
    setShowSensitive(prev => ({
      ...prev,
      [key]: !prev[key],
    }));
  };

  const handleEditVariable = (variable: EnvironmentVariable) => {
    setSelectedVariable(variable);
    setEditModalOpen(true);
  };

  const handleSaveVariable = () => {
    if (!selectedVariable) return;
    const doLocalUpdate = () => {
      setEnvironmentCategories(prev =>
        prev.map(category => ({
          ...category,
          variables: category.variables.map(variable =>
            variable.key === selectedVariable.key ? selectedVariable : variable
          ),
        }))
      );
      setEditModalOpen(false);
      setSelectedVariable(null);
    };

    // Persist to backend config at the mapped path
    (async () => {
      try {
        const binding = BINDINGS.find(b => b.key === selectedVariable.key);
        if (!binding) {
          doLocalUpdate();
          return;
        }
        const res = await fetch(CONFIG_URL);
        let cfg: any = {};
        if (res.ok) cfg = await res.json();
        // Ensure nested structure
        let ptr = cfg;
        for (let i = 0; i < binding.path.length - 1; i++) {
          const k = binding.path[i];
          ptr[k] = ptr[k] || {};
          ptr = ptr[k];
        }
        const leafKey = binding.path[binding.path.length - 1];
        // Parse value by type
        let parsed: any = selectedVariable.value;
        if (binding.type === 'number') parsed = Number(selectedVariable.value);
        if (binding.type === 'boolean') parsed = (String(selectedVariable.value).toLowerCase() === 'true' || selectedVariable.value === '1');
        if (binding.key === 'CORS_ORIGINS') {
          parsed = selectedVariable.value.split(',').map(s => s.trim()).filter(Boolean);
        }
        ptr[leafKey] = parsed;
        await fetch(CONFIG_URL, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(cfg),
        });
        // If this variable requires restart, surface a UI notice
        if (binding.restartRequired) {
          setShowRestartNotice(true);
          setTimeout(() => setShowRestartNotice(false), 8000);
        }
      } catch {
        // ignore write failure; still update locally
      } finally {
        doLocalUpdate();
      }
    })();
  };

  const getFilteredVariables = () => {
    let allVariables: EnvironmentVariable[] = [];

    environmentCategories.forEach(category => {
      if (selectedCategory === 'all' || category.name.toLowerCase().includes(selectedCategory)) {
        allVariables = [...allVariables, ...category.variables];
      }
    });

    if (searchQuery) {
      allVariables = allVariables.filter(variable =>
        variable.key.toLowerCase().includes(searchQuery.toLowerCase()) ||
        variable.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
        variable.category.toLowerCase().includes(searchQuery.toLowerCase())
      );
    }

    return allVariables;
  };

  const getVariableIcon = (type: string) => {
    switch (type) {
      case 'password': return <IconKey size={14} />;
      case 'url': return <IconCloud size={14} />;
      case 'number': return <IconSettings size={14} />;
      case 'boolean': return <IconSettings size={14} />;
      case 'json': return <IconSettings size={14} />;
      default: return <IconSettings size={14} />;
    }
  };

  const renderVariableValue = (variable: EnvironmentVariable) => {
    if (variable.sensitive && !showSensitive[variable.key]) {
      return (
        <Group gap="xs">
          <Code>{'*'.repeat(8)}</Code>
          <ActionIcon
            size="sm"
            variant="subtle"
            onClick={() => toggleSensitive(variable.key)}
          >
            <IconEye size={12} />
          </ActionIcon>
        </Group>
      );
    }

    return (
      <Group gap="xs">
        <Code style={{ maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {variable.value || '<empty>'}
        </Code>
        {variable.sensitive && (
          <ActionIcon
            size="sm"
            variant="subtle"
            onClick={() => toggleSensitive(variable.key)}
          >
            <IconEyeOff size={12} />
          </ActionIcon>
        )}
      </Group>
    );
  };

  return (
    <Card shadow="sm" p="lg" radius="md" withBorder>
      {showRestartNotice && (
        <Alert color="grape" title="Restart required" mb="md" icon={<IconInfoCircle size={16} />}>Some changes require a service restart to take effect.</Alert>
      )}
      <Group justify="space-between" mb="md">
        <Text size="lg" fw={600}>
          Environment Variables
        </Text>
        <Group gap="sm">
          <Button size="sm" variant="light" leftSection={<IconDownload size={14} />} onClick={async () => {
            try {
              const res = await fetch(CONFIG_URL);
              const cfg = res.ok ? await res.json() : {};
              const blob = new Blob([JSON.stringify(cfg, null, 2)], { type: 'application/json' });
              const url = URL.createObjectURL(blob);
              const a = document.createElement('a');
              a.href = url;
              a.download = 'config.local.json';
              a.click();
              URL.revokeObjectURL(url);
            } catch {}
          }}>Export</Button>
          <Button size="sm" variant="light" leftSection={<IconUpload size={14} />} onClick={async () => {
            const input = document.createElement('input');
            input.type = 'file';
            input.accept = 'application/json';
            input.onchange = async () => {
              if (!input.files || input.files.length === 0) return;
              const file = input.files[0];
              const text = await file.text();
              try {
                const cfg = JSON.parse(text);
                await fetch(CONFIG_URL, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(cfg) });
                setEnvironmentCategories(buildCategories(cfg));
                setShowRestartNotice(true);
                setTimeout(() => setShowRestartNotice(false), 8000);
              } catch {}
            };
            input.click();
          }}>Import</Button>
          <ActionIcon variant="subtle" onClick={async () => {
            try {
              const res = await fetch(CONFIG_URL);
              const cfg = res.ok ? await res.json() : {};
              setEnvironmentCategories(buildCategories(cfg));
            } catch {}
          }}>
            <IconRefresh size={16} />
          </ActionIcon>
        </Group>
      </Group>

      {/* Search and Filter Controls */}
      <Group mb="md" gap="md">
        <TextInput
          placeholder="Search variables..."
          value={searchQuery}
          onChange={(event) => setSearchQuery(event.currentTarget.value)}
          leftSection={<IconSearch size={14} />}
          style={{ flex: 1 }}
        />
        <Select
          placeholder="Filter by category"
          value={selectedCategory}
          onChange={(value) => setSelectedCategory(value || 'all')}
          data={[
            { value: 'all', label: 'All Categories' },
            { value: 'database', label: 'Database' },
            { value: 'llm', label: 'LLM & AI' },
            { value: 'storage', label: 'Storage' },
            { value: 'services', label: 'Services' },
            { value: 'security', label: 'Security' },
          ]}
          style={{ width: 200 }}
        />
      </Group>

      {/* Environment Variables by Category */}
      <Accordion
        multiple
        value={expandedCategories}
        onChange={setExpandedCategories}
        variant="separated"
      >
        {environmentCategories.map((category) => {
          const filteredVariables = category.variables.filter(variable => {
            const matchesSearch = !searchQuery ||
              variable.key.toLowerCase().includes(searchQuery.toLowerCase()) ||
              variable.description.toLowerCase().includes(searchQuery.toLowerCase());

            const matchesCategory = selectedCategory === 'all' ||
              category.name.toLowerCase().includes(selectedCategory);

            return matchesSearch && matchesCategory;
          });

          if (filteredVariables.length === 0) return null;

          return (
            <Accordion.Item key={category.name} value={category.name.toLowerCase().replace(/\s+/g, '')}>
              <Accordion.Control icon={category.icon}>
                <Group justify="space-between" style={{ width: '100%' }}>
                  <Box>
                    <Text fw={500}>{category.name}</Text>
                    <Text size="sm" c="dimmed">{category.description}</Text>
                  </Box>
                  <Badge size="sm" variant="light">
                    {filteredVariables.length} variables
                  </Badge>
                </Group>
              </Accordion.Control>
              <Accordion.Panel>
                <Stack gap="md">
                  {filteredVariables.map((variable) => (
                    <Paper key={variable.key} p="md" withBorder>
                      <Group justify="space-between" align="flex-start">
                        <Box style={{ flex: 1 }}>
                          <Group gap="xs" mb="xs">
                            {getVariableIcon(variable.type)}
                            <Text fw={500} size="sm">{variable.key}</Text>
                            {variable.required && (
                              <Badge size="xs" color="red" variant="light">Required</Badge>
                            )}
                            {variable.sensitive && (
                              <Badge size="xs" color="orange" variant="light">Sensitive</Badge>
                            )}
                            <Badge size="xs" variant="light">{variable.type}</Badge>
                            {variable.restartRequired && (
                              <Tooltip label="Changing this setting requires a service restart to take effect" withArrow>
                                <Badge size="xs" color="grape" variant="filled">Restart required</Badge>
                              </Tooltip>
                            )}
                          </Group>

                          <Text size="sm" c="dimmed" mb="xs">
                            {variable.description}
                          </Text>

                          <Group gap="md" align="flex-start">
                            <Box>
                              <Text size="xs" fw={500} c="dimmed" mb={4}>Current Value:</Text>
                              {renderVariableValue(variable)}
                            </Box>

                            {variable.defaultValue && (
                              <Box>
                                <Text size="xs" fw={500} c="dimmed" mb={4}>Default:</Text>
                                <Code>{variable.defaultValue}</Code>
                              </Box>
                            )}

                            {variable.example && (
                              <Box>
                                <Text size="xs" fw={500} c="dimmed" mb={4}>Example:</Text>
                                <Code>{variable.example}</Code>
                              </Box>
                            )}
                          </Group>

                          {variable.validation && (
                            <Alert
                              icon={<IconInfoCircle size={14} />}
                              color="blue"
                              variant="light"
                              mt="xs"
                              p="xs"
                            >
                              <Text size="xs">{variable.validation}</Text>
                            </Alert>
                          )}
                        </Box>

                        <ActionIcon
                          variant="subtle"
                          onClick={() => handleEditVariable(variable)}
                        >
                          <IconEdit size={14} />
                        </ActionIcon>
                      </Group>
                    </Paper>
                  ))}
                </Stack>
              </Accordion.Panel>
            </Accordion.Item>
          );
        })}
      </Accordion>

      {/* Edit Variable Modal */}
      <Modal
        opened={editModalOpen}
        onClose={() => setEditModalOpen(false)}
        title={`Edit ${selectedVariable?.key}`}
        size="md"
      >
        {selectedVariable && (
          <Stack gap="md">
            <TextInput
              label="Variable Key"
              value={selectedVariable.key}
              disabled
            />

            <Textarea
              label="Description"
              value={selectedVariable.description}
              onChange={(event) => setSelectedVariable({
                ...selectedVariable,
                description: event.currentTarget.value,
              })}
              rows={2}
            />

            <TextInput
              label="Value"
              type={selectedVariable.sensitive ? 'password' : 'text'}
              value={selectedVariable.value}
              onChange={(event) => setSelectedVariable({
                ...selectedVariable,
                value: event.currentTarget.value,
              })}
            />

            <Group gap="md">
              <Switch
                label="Required"
                checked={selectedVariable.required}
                onChange={(event) => setSelectedVariable({
                  ...selectedVariable,
                  required: event.currentTarget.checked,
                })}
              />

              <Switch
                label="Sensitive"
                checked={selectedVariable.sensitive}
                onChange={(event) => setSelectedVariable({
                  ...selectedVariable,
                  sensitive: event.currentTarget.checked,
                })}
              />
            </Group>

            <Group justify="flex-end" gap="sm">
              <Button variant="light" onClick={() => setEditModalOpen(false)}>
                Cancel
              </Button>
              <Button onClick={handleSaveVariable}>
                Save Changes
              </Button>
            </Group>
          </Stack>
        )}
      </Modal>
    </Card>
  );
};

export default EnvironmentVariablesPanel;
