import React, { useState, useEffect, useRef } from 'react';
import {
  Card,
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
  TextInput,
  Table,
  Tabs,
  Loader,
  Menu,
} from '@mantine/core';
import ModernConsole from './ModernConsole';
import { LogsView } from '../../views/LogsView';
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
  IconSearch,
  IconClock,
  IconCopy,
  IconChevronDown,
  IconFileText,
  IconBraces,
} from '@tabler/icons-react';

interface LogEntry {
  timestamp: string;
  level: 'INFO' | 'WARNING' | 'ERROR' | 'DEBUG';
  service: string;
  message: string;
  details?: any;
}

interface SearchLogEntry {
  service: string;
  level: string;
  timestamp: string;
  correlation_id?: string;
  message: string;
  project_id?: string;
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
  const [activeTab, setActiveTab] = useState<string>(typeof window !== 'undefined' && window.location.hash ? window.location.hash.substring(1) : 'overview');
  const [viewMode, setViewMode] = useState<Record<string, 'console' | 'logs'>>({});
  const [selectedContainer, setSelectedContainer] = useState<string>('');
  const [logTimeRange, setLogTimeRange] = useState<string>('1h');
  
  // Correlation ID search state
  const [correlationId, setCorrelationId] = useState<string>('');
  const [searchTimeRange, setSearchTimeRange] = useState<string>('6h');
  const [searchResults, setSearchResults] = useState<SearchLogEntry[]>([]);
  const [isSearching, setIsSearching] = useState<boolean>(false);
  const [searchError, setSearchError] = useState<string | null>(null);

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

  const [containerStats, setContainerStats] = useState<ContainerStats[]>([]);
  const [containerError, setContainerError] = useState<string | null>(null);

  // Real system health from backend /health
  const [healthStatus, setHealthStatus] = useState<'healthy' | 'degraded' | 'unknown'>('unknown');
  const [servicesHealth, setServicesHealth] = useState<Record<string, string>>({});

  const fetchSystemHealth = async () => {
    try {
      const resp = await fetch('/api/health');
      if (!resp.ok) throw new Error(String(resp.status));
      const data = await resp.json();
      setHealthStatus((data.status as 'healthy' | 'degraded') || 'unknown');
      setServicesHealth((data.services as Record<string, string>) || {});
    } catch (e) {
      setHealthStatus('unknown');
      setServicesHealth({});
    }
  };

  // Correlation ID search function
  const searchByCorrelationId = async () => {
    if (!correlationId.trim()) {
      setSearchError('Please enter a correlation ID to search');
      return;
    }

    setIsSearching(true);
    setSearchError(null);
    setSearchResults([]);

    try {
      const params = new URLSearchParams({
        cid: correlationId.trim(),
        limit: '200'
      });

      // Add time range
      const now = Date.now();
      const rangeMs = {
        '15m': 15 * 60 * 1000,
        '1h': 60 * 60 * 1000,
        '6h': 6 * 60 * 60 * 1000,
        '24h': 24 * 60 * 60 * 1000,
        '7d': 7 * 24 * 60 * 60 * 1000,
      }[searchTimeRange] || 6 * 60 * 60 * 1000;
      
      const fromTs = new Date(now - rangeMs).toISOString();
      params.set('from', fromTs);

      const response = await fetch(`/api/logs/search?${params.toString()}`);
      
      if (!response.ok) {
        throw new Error(`Search failed: ${response.status} ${response.statusText}`);
      }

      const data = await response.json();
      const results: SearchLogEntry[] = (data.entries || []).map((entry: any) => ({
        service: entry.service || 'unknown',
        level: entry.level || 'INFO',
        timestamp: entry.timestamp || new Date().toISOString(),
        correlation_id: entry.correlation_id,
        message: entry.message || '',
        project_id: entry.project_id
      }));

      setSearchResults(results);
      
      if (results.length === 0) {
        setSearchError(`No logs found for correlation ID: ${correlationId}`);
      }
    } catch (error: any) {
      console.error('Correlation ID search failed:', error);
      setSearchError(error.message || 'Failed to search logs');
    } finally {
      setIsSearching(false);
    }
  };

