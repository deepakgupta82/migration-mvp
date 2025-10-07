import React, { useEffect, useState } from 'react';
import { Card, Stack, Group, Text, Button, Table, Modal, TextInput, Select, Switch, Grid, ActionIcon, Badge, Divider, Loader, NumberInput, Textarea, Accordion } from '@mantine/core';
import { IconPlus, IconTrash, IconEdit, IconRefresh, IconKey } from '@tabler/icons-react';

type Provider = 'aws' | 'azure' | 'gcp' | 'custom';
type Transport = 'stdio' | 'ws' | 'sse';

interface STDIOConnection { command: string; args?: string[]; cwd?: string }
interface ConnectionConfig { transport: Transport; stdio?: STDIOConnection; ws?: { url: string }; sse?: { url: string } }

interface MCPServerConfig {
  id?: string;
  name: string;
  provider: Provider;
  connection: ConnectionConfig;
  env?: Record<string, string>;
  tool_allowlist?: string[];
  tool_denylist?: string[];
  is_enabled?: boolean;
  description?: string;
  health_status?: 'unknown' | 'healthy' | 'unhealthy';
  rate_limit_rpm?: number;
  max_concurrency?: number;
  discovery_cache_ttl_sec?: number;
  last_discovered_at?: string;
}

interface UnifiedToolSchema { name: string; description?: string; server_id: string; provider: Provider }

const defaultConfig: MCPServerConfig = {
  name: '',
  provider: 'custom',
  connection: { transport: 'stdio', stdio: { command: 'node', args: ['index.js'] } },
  env: {},
  tool_allowlist: [],
  tool_denylist: [],
  is_enabled: true,
  description: ''
};

const API = 'http://localhost:8008/api/mcp';

