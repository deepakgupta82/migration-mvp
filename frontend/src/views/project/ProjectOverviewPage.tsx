import React, { useMemo, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Group, Title, Text, Button, Badge, Card, SimpleGrid, Loader, Alert, Collapse, ActionIcon, Stack } from '@mantine/core';
import { IconTrash, IconRefresh, IconChevronRight, IconChevronDown } from '@tabler/icons-react';
import { apiService, Project } from '../../services/api';
import { useProjectStats } from '../../hooks/useStatsWebSocket';

type EssentialsField = { label: string; value: string | React.ReactNode };

export const ProjectOverviewPage: React.FC = () => {
  const { projectId } = useParams();

  // Local state for real data
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [project, setProject] = useState<Project | null>(null);
  const [stats, setStats] = useState<any | null>(null);
  const [statsOpen, setStatsOpen] = useState<boolean>(true);

  const loadData = async () => {
    if (!projectId) return;
    setLoading(true);
    setError(null);
    try {
  const p = await apiService.getProject(projectId);
  setProject(p);
    } catch (e: any) {
      setError(e?.message || 'Failed to load project overview');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (projectId) {
      loadData();
    }
  }, [projectId]);

  const projectName = project?.name || projectId || '—';
  // Live stats via WebSocket (fallback already inside the hook)
  const { stats: wsStats, refreshStats } = useProjectStats(projectId || '');
  useEffect(() => {
    if (wsStats) setStats(wsStats);
  }, [wsStats]);

  // Normalize stats from either stats-service or websocket-like shapes
  const filesCount = (stats?.files_count) ?? stats?.data?.files_count ?? stats?.data?.documents?.total ?? 0;
  const embeddingsCount = (stats?.embeddings_count) ?? stats?.data?.embeddings_count ?? stats?.data?.embeddings?.total ?? 0;
  const graphNodes = (stats?.graph_nodes) ?? stats?.data?.graph_nodes ?? stats?.data?.graph?.nodes ?? 0;
  const graphRelationships = (stats?.graph_relationships) ?? stats?.data?.graph_relationships ?? stats?.data?.graph?.relationships ?? 0;
  const lastUpdated = stats?.last_updated || stats?.data?.last_updated || project?.updated_at;

  const essentials: EssentialsField[] = useMemo(() => [
    { label: 'Client', value: project?.client_name || '—' },
    { label: 'Status', value: project?.status || '—' },
    { label: 'Files', value: String(filesCount) },
    { label: 'Embeddings', value: String(embeddingsCount) },
    { label: 'Graph nodes', value: String(graphNodes) },
    { label: 'Graph edges', value: String(graphRelationships) },
    { label: 'Created', value: project?.created_at ? new Date(project.created_at).toLocaleString() : '—' },
    { label: 'Updated', value: lastUpdated ? new Date(lastUpdated).toLocaleString() : '—' },
    { label: 'Project ID', value: project?.id || projectId || '—' },
    { label: 'Description', value: project?.description || '—' },
  ], [project, filesCount, embeddingsCount, graphNodes, graphRelationships, lastUpdated, projectId]);

  return (
    <Stack gap="xl">
      {loading && (
        <Group justify="center" p="md"><Loader /></Group>
      )}
      {error && (
        <Alert color="red" title="Failed to load overview">{error}</Alert>
      )}
      {/* Header */}
      <Group justify="space-between" align="flex-start">
        <div>
          <Title order={2} fw={700}>{projectName}</Title>
        </div>
        <Group>
          <Button variant="default" leftSection={<IconTrash size={16} />}>Delete</Button>
          <Button variant="default" leftSection={<IconRefresh size={16} />} onClick={() => { refreshStats(); loadData(); }}>Refresh</Button>
        </Group>
      </Group>

      {/* Stats (collapsible) */}
      <Card withBorder>
        <Group justify="space-between" mb="sm" align="center">
          <Group gap="xs" align="center" onClick={() => setStatsOpen((s) => !s)} style={{ cursor: 'pointer' }}>
            <ActionIcon variant="subtle" size="sm">
              {statsOpen ? <IconChevronDown size={16} /> : <IconChevronRight size={16} />}
            </ActionIcon>
            <Title order={4} m={0}>Stats</Title>
          </Group>
        </Group>
        <Collapse in={statsOpen}>
          <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md">
            {essentials.map((f) => (
              <div key={f.label}>
                <Text size="xs" c="dimmed" fw={600} tt="uppercase">{f.label}</Text>
                <Text>{f.value}</Text>
              </div>
            ))}
          </SimpleGrid>
        </Collapse>
      </Card>

    </Stack>
  );
};