  // Clear search results
  const clearSearch = () => {
    setCorrelationId('');
    setSearchResults([]);
    setSearchError(null);
  };

  // Copy search results as CSV
  const copyAsCSV = () => {
    if (searchResults.length === 0) return;
    
    const headers = ['Timestamp', 'Service', 'Level', 'Message', 'Project ID', 'Correlation ID'];
    const csvContent = [
      headers.join(','),
      ...searchResults.map(entry => [
        `"${entry.timestamp ? new Date(entry.timestamp).toISOString() : ''}",`,
        `"${entry.service}",`,
        `"${entry.level}",`,
        `"${(entry.message || '').replace(/"/g, '""')}",`,
        `"${entry.project_id || ''}",`,
        `"${entry.correlation_id || ''}"`
      ].join(''))
    ].join('\n');
    
    navigator.clipboard.writeText(csvContent).then(() => {
      // Could add a notification here if needed
      console.log('CSV copied to clipboard');
    }).catch(err => {
      console.error('Failed to copy CSV:', err);
    });
  };

  // Copy search results as JSON
  const copyAsJSON = () => {
    if (searchResults.length === 0) return;
    
    const jsonData = {
      search_query: {
        correlation_id: correlationId,
        time_range: searchTimeRange,
        search_timestamp: new Date().toISOString()
      },
      results_count: searchResults.length,
      entries: searchResults.map(entry => ({
        timestamp: entry.timestamp,
        service: entry.service,
        level: entry.level,
        message: entry.message,
        project_id: entry.project_id,
        correlation_id: entry.correlation_id
      }))
    };
    
    const jsonContent = JSON.stringify(jsonData, null, 2);
    
    navigator.clipboard.writeText(jsonContent).then(() => {
      // Could add a notification here if needed
      console.log('JSON copied to clipboard');
    }).catch(err => {
      console.error('Failed to copy JSON:', err);
    });
  };