export default function MCPServersPanel() {
  const [servers, setServers] = useState<MCPServerConfig[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<MCPServerConfig | null>(null);
  const [toolsMap, setToolsMap] = useState<Record<string, UnifiedToolSchema[]>>({});
  const [discovering, setDiscovering] = useState<string | null>(null);
  const [healthLoading, setHealthLoading] = useState<string | null>(null);

  const loadServers = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/servers`);
      const data = await res.json();
      setServers(data || []);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadServers(); }, []);

  const openCreate = () => { setEditing({ ...defaultConfig }); setModalOpen(true); };
  const openEdit = (cfg: MCPServerConfig) => { setEditing({ ...cfg }); setModalOpen(true); };

  const saveServer = async () => {
    if (!editing) return;
    const hasId = !!editing.id;
    const method = hasId ? 'PUT' : 'POST';
    const url = hasId ? `${API}/servers/${editing.id}` : `${API}/servers`;
    const body = JSON.stringify({
      id: editing.id,
      name: editing.name,
      provider: editing.provider,
      connection: editing.connection,
      env: editing.env || {},
      tool_allowlist: editing.tool_allowlist || [],
      tool_denylist: editing.tool_denylist || [],
      is_enabled: editing.is_enabled !== false,
      description: editing.description || ''
    });
    const res = await fetch(url, { method, headers: { 'Content-Type': 'application/json' }, body });
    if (res.ok) {
      setModalOpen(false);
      setEditing(null);
      await loadServers();
    }
  };

  const deleteServer = async (id?: string) => {
    if (!id) return;
    if (!(window as any).confirm('Delete this MCP server?')) return;
    await fetch(`${API}/servers/${id}`, { method: 'DELETE' });
    await loadServers();
  };

  const discover = async (id: string) => {
    setDiscovering(id);
    try {
      const res = await fetch(`${API}/servers/${id}/discover`, { method: 'POST' });
      const data = await res.json();
      setToolsMap(prev => ({ ...prev, [id]: data || [] }));
    } finally {
      setDiscovering(null);
    }
  };

  const viewTools = async (id: string) => {
    const res = await fetch(`${API}/servers/${id}/tools`);
    const data = await res.json();
    setToolsMap(prev => ({ ...prev, [id]: data || [] }));
  };

  const checkHealth = async (id: string) => {
    setHealthLoading(id);
    try {
      const res = await fetch(`${API}/servers/${id}/health`);
      const data = await res.json();
      setServers(prev => prev.map(s => s.id === id ? { ...s, health_status: data.status, last_discovered_at: data.last_discovered_at } : s));
    } finally {
      setHealthLoading(null);
    }
  };

  return (
    <Card shadow="sm" p="lg" radius="md" withBorder>
      <Stack gap="md">
        <Group justify="space-between">
          <div>
            <Text size="lg" fw={600}>Model Context Protocol Servers</Text>
            <Text size="sm" c="dimmed">Register AWS/Azure/GCP MCP servers and discover tools</Text>
          </div>
          <Group>
            <Button leftSection={<IconPlus size={16} />} onClick={openCreate}>Add Server</Button>
            <ActionIcon onClick={loadServers} variant="light"><IconRefresh size={16} /></ActionIcon>
          </Group>
        </Group>
        <Divider />

        {loading ? (
          <Group justify="center"><Loader /></Group>
        ) : (
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Name</Table.Th>
                <Table.Th>Provider</Table.Th>
                <Table.Th>Transport</Table.Th>
                <Table.Th>Status</Table.Th>
                  <Table.Th>Policies</Table.Th>
                <Table.Th>Tools</Table.Th>
                <Table.Th>Actions</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {servers.map((s) => (
                <Table.Tr key={s.id}>
                  <Table.Td>
                    <Text fw={600}>{s.name}</Text>
                    <Text size="xs" c="dimmed">{s.description}</Text>
                  </Table.Td>
                  <Table.Td><Badge>{s.provider}</Badge></Table.Td>
                  <Table.Td><Badge variant="light">{s.connection.transport}</Badge></Table.Td>
                  <Table.Td>
                    <Badge color={s.health_status === 'healthy' ? 'green' : s.health_status === 'unhealthy' ? 'red' : 'gray'}>
                      {s.health_status || 'unknown'}
                    </Badge>
                    {s.last_discovered_at && (
                      <Text size="xs" c="dimmed">Last: {new Date(s.last_discovered_at).toLocaleString()}</Text>
                    )}
                  </Table.Td>
                  <Table.Td>
                    <Stack gap={2}>
                      <Text size="xs">RPM: {s.rate_limit_rpm ?? 60} • Concurrency: {s.max_concurrency ?? 4}</Text>
                      <Text size="xs" c="dimmed">Tools TTL: {s.discovery_cache_ttl_sec ?? 900}s</Text>
                    </Stack>
                  </Table.Td>
                  <Table.Td>
                    <Group gap="xs">
                      <Button size="xs" variant="light" onClick={() => viewTools(s.id!)}>View</Button>
                      <Button size="xs" variant="outline" onClick={() => discover(s.id!)} loading={discovering === s.id}>Discover</Button>
                      <Button size="xs" variant="default" onClick={() => checkHealth(s.id!)} loading={healthLoading === s.id}>Health</Button>
                    </Group>
                    {toolsMap[s.id!] && toolsMap[s.id!].length > 0 && (
                      <Stack gap={4} mt={6}>
                        {toolsMap[s.id!].slice(0, 5).map(t => (
                          <Text size="xs" key={t.name}>• {t.name}</Text>
                        ))}
                        {toolsMap[s.id!].length > 5 && (
                          <Text size="xs" c="dimmed">+{toolsMap[s.id!].length - 5} more</Text>
                        )}
                      </Stack>
                    )}
                  </Table.Td>
                  <Table.Td>
                    <Group gap="xs">
                      <ActionIcon variant="subtle" color="blue" onClick={() => openEdit(s)}><IconEdit size={16} /></ActionIcon>
                      <ActionIcon variant="subtle" color="red" onClick={() => deleteServer(s.id)}><IconTrash size={16} /></ActionIcon>
                    </Group>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        )}

        <Modal opened={modalOpen} onClose={() => setModalOpen(false)} title={editing?.id ? 'Edit MCP Server' : 'Add MCP Server'} size="lg">
          {editing && (
            <Stack>
              <TextInput label="Name" value={editing.name} onChange={(e) => setEditing({ ...editing, name: e.currentTarget.value })} required />
              <Select label="Provider" value={editing.provider} onChange={(v) => setEditing({ ...editing, provider: (v as Provider) || 'custom' })}
                data={[{value:'aws',label:'AWS'},{value:'azure',label:'Azure'},{value:'gcp',label:'GCP'},{value:'custom',label:'Custom'}]}
              />
              <Select label="Transport" value={editing.connection.transport} onChange={(v) => setEditing({ ...editing, connection: { ...editing.connection, transport: (v as Transport) || 'stdio', stdio: (v==='stdio'? (editing.connection.stdio || {command:'node', args:['index.js']}) : undefined) } })}
                data={[{value:'stdio',label:'STDIO'},{value:'ws',label:'WebSocket'},{value:'sse',label:'SSE'}]}
              />
              {editing.connection.transport === 'stdio' && (
                <Grid>
                  <Grid.Col span={6}><TextInput label="Command" value={editing.connection.stdio?.command||''} onChange={(e)=> setEditing({ ...editing, connection: { ...editing.connection, stdio: { ...(editing.connection.stdio||{command:''}), command: e.currentTarget.value } } })} required/></Grid.Col>
                  <Grid.Col span={6}><TextInput label="Args (space-separated)" value={(editing.connection.stdio?.args||[]).join(' ')} onChange={(e)=> setEditing({ ...editing, connection: { ...editing.connection, stdio: { ...(editing.connection.stdio||{command:''}), args: e.currentTarget.value.trim()? e.currentTarget.value.split(' ') : [] } } })} /></Grid.Col>
                  <Grid.Col span={12}><TextInput label="Working Directory" value={editing.connection.stdio?.cwd||''} onChange={(e)=> setEditing({ ...editing, connection: { ...editing.connection, stdio: { ...(editing.connection.stdio||{command:''}), cwd: e.currentTarget.value } } })} /></Grid.Col>
                </Grid>
              )}
              <Grid>
                <Grid.Col span={4}><NumberInput label="Rate limit (RPM)" value={editing.rate_limit_rpm ?? 60} onChange={(v)=> setEditing({ ...editing, rate_limit_rpm: Number(v) || 60 })} min={1} /></Grid.Col>
                <Grid.Col span={4}><NumberInput label="Max concurrency" value={editing.max_concurrency ?? 4} onChange={(v)=> setEditing({ ...editing, max_concurrency: Number(v) || 4 })} min={1} /></Grid.Col>
                <Grid.Col span={4}><NumberInput label="Tools cache TTL (sec)" value={editing.discovery_cache_ttl_sec ?? 900} onChange={(v)=> setEditing({ ...editing, discovery_cache_ttl_sec: Number(v) || 900 })} min={60} /></Grid.Col>
              </Grid>
              
              <Divider label="Environment Variables" labelPosition="center" />
              <Stack gap="xs">
                <Text size="sm" c="dimmed">Configure credentials and environment variables for the MCP server</Text>
                {editing.provider === 'aws' && (
                  <>
                    <TextInput 
                      label="AWS Access Key ID" 
                      placeholder="AKIAIOSFODNN7EXAMPLE"
                      value={editing.env?.AWS_ACCESS_KEY_ID || ''} 
                      onChange={(e) => setEditing({ ...editing, env: { ...editing.env, AWS_ACCESS_KEY_ID: e.currentTarget.value } })}
                      leftSection={<IconKey size={16} />}
                    />
                    <TextInput 
                      label="AWS Secret Access Key" 
                      placeholder="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
                      type="password"
                      value={editing.env?.AWS_SECRET_ACCESS_KEY || ''} 
                      onChange={(e) => setEditing({ ...editing, env: { ...editing.env, AWS_SECRET_ACCESS_KEY: e.currentTarget.value } })}
                      leftSection={<IconKey size={16} />}
                    />
                    <TextInput 
                      label="AWS Default Region (optional)" 
                      placeholder="us-east-1"
                      value={editing.env?.AWS_DEFAULT_REGION || ''} 
                      onChange={(e) => setEditing({ ...editing, env: { ...editing.env, AWS_DEFAULT_REGION: e.currentTarget.value } })}
                    />
                  </>
                )}
                {editing.provider === 'azure' && (
                  <>
                    <TextInput 
                      label="Azure Client ID" 
                      value={editing.env?.AZURE_CLIENT_ID || ''} 
                      onChange={(e) => setEditing({ ...editing, env: { ...editing.env, AZURE_CLIENT_ID: e.currentTarget.value } })}
                      leftSection={<IconKey size={16} />}
                    />
                    <TextInput 
                      label="Azure Client Secret" 
                      type="password"
                      value={editing.env?.AZURE_CLIENT_SECRET || ''} 
                      onChange={(e) => setEditing({ ...editing, env: { ...editing.env, AZURE_CLIENT_SECRET: e.currentTarget.value } })}
                      leftSection={<IconKey size={16} />}
                    />
                    <TextInput 
                      label="Azure Tenant ID" 
                      value={editing.env?.AZURE_TENANT_ID || ''} 
                      onChange={(e) => setEditing({ ...editing, env: { ...editing.env, AZURE_TENANT_ID: e.currentTarget.value } })}
                    />
                  </>
                )}
                {editing.provider === 'gcp' && (
                  <TextInput 
                    label="GCP Service Account Key Path" 
                    value={editing.env?.GOOGLE_APPLICATION_CREDENTIALS || ''} 
                    onChange={(e) => setEditing({ ...editing, env: { ...editing.env, GOOGLE_APPLICATION_CREDENTIALS: e.currentTarget.value } })}
                    leftSection={<IconKey size={16} />}
                  />
                )}
                <Accordion variant="contained">
                  <Accordion.Item value="custom-env">
                    <Accordion.Control>Additional Environment Variables</Accordion.Control>
                    <Accordion.Panel>
                      <Textarea 
                        placeholder="KEY=value&#10;ANOTHER_KEY=another_value"
                        description="Enter one environment variable per line in KEY=value format"
                        minRows={4}
                        value={Object.entries(editing.env || {})
                          .filter(([k]) => {
                            // Exclude provider-specific vars from custom textarea
                            if (editing.provider === 'aws') return !['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_DEFAULT_REGION'].includes(k);
                            if (editing.provider === 'azure') return !['AZURE_CLIENT_ID', 'AZURE_CLIENT_SECRET', 'AZURE_TENANT_ID'].includes(k);
                            if (editing.provider === 'gcp') return k !== 'GOOGLE_APPLICATION_CREDENTIALS';
                            return true;
                          })
                          .map(([k, v]) => `${k}=${v}`)
                          .join('\n')}
                        onChange={(e) => {
                          const lines = e.currentTarget.value.split('\n');
                          const customEnv: Record<string, string> = {};
                          lines.forEach(line => {
                            const [key, ...valueParts] = line.split('=');
                            if (key && valueParts.length > 0) {
                              customEnv[key.trim()] = valueParts.join('=').trim();
                            }
                          });
                          // Preserve provider-specific vars
                          const preservedVars: Record<string, string> = {};
                          if (editing.provider === 'aws') {
                            if (editing.env?.AWS_ACCESS_KEY_ID) preservedVars.AWS_ACCESS_KEY_ID = editing.env.AWS_ACCESS_KEY_ID;
                            if (editing.env?.AWS_SECRET_ACCESS_KEY) preservedVars.AWS_SECRET_ACCESS_KEY = editing.env.AWS_SECRET_ACCESS_KEY;
                            if (editing.env?.AWS_DEFAULT_REGION) preservedVars.AWS_DEFAULT_REGION = editing.env.AWS_DEFAULT_REGION;
                          }
                          if (editing.provider === 'azure') {
                            if (editing.env?.AZURE_CLIENT_ID) preservedVars.AZURE_CLIENT_ID = editing.env.AZURE_CLIENT_ID;
                            if (editing.env?.AZURE_CLIENT_SECRET) preservedVars.AZURE_CLIENT_SECRET = editing.env.AZURE_CLIENT_SECRET;
                            if (editing.env?.AZURE_TENANT_ID) preservedVars.AZURE_TENANT_ID = editing.env.AZURE_TENANT_ID;
                          }
                          if (editing.provider === 'gcp' && editing.env?.GOOGLE_APPLICATION_CREDENTIALS) {
                            preservedVars.GOOGLE_APPLICATION_CREDENTIALS = editing.env.GOOGLE_APPLICATION_CREDENTIALS;
                          }
                          setEditing({ ...editing, env: { ...preservedVars, ...customEnv } });
                        }}
                      />
                    </Accordion.Panel>
                  </Accordion.Item>
                </Accordion>
              </Stack>
              
              <Switch label="Enabled" checked={editing.is_enabled !== false} onChange={(e)=> setEditing({ ...editing, is_enabled: e.currentTarget.checked })} />
              <Group justify="flex-end">
                <Button onClick={saveServer}>{editing.id ? 'Save Changes' : 'Create Server'}</Button>
              </Group>
            </Stack>
          )}
        </Modal>
      </Stack>
    </Card>
  );
}
