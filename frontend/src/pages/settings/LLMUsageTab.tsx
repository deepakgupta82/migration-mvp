/**
 * LLM Usage Tab - Project-level usage tracking with optimized layout
 */

import React, { useEffect, useMemo, useState } from 'react';
import { Button, Group, Stack, Text, TextInput, Title, Table, Badge, NumberInput, Loader, Card, Grid, Tooltip, ActionIcon, Modal, Code, ScrollArea } from '@mantine/core';
import { IconRefresh, IconActivity, IconCopy, IconEye } from '@tabler/icons-react';
import api, { LLMCall } from '../../services/api';

const formatCents = (cents?: number) => typeof cents === 'number' ? `$${(cents / 100).toFixed(4)}` : '-';
const fmt = (n?: number) => typeof n === 'number' ? n.toLocaleString() : '-';

export const LLMUsageTab: React.FC = () => {
  const [projectId, setProjectId] = useState<string>('');
  const [model, setModel] = useState<string>('');
  const [correlationId, setCorrelationId] = useState<string>('');
  const [limit, setLimit] = useState<number>(50);
  const [offset, setOffset] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(false);
  const [llmCalls, setLlmCalls] = useState<LLMCall[]>([]);
  
  // Modal for viewing prompt/response
  const [viewModalOpen, setViewModalOpen] = useState(false);
  const [selectedCall, setSelectedCall] = useState<LLMCall | null>(null);

  const fetchLLMCalls = async () => {
    setLoading(true);
    try {
      const llms = await api.listLLMCalls({ 
        project_id: projectId || undefined, 
        model: model || undefined, 
        correlation_id: correlationId || undefined, 
        limit, 
        offset 
      }) as unknown as LLMCall[];

      setLlmCalls(Array.isArray(llms) ? llms : (llms as any).items || []);
    } catch (e) {
      console.error('Failed to fetch LLM usage data', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLLMCalls();
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
    fetchLLMCalls();
  };

  const onReset = () => {
    setProjectId('');
    setModel('');
    setCorrelationId('');
    setLimit(50);
    setOffset(0);
    fetchLLMCalls();
  };

  const handleViewDetails = (call: LLMCall) => {
    setSelectedCall(call);
    setViewModalOpen(true);
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  return (
    <Stack gap="md">
      {/* Single-line filters - optimized for project-level usage */}
      <Card withBorder p="xs">
        <Group gap="xs" wrap="nowrap" align="end">
          <TextInput 
            label="Project ID" 
            placeholder="uuid..." 
            value={projectId} 
            onChange={(e) => setProjectId(e.currentTarget.value)} 
            style={{ flex: '1 1 220px', minWidth: 180 }} 
            size="xs"
          />
          <TextInput 
            label="Model" 
            placeholder="gpt-4o, gemini..." 
            value={model} 
            onChange={(e) => setModel(e.currentTarget.value)} 
            style={{ flex: '1 1 180px', minWidth: 140 }} 
            size="xs"
          />
          <TextInput 
            label="Correlation ID" 
            placeholder="trace id" 
            value={correlationId} 
            onChange={(e) => setCorrelationId(e.currentTarget.value)} 
            style={{ flex: '1 1 220px', minWidth: 180 }} 
            size="xs"
          />
          <NumberInput 
            label="Limit" 
            min={1} 
            max={500} 
            value={limit} 
            onChange={(v) => setLimit(Number(v) || 50)} 
            style={{ width: 90 }} 
            size="xs"
          />
          <Button size="xs" onClick={onApplyFilters} style={{ height: 26 }}>Apply</Button>
          <Button size="xs" variant="subtle" onClick={onReset} style={{ height: 26 }}>Reset</Button>
          <Button size="xs" variant="light" leftSection={<IconRefresh size={14} />} onClick={fetchLLMCalls} style={{ height: 26 }}>
            Refresh
          </Button>
        </Group>
      </Card>

      {/* Token aggregates */}
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
                <Table.Th>Actions</Table.Th>
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
                  <Table.Td>
                    <Tooltip label="View prompt & response">
                      <ActionIcon 
                        variant="subtle" 
                        size="sm" 
                        onClick={() => handleViewDetails(c)}
                        disabled={!c.prompt_text && !c.response_text}
                      >
                        <IconEye size={16} />
                      </ActionIcon>
                    </Tooltip>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Stack>
      )}

      {/* Modal for viewing prompt/response details */}
      <Modal
        opened={viewModalOpen}
        onClose={() => setViewModalOpen(false)}
        title="LLM Call Details"
        size="xl"
      >
        {selectedCall && (
          <Stack gap="md">
            {/* Call metadata */}
            <Group gap="md">
              <Badge variant="light">{selectedCall.provider || 'unknown'}</Badge>
              <Badge variant="outline">{selectedCall.model || 'unknown'}</Badge>
              <Badge variant="light" color={selectedCall.status === 'success' ? 'green' : 'red'}>
                {selectedCall.status || 'unknown'}
              </Badge>
            </Group>

            {/* Prompt section */}
            {selectedCall.prompt_text && (
              <Stack gap="xs">
                <Group justify="space-between">
                  <Text fw={600} size="sm">Prompt ({fmt(selectedCall.prompt_tokens)} tokens)</Text>
                  <ActionIcon 
                    variant="subtle" 
                    size="sm" 
                    onClick={() => copyToClipboard(selectedCall.prompt_text || '')}
                  >
                    <IconCopy size={14} />
                  </ActionIcon>
                </Group>
                <ScrollArea h={200} style={{ border: '1px solid var(--mantine-color-gray-3)', borderRadius: 4 }}>
                  <Code block style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                    {selectedCall.prompt_text}
                  </Code>
                </ScrollArea>
              </Stack>
            )}

            {/* Response section */}
            {selectedCall.response_text && (
              <Stack gap="xs">
                <Group justify="space-between">
                  <Text fw={600} size="sm">Response ({fmt(selectedCall.completion_tokens)} tokens)</Text>
                  <ActionIcon 
                    variant="subtle" 
                    size="sm" 
                    onClick={() => copyToClipboard(selectedCall.response_text || '')}
                  >
                    <IconCopy size={14} />
                  </ActionIcon>
                </Group>
                <ScrollArea h={300} style={{ border: '1px solid var(--mantine-color-gray-3)', borderRadius: 4 }}>
                  <Code block style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                    {selectedCall.response_text}
                  </Code>
                </ScrollArea>
              </Stack>
            )}

            {/* Metadata */}
            <Group gap="md">
              <Text size="sm" c="dimmed">Duration: {selectedCall.duration_ms ? `${selectedCall.duration_ms}ms` : '-'}</Text>
              <Text size="sm" c="dimmed">Cost: {formatCents(selectedCall.cost_usd_cents)}</Text>
              {selectedCall.created_at && (
                <Text size="sm" c="dimmed">Time: {new Date(selectedCall.created_at).toLocaleString()}</Text>
              )}
            </Group>
          </Stack>
        )}
      </Modal>
    </Stack>
  );
};

export default LLMUsageTab;