  const fetchContainerStats = async () => {
    try {
      setContainerError(null);
      const resp = await fetch('/api/health/containers');
      if (!resp.ok) {
        const msg = `HTTP ${resp.status}: ${resp.statusText}`;
        setContainerError(msg);
        throw new Error(msg);
      }
      const data = await resp.json();
      if (data.containers && Array.isArray(data.containers)) {
        setContainerStats(data.containers);
      } else {
        setContainerStats([]);
      }
    } catch (e: any) {
      setContainerStats([]);
      if (!containerError) setContainerError(String(e?.message || e));
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

  // Render correlation ID search interface
  const renderSearch = () => (
    <Stack gap="md">
      <Group justify="space-between" align="center">
        <Group gap="sm">
          <IconSearch size={20} />
          <Text size="lg" fw={600}>Cross-Service Log Search</Text>
        </Group>
        <Badge color="blue" variant="light">Search across all services</Badge>
      </Group>
      
      <Card withBorder p="md">
        <Stack gap="md">
          <Group align="end" gap="md">
            <TextInput
              label="Correlation ID"
              placeholder="Enter correlation ID (e.g., corr_123, doc-process-abc)"
              value={correlationId}
              onChange={(event) => setCorrelationId(event.currentTarget.value)}
              style={{ flex: 1 }}
              leftSection={<IconSearch size={16} />}
              onKeyPress={(event) => {
                if (event.key === 'Enter') {
                  searchByCorrelationId();
                }
              }}
            />
            <Select
              label="Time Range"
              value={searchTimeRange}
              onChange={(value) => setSearchTimeRange(value || '6h')}
              data={[
                { value: '15m', label: 'Last 15 minutes' },
                { value: '1h', label: 'Last hour' },
                { value: '6h', label: 'Last 6 hours' },
                { value: '24h', label: 'Last 24 hours' },
                { value: '7d', label: 'Last 7 days' },
              ]}
              w={180}
              leftSection={<IconClock size={16} />}
            />
            <Button
              onClick={searchByCorrelationId}
              loading={isSearching}
              disabled={!correlationId.trim()}
              leftSection={<IconSearch size={16} />}
            >
              Search
            </Button>
            {(searchResults.length > 0 || searchError) && (
              <Group gap="xs">
                <Menu shadow="md" width={200}>
                  <Menu.Target>
                    <Button
                      variant="light"
                      color="blue"
                      disabled={searchResults.length === 0}
                      leftSection={<IconCopy size={16} />}
                      rightSection={<IconChevronDown size={14} />}
                    >
                      Copy
                    </Button>
                  </Menu.Target>
                  
                  <Menu.Dropdown>
                    <Menu.Label>Export Format</Menu.Label>
                    <Menu.Item
                      leftSection={<IconFileText size={16} />}
                      onClick={copyAsCSV}
                      disabled={searchResults.length === 0}
                    >
                      Copy as CSV
                    </Menu.Item>
                    <Menu.Item
                      leftSection={<IconBraces size={16} />}
                      onClick={copyAsJSON}
                      disabled={searchResults.length === 0}
                    >
                      Copy as JSON
                    </Menu.Item>
                  </Menu.Dropdown>
                </Menu>
                
                <Button
                  variant="light"
                  color="gray"
                  onClick={clearSearch}
                  leftSection={<IconX size={16} />}
                >
                  Clear
                </Button>
              </Group>
            )}
          </Group>
          
          {searchError && (
            <Alert color="orange" icon={<IconAlertTriangle size={16} />}>
              {searchError}
            </Alert>
          )}
        </Stack>
      </Card>

      {/* Search Results */}
      {searchResults.length > 0 && (
        <Card withBorder>
          <Group justify="space-between" mb="md">
            <Group gap="sm">
              <Text size="md" fw={600}>Search Results</Text>
              <Badge color="green" variant="light">
                {searchResults.length} entries found
              </Badge>
            </Group>
            <Text size="sm" c="dimmed">
              Correlation ID: {correlationId}
            </Text>
          </Group>
          
          <ScrollArea h={400}>
            <Table striped highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Timestamp</Table.Th>
                  <Table.Th>Service</Table.Th>
                  <Table.Th>Level</Table.Th>
                  <Table.Th>Message</Table.Th>
                  <Table.Th>Project</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {searchResults.map((entry, index) => {
                  const getLevelColor = (level: string) => {
                    switch (level?.toUpperCase()) {
                      case 'ERROR': return 'red';
                      case 'WARNING': return 'orange';
                      case 'INFO': return 'blue';
                      case 'DEBUG': return 'gray';
                      case 'CRITICAL': return 'red';
                      default: return 'blue';
                    }
                  };

                  return (
                    <Table.Tr key={index}>
                      <Table.Td>
                        <Text size="xs" ff="monospace" c="dimmed">
                          {entry.timestamp ? new Date(entry.timestamp).toLocaleString() : '-'}
                        </Text>
                      </Table.Td>
                      <Table.Td>
                        <Badge size="sm" variant="light" color="cyan">
                          {entry.service}
                        </Badge>
                      </Table.Td>
                      <Table.Td>
                        <Badge size="sm" color={getLevelColor(entry.level)} variant="light">
                          {entry.level}
                        </Badge>
                      </Table.Td>
                      <Table.Td>
                        <Text size="sm" style={{ 
                          maxWidth: '400px', 
                          wordBreak: 'break-word',
                          whiteSpace: 'pre-wrap'
                        }}>
                          {entry.message}
                        </Text>
                      </Table.Td>
                      <Table.Td>
                        {entry.project_id ? (
                          <Badge size="sm" variant="light" color="gray">
                            {entry.project_id}
                          </Badge>
                        ) : (
                          <Text size="xs" c="dimmed">-</Text>
                        )}
                      </Table.Td>
                    </Table.Tr>
                  );
                })}
              </Table.Tbody>
            </Table>
          </ScrollArea>
        </Card>
      )}

      {isSearching && (
        <Card withBorder>
          <Group justify="center" p="xl">
            <Loader size="sm" />
            <Text size="sm" c="dimmed">Searching logs across all services...</Text>
          </Group>
        </Card>
      )}
    </Stack>
  );

  // Sync tab with URL hash changes
  useEffect(() => {
    const handler = () => {
      const tab = window.location.hash ? window.location.hash.substring(1) : 'overview';
      setActiveTab(tab || 'overview');
    };
    window.addEventListener('hashchange', handler);
    return () => window.removeEventListener('hashchange', handler);
  }, []);

  // Auto-select first container when containers load
  useEffect(() => {
    if (containerStats.length > 0 && (!selectedContainer || !containerStats.find(c => c.name === selectedContainer))) {
      setSelectedContainer(containerStats[0].name);
    }
  }, [containerStats, selectedContainer]);

  // Real updates: poll backend health for service status and container stats
  useEffect(() => {
    fetchSystemHealth();
    fetchContainerStats();
    const healthInterval = setInterval(() => fetchSystemHealth(), 120000);
    const containerInterval = setInterval(() => fetchContainerStats(), 60000);
    return () => {
      clearInterval(healthInterval);
      clearInterval(containerInterval);
    };
  }, []);

  return (
    <Card withBorder>
      <Stack gap="md">
        <Group justify="space-between">
          <Group gap="sm">
            <IconContainer size={20} />
            <Text size="lg" fw={600}>System Logs & Monitoring</Text>
          </Group>
        </Group>
        
        <Divider />
        
        <Tabs value={activeTab} onChange={(value) => {
          const newTab = value || 'overview';
          setActiveTab(newTab);
          if (typeof window !== 'undefined') {
            window.location.hash = newTab;
          }
        }}>
          <Tabs.List>
            <Tabs.Tab value="overview" leftSection={<IconActivity size={16} />}>
              Overview
            </Tabs.Tab>
            <Tabs.Tab value="search" leftSection={<IconSearch size={16} />}>
              Search
            </Tabs.Tab>
            <Tabs.Tab value="logs" leftSection={<IconList size={16} />}>
              Advanced Logs
            </Tabs.Tab>
            <Tabs.Tab value="backend" leftSection={<IconServer size={16} />}>
              Backend
            </Tabs.Tab>
          </Tabs.List>
          
          <Tabs.Panel value="overview" pt="md">
            <Grid>
              <Grid.Col span={6}>
                <Card withBorder>
                  <Text size="md" fw={600} mb="md">Application Services</Text>
                  <Stack gap="sm">
                    {Object.entries(servicesHealth).map(([name, status]) => (
                      <Group key={name} justify="space-between">
                        <Group gap="sm">
                          <Badge color={status === 'connected' ? 'green' : 'red'} size="sm">
                            {status === 'connected' ? 'running' : 'error'}
                          </Badge>
                          <Text size="sm" fw={500}>{name}</Text>
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
                    {containerStats.length > 0 ? (
                      containerStats.filter(container => container && container.name).map((container, index) => (
                        <Group key={index} justify="space-between">
                          <Group gap="sm">
                            <Badge color={getStatusColor(container.status)} size="sm">
                              {container.status}
                            </Badge>
                            <Text size="sm" fw={500}>{container.name}</Text>
                          </Group>
                        </Group>
                      ))
                    ) : (
                      <Text size="sm" c="dimmed" style={{ textAlign: 'center', padding: '20px' }}>
                        Loading container stats...
                      </Text>
                    )}
                  </Stack>
                </Card>
              </Grid.Col>
            </Grid>
          </Tabs.Panel>
          
          <Tabs.Panel value="search" pt="md">
            {renderSearch()}
          </Tabs.Panel>
          
          <Tabs.Panel value="logs" pt="md">
            <div style={{ paddingTop: 4 }}>
              <LogsView />
            </div>
          </Tabs.Panel>
          
          <Tabs.Panel value="backend" pt="md">
            <ModernConsole service="backend" title="Backend API" icon={<IconServer size={20} />} mode="logs" />
          </Tabs.Panel>
        </Tabs>
      </Stack>
    </Card>
  );
};

export default SystemLogsViewer;