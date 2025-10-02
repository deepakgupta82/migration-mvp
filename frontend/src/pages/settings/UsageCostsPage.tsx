import React, { useEffect, useMemo, useState } from 'react';
import { Button, Group, Stack, Text, TextInput, Title, Table, Badge, NumberInput, Loader, Card, Grid, Tooltip } from '@mantine/core';
import { IconCash, IconFilter, IconRefresh, IconActivity, IconListDetails } from '@tabler/icons-react';
import { SettingsPageLayout } from '../../components/layout/SettingsPageLayout';
import api, { AgentEvent, AgentRun, LLMCall } from '../../services/api';

const formatCents = (cents?: number) => typeof cents === 'number' ? `$${(cents / 100).toFixed(4)}` : '-';
const fmt = (n?: number) => typeof n === 'number' ? n.toLocaleString() : '-';

export const UsageCostsPage: React.FC = () => {
  const [projectId, setProjectId] = useState<string>('');
  const [provider, setProvider] = useState<string>('');
  const [model, setModel] = useState<string>('');
  const [correlationId, setCorrelationId] = useState<string>('');
  const [limit, setLimit] = useState<number>(50);
  const [offset, setOffset] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(false);
  const [llmCalls, setLlmCalls] = useState<LLMCall[]>([]);
  const [agentRuns, setAgentRuns] = useState<AgentRun[]>([]);
  const [agentEvents, setAgentEvents] = useState<AgentEvent[]>([]);
  const [page, setPage] = useState<number>(1);

  const fetchAll = async () => {
    setLoading(true);
    try {
      const [llms, runs] = await Promise.all([
        api.listLLMCalls({ project_id: projectId || undefined, provider: provider || undefined, model: model || undefined, correlation_id: correlationId || undefined, limit, offset }) as unknown as Promise<LLMCall[]>,
        api.listAgentRuns({ project_id: projectId || undefined, correlation_id: correlationId || undefined, limit, offset }) as unknown as Promise<AgentRun[]>,
      ]);

      setLlmCalls(Array.isArray(llms) ? llms : (llms as any).items || []);
      setAgentRuns(Array.isArray(runs) ? runs : (runs as any).items || []);

      // If a single run is selected (by correlation), fetch its events
      if (correlationId) {
        const runId = (Array.isArray(runs) ? runs : (runs as any).items || [])[0]?.run_id;
        const events = await api.listAgentEvents({ correlation_id: correlationId, run_id: runId, limit: 200, offset: 0 }) as unknown as AgentEvent[];
        setAgentEvents(Array.isArray(events) ? events : (events as any).items || []);
      } else {
        setAgentEvents([]);
      }
    } catch (e) {
      console.error('Failed to fetch usage data', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const totals = useMemo(() => {
    const tokensIn = llmCalls.reduce((a, c) => a + (c.prompt_tokens || 0), 0);
    const tokensOut = llmCalls.reduce((a, c) => a + (c.completion_tokens || 0), 0);
    const tokensTotal = llmCalls.reduce((a, c) => a + (c.total_tokens || ((c.prompt_tokens || 0) + (c.completion_tokens || 0))), 0);
    const costCents = llmCalls.reduce((a, c) => a + (c.cost_usd_cents || 0), 0);
    return { tokensIn, tokensOut, tokensTotal, costCents };
  }, [llmCalls]);

  const onApplyFilters = () => {
    setOffset((page - 1) * limit);
    fetchAll();
  };

  const onReset = () => {
    setProjectId('');
    setProvider('');
    setModel('');
    setCorrelationId('');
    setLimit(50);
    setOffset(0);
    setPage(1);
    fetchAll();
  };

  return (
    <SettingsPageLayout
      title="Usage & Costs"
      description="Track LLM calls and AI Agent runs with token usage, durations, and costs aggregated by project and correlation ID."
      icon={<IconCash size="1.5rem" />}
      breadcrumbText="Usage & Costs"
      actions={
        <Group gap="xs">
          <Button variant="light" leftSection={<IconRefresh size={16} />} size="sm" onClick={fetchAll}>Refresh</Button>
        </Group>
      }
    >
      <Stack gap="md">
        {/* Filters */}
        <Card withBorder>
          <Group align="end" wrap="wrap" gap="md">
            <TextInput label="Project ID" placeholder="uuid..." value={projectId} onChange={(e) => setProjectId(e.currentTarget.value)} style={{ minWidth: 260 }} />
            <TextInput label="Provider" placeholder="openai, azure, ..." value={provider} onChange={(e) => setProvider(e.currentTarget.value)} style={{ minWidth: 180 }} />
            <TextInput label="Model" placeholder="gpt-4o-mini, ..." value={model} onChange={(e) => setModel(e.currentTarget.value)} style={{ minWidth: 220 }} />
            <TextInput label="Correlation ID" placeholder="trace id" value={correlationId} onChange={(e) => setCorrelationId(e.currentTarget.value)} style={{ minWidth: 260 }} />
            <NumberInput label="Limit" min={1} max={500} value={limit} onChange={(v) => setLimit(Number(v) || 50)} style={{ width: 120 }} />
            <Group gap="xs">
              <Button leftSection={<IconFilter size={16} />} onClick={onApplyFilters}>Apply</Button>
              <Button variant="subtle" onClick={onReset}>Reset</Button>
            </Group>
          </Group>
        </Card>

        {/* Aggregates */}
        <Grid>
          <Grid.Col span={{ base: 12, sm: 6, md: 3 }}>
            <Card withBorder>
              <Text size="sm" c="dimmed">Prompt tokens</Text>
              <Title order={3}>{fmt(totals.tokensIn)}</Title>
            </Card>
          </Grid.Col>
          <Grid.Col span={{ base: 12, sm: 6, md: 3 }}>
            <Card withBorder>
              <Text size="sm" c="dimmed">Completion tokens</Text>
              <Title order={3}>{fmt(totals.tokensOut)}</Title>
            </Card>
          </Grid.Col>
          <Grid.Col span={{ base: 12, sm: 6, md: 3 }}>
            <Card withBorder>
              <Text size="sm" c="dimmed">Total tokens</Text>
              <Title order={3}>{fmt(totals.tokensTotal)}</Title>
            </Card>
          </Grid.Col>
          <Grid.Col span={{ base: 12, sm: 6, md: 3 }}>
            <Card withBorder>
              <Text size="sm" c="dimmed">Estimated cost</Text>
              <Title order={3}>{formatCents(totals.costCents)}</Title>
            </Card>
          </Grid.Col>
        </Grid>

        {loading ? (
          <Group justify="center" p="lg"><Loader /></Group>
        ) : (
          <Stack gap="lg">
            {/* LLM Calls table */}
            <Stack gap="xs">
              <Group>
                <IconActivity size={18} />
                <Title order={4}>LLM Calls</Title>
              </Group>
              <Table highlightOnHover withRowBorders={false} striped stickyHeader>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>Time</Table.Th>
                    <Table.Th>Provider</Table.Th>
                    <Table.Th>Model</Table.Th>
                    <Table.Th>Prompt</Table.Th>
                    <Table.Th>Completion</Table.Th>
                    <Table.Th>Total</Table.Th>
                    <Table.Th>Cost</Table.Th>
                    <Table.Th>Status</Table.Th>
                    <Table.Th>Correlation</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {llmCalls.map((c, idx) => (
                    <Table.Tr key={c.id || idx}>
                      <Table.Td>{c.created_at ? new Date(c.created_at).toLocaleString() : '-'}</Table.Td>
                      <Table.Td>{c.provider || '-'}</Table.Td>
                      <Table.Td>{c.model || '-'}</Table.Td>
                      <Table.Td>{fmt(c.prompt_tokens)}</Table.Td>
                      <Table.Td>{fmt(c.completion_tokens)}</Table.Td>
                      <Table.Td>{fmt(c.total_tokens)}</Table.Td>
                      <Table.Td>{formatCents(c.cost_usd_cents)}</Table.Td>
                      <Table.Td>
                        <Badge variant="light" color={c.status === 'success' ? 'green' : (c.status === 'error' ? 'red' : 'gray')}>
                          {c.status || 'unknown'}
                        </Badge>
                      </Table.Td>
                      <Table.Td>
                        <Tooltip label={c.correlation_id || ''}>
                          <Text size="sm" style={{ maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis' }}>{c.correlation_id || '-'}</Text>
                        </Tooltip>
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </Stack>

            {/* Agent Runs table */}
            <Stack gap="xs">
              <Group>
                <IconListDetails size={18} />
                <Title order={4}>Agent Runs</Title>
              </Group>
              <Table highlightOnHover withRowBorders={false} striped stickyHeader>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>Run ID</Table.Th>
                    <Table.Th>Agent</Table.Th>
                    <Table.Th>Status</Table.Th>
                    <Table.Th>Started</Table.Th>
                    <Table.Th>Completed</Table.Th>
                    <Table.Th>Duration</Table.Th>
                    <Table.Th>Correlation</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {agentRuns.map((r, idx) => (
                    <Table.Tr key={r.id || r.run_id || idx}>
                      <Table.Td>{r.run_id || '-'}</Table.Td>
                      <Table.Td>{r.agent_name || '-'}</Table.Td>
                      <Table.Td>
                        <Badge variant="light" color={r.status === 'completed' ? 'green' : (r.status === 'failed' ? 'red' : 'yellow')}>
                          {r.status || 'unknown'}
                        </Badge>
                      </Table.Td>
                      <Table.Td>{r.started_at ? new Date(r.started_at).toLocaleString() : '-'}</Table.Td>
                      <Table.Td>{r.completed_at ? new Date(r.completed_at).toLocaleString() : '-'}</Table.Td>
                      <Table.Td>{typeof r.duration_ms === 'number' ? `${r.duration_ms} ms` : '-'}</Table.Td>
                      <Table.Td>
                        <Tooltip label={r.correlation_id || ''}>
                          <Text size="sm" style={{ maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.correlation_id || '-'}</Text>
                        </Tooltip>
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </Stack>

            {/* Agent Events table (when filtered by correlation) */}
            {!!agentEvents.length && (
              <Stack gap="xs">
                <Group>
                  <IconListDetails size={18} />
                  <Title order={5}>Agent Events</Title>
                </Group>
                <Table highlightOnHover withRowBorders={false} striped stickyHeader>
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th>Time</Table.Th>
                      <Table.Th>Type</Table.Th>
                      <Table.Th>Message</Table.Th>
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {agentEvents.map((e, idx) => (
                      <Table.Tr key={e.id || idx}>
                        <Table.Td>{e.ts ? new Date(e.ts).toLocaleString() : '-'}</Table.Td>
                        <Table.Td>{e.event_type || '-'}</Table.Td>
                        <Table.Td>
                          <Text size="sm" style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 720 }}>
                            {e.message || JSON.stringify(e.meta || {})}
                          </Text>
                        </Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              </Stack>
            )}
          </Stack>
        )}
      </Stack>
    </SettingsPageLayout>
  );
};

export default UsageCostsPage;
