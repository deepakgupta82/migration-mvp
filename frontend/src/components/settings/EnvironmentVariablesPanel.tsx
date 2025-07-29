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
}

interface EnvironmentCategory {
  name: string;
  icon: React.ReactNode;
  description: string;
  variables: EnvironmentVariable[];
}

export const EnvironmentVariablesPanel: React.FC = () => {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [selectedVariable, setSelectedVariable] = useState<EnvironmentVariable | null>(null);
  const [showSensitive, setShowSensitive] = useState<Record<string, boolean>>({});
  const [expandedCategories, setExpandedCategories] = useState<string[]>(['database', 'llm']);

  // Mock environment variables data - replace with real API calls
  const [environmentCategories, setEnvironmentCategories] = useState<EnvironmentCategory[]>([
    {
      name: 'Database Configuration',
      icon: <IconDatabase size={16} />,
      description: 'Database connection and configuration settings',
      variables: [
        {
          key: 'DATABASE_URL',
          value: 'postgresql://projectuser:projectpass@localhost:5432/projectdb',
          description: 'Primary PostgreSQL database connection string',
          category: 'database',
          type: 'url',
          required: true,
          sensitive: true,
          example: 'postgresql://user:password@host:port/database',
          validation: 'Must be a valid PostgreSQL connection string',
        },
        {
          key: 'NEO4J_URI',
          value: 'bolt://localhost:7687',
          description: 'Neo4j graph database connection URI',
          category: 'database',
          type: 'url',
          required: true,
          sensitive: false,
          example: 'bolt://localhost:7687',
        },
        {
          key: 'NEO4J_USERNAME',
          value: 'neo4j',
          description: 'Neo4j database username',
          category: 'database',
          type: 'string',
          required: true,
          sensitive: false,
        },
        {
          key: 'NEO4J_PASSWORD',
          value: 'password',
          description: 'Neo4j database password',
          category: 'database',
          type: 'password',
          required: true,
          sensitive: true,
        },
        {
          key: 'WEAVIATE_URL',
          value: 'http://localhost:8080',
          description: 'Weaviate vector database endpoint',
          category: 'database',
          type: 'url',
          required: true,
          sensitive: false,
        },
        {
          key: 'REDIS_URL',
          value: 'redis://localhost:6379',
          description: 'Redis cache connection string',
          category: 'database',
          type: 'url',
          required: false,
          sensitive: false,
        },
      ],
    },
    {
      name: 'LLM & AI Configuration',
      icon: <IconRobot size={16} />,
      description: 'Large Language Model and AI service settings',
      variables: [
        {
          key: 'OPENAI_API_KEY',
          value: 'sk-...',
          description: 'OpenAI API key for GPT models',
          category: 'llm',
          type: 'password',
          required: false,
          sensitive: true,
          example: 'sk-1234567890abcdef...',
        },
        {
          key: 'ANTHROPIC_API_KEY',
          value: '',
          description: 'Anthropic API key for Claude models',
          category: 'llm',
          type: 'password',
          required: false,
          sensitive: true,
          example: 'sk-ant-api03-...',
        },
        {
          key: 'AZURE_OPENAI_ENDPOINT',
          value: '',
          description: 'Azure OpenAI service endpoint',
          category: 'llm',
          type: 'url',
          required: false,
          sensitive: false,
          example: 'https://your-resource.openai.azure.com/',
        },
        {
          key: 'AZURE_OPENAI_API_KEY',
          value: '',
          description: 'Azure OpenAI API key',
          category: 'llm',
          type: 'password',
          required: false,
          sensitive: true,
        },
        {
          key: 'DEFAULT_LLM_PROVIDER',
          value: 'openai',
          description: 'Default LLM provider to use',
          category: 'llm',
          type: 'string',
          required: true,
          sensitive: false,
          example: 'openai, anthropic, azure',
        },
        {
          key: 'DEFAULT_LLM_MODEL',
          value: 'gpt-4',
          description: 'Default LLM model to use',
          category: 'llm',
          type: 'string',
          required: true,
          sensitive: false,
          example: 'gpt-4, gpt-3.5-turbo, claude-3-sonnet',
        },
        {
          key: 'LLM_TEMPERATURE',
          value: '0.1',
          description: 'Default temperature for LLM responses (0.0-1.0)',
          category: 'llm',
          type: 'number',
          required: false,
          sensitive: false,
          defaultValue: '0.1',
          validation: 'Must be between 0.0 and 1.0',
        },
        {
          key: 'LLM_MAX_TOKENS',
          value: '4000',
          description: 'Maximum tokens for LLM responses',
          category: 'llm',
          type: 'number',
          required: false,
          sensitive: false,
          defaultValue: '4000',
        },
      ],
    },
    {
      name: 'Cloud Storage',
      icon: <IconCloud size={16} />,
      description: 'Object storage and file management settings',
      variables: [
        {
          key: 'MINIO_ENDPOINT',
          value: 'localhost:9000',
          description: 'MinIO object storage endpoint',
          category: 'storage',
          type: 'string',
          required: true,
          sensitive: false,
        },
        {
          key: 'MINIO_ACCESS_KEY',
          value: 'minioadmin',
          description: 'MinIO access key',
          category: 'storage',
          type: 'string',
          required: true,
          sensitive: true,
        },
        {
          key: 'MINIO_SECRET_KEY',
          value: 'minioadmin',
          description: 'MinIO secret key',
          category: 'storage',
          type: 'password',
          required: true,
          sensitive: true,
        },
        {
          key: 'MINIO_BUCKET_NAME',
          value: 'agentimigrate',
          description: 'Default MinIO bucket name',
          category: 'storage',
          type: 'string',
          required: true,
          sensitive: false,
        },
        {
          key: 'AWS_ACCESS_KEY_ID',
          value: '',
          description: 'AWS access key for S3 storage',
          category: 'storage',
          type: 'string',
          required: false,
          sensitive: true,
        },
        {
          key: 'AWS_SECRET_ACCESS_KEY',
          value: '',
          description: 'AWS secret access key',
          category: 'storage',
          type: 'password',
          required: false,
          sensitive: true,
        },
        {
          key: 'AWS_REGION',
          value: 'us-east-1',
          description: 'AWS region for services',
          category: 'storage',
          type: 'string',
          required: false,
          sensitive: false,
          defaultValue: 'us-east-1',
        },
      ],
    },
    {
      name: 'Application Services',
      icon: <IconServer size={16} />,
      description: 'Core application and service configuration',
      variables: [
        {
          key: 'BACKEND_PORT',
          value: '8000',
          description: 'Backend service port',
          category: 'services',
          type: 'number',
          required: true,
          sensitive: false,
          defaultValue: '8000',
        },
        {
          key: 'PROJECT_SERVICE_PORT',
          value: '8002',
          description: 'Project service port',
          category: 'services',
          type: 'number',
          required: true,
          sensitive: false,
          defaultValue: '8002',
        },
        {
          key: 'FRONTEND_PORT',
          value: '3000',
          description: 'Frontend development server port',
          category: 'services',
          type: 'number',
          required: true,
          sensitive: false,
          defaultValue: '3000',
        },
        {
          key: 'MEGAPARSE_URL',
          value: 'http://localhost:5001',
          description: 'MegaParse document processing service URL',
          category: 'services',
          type: 'url',
          required: true,
          sensitive: false,
        },
        {
          key: 'CORS_ORIGINS',
          value: 'http://localhost:3000,http://localhost:3001',
          description: 'Allowed CORS origins (comma-separated)',
          category: 'services',
          type: 'string',
          required: true,
          sensitive: false,
        },
        {
          key: 'LOG_LEVEL',
          value: 'INFO',
          description: 'Application logging level',
          category: 'services',
          type: 'string',
          required: false,
          sensitive: false,
          defaultValue: 'INFO',
          example: 'DEBUG, INFO, WARNING, ERROR',
        },
        {
          key: 'ENVIRONMENT',
          value: 'development',
          description: 'Application environment',
          category: 'services',
          type: 'string',
          required: true,
          sensitive: false,
          example: 'development, staging, production',
        },
      ],
    },
    {
      name: 'Security & Authentication',
      icon: <IconKey size={16} />,
      description: 'Security, authentication, and encryption settings',
      variables: [
        {
          key: 'JWT_SECRET_KEY',
          value: 'your-secret-key-here',
          description: 'JWT token signing secret key',
          category: 'security',
          type: 'password',
          required: true,
          sensitive: true,
          validation: 'Should be at least 32 characters long',
        },
        {
          key: 'JWT_ALGORITHM',
          value: 'HS256',
          description: 'JWT signing algorithm',
          category: 'security',
          type: 'string',
          required: true,
          sensitive: false,
          defaultValue: 'HS256',
        },
        {
          key: 'JWT_EXPIRATION_HOURS',
          value: '24',
          description: 'JWT token expiration time in hours',
          category: 'security',
          type: 'number',
          required: false,
          sensitive: false,
          defaultValue: '24',
        },
        {
          key: 'ENCRYPTION_KEY',
          value: '',
          description: 'Encryption key for sensitive data',
          category: 'security',
          type: 'password',
          required: false,
          sensitive: true,
        },
        {
          key: 'RATE_LIMIT_PER_MINUTE',
          value: '100',
          description: 'API rate limit per minute per IP',
          category: 'security',
          type: 'number',
          required: false,
          sensitive: false,
          defaultValue: '100',
        },
      ],
    },
  ]);

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

    // Update the variable in the categories
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
      <Group justify="space-between" mb="md">
        <Text size="lg" fw={600}>
          Environment Variables
        </Text>
        <Group gap="sm">
          <Button
            size="sm"
            variant="light"
            leftSection={<IconDownload size={14} />}
          >
            Export
          </Button>
          <Button
            size="sm"
            variant="light"
            leftSection={<IconUpload size={14} />}
          >
            Import
          </Button>
          <ActionIcon variant="subtle">
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
