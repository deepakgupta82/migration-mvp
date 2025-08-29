import React, { useMemo, useEffect, useState } from 'react';
import { useParams, Link, NavLink } from 'react-router-dom';
import { Box, Group, Title, Text, Button, Badge, Card, Grid, Stack, Tabs, SimpleGrid, Loader, Alert } from '@mantine/core';
import { IconTrash, IconRefresh, IconDeviceMobile, IconArrowRight, IconShieldCheck, IconActivity } from '@tabler/icons-react';
import { apiService, Project } from '../../services/api';

type EssentialsField = { label: string; value: string | React.ReactNode };

export const ProjectOverviewPage: React.FC = () => {
  const { projectId } = useParams();

  // Local state for real data
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [project, setProject] = useState<Project | null>(null);
  const [stats, setStats] = useState<any | null>(null);

  const loadData = async () => {
    if (!projectId) return;
    setLoading(true);
    setError(null);
    try {
      const [p, s] = await Promise.all([
        apiService.getProject(projectId),
        apiService.getProjectStats(projectId).catch(() => null),
      ]);
      setProject(p);
      setStats(s);
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

  // TODO: Wire with real project metadata and stats selectors
  const projectName = project?.name || projectId || '—';
  const projectType = 'Migration Project';

  // Normalize stats from either stats-service or websocket-like shapes
  const filesCount = stats?.data?.documents?.total
    ?? stats?.data?.documents_count
    ?? stats?.data?.files_count
    ?? stats?.files_count
    ?? 0;
  const embeddingsCount = stats?.data?.embeddings?.total
    ?? stats?.data?.embeddings_count
    ?? stats?.embeddings_count
    ?? 0;
  const graphNodes = stats?.data?.graph?.nodes
    ?? stats?.data?.graph_nodes
    ?? stats?.graph_nodes
    ?? 0;
  const graphRelationships = stats?.data?.graph?.relationships
    ?? stats?.data?.graph_relationships
    ?? stats?.graph_relationships
    ?? 0;
  const lastUpdated = stats?.data?.last_updated || stats?.last_updated || project?.updated_at;

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

  const tags = [
    `Client: ${project?.client_name || '—'}`,
    `Owner: ${project?.client_contact || '—'}`,
    `Status: ${project?.status || '—'}`,
    `Updated: ${lastUpdated ? new Date(lastUpdated).toLocaleDateString() : '—'}`,
  ];

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
          <Text c="dimmed">{projectType}</Text>
        </div>
        <Group>
          <Button variant="default" leftSection={<IconTrash size={16} />}>Delete</Button>
          <Button variant="default">Move</Button>
          <Button variant="default" leftSection={<IconRefresh size={16} />} onClick={loadData}>Refresh</Button>
          <Button leftSection={<IconDeviceMobile size={16} />}>Open in mobile</Button>
        </Group>
      </Group>

      {/* Essentials */}
      <Card withBorder>
        <Group justify="space-between" mb="md">
          <Title order={4}>Essentials</Title>
        </Group>
        <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md">
          {essentials.map((f) => (
            <div key={f.label}>
              <Text size="xs" c="dimmed" fw={600} tt="uppercase">{f.label}</Text>
              <Text>{f.value}</Text>
            </div>
          ))}
        </SimpleGrid>
        <Group mt="lg" gap="xs">
          {tags.map((t) => (
            <Badge key={t} variant="light" color="blue" radius="sm">{t}</Badge>
          ))}
        </Group>
      </Card>

      {/* Tabs */}
      <Tabs defaultValue="get-started">
        <Tabs.List>
          <Tabs.Tab value="get-started">Get started</Tabs.Tab>
          <Tabs.Tab value="properties">Properties</Tabs.Tab>
          <Tabs.Tab value="monitoring">Monitoring</Tabs.Tab>
          <Tabs.Tab value="tools">Tools + SDKs</Tabs.Tab>
          <Tabs.Tab value="tutorials">Tutorials</Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="get-started" pt="md">
          <Grid>
            <Grid.Col span={{ base: 12, md: 4 }}>
              <Card shadow="sm">
                <Group justify="space-between" mb="xs">
                  <Group gap="xs"><IconShieldCheck size={18} /><Text fw={600}>Control access to key vault</Text></Group>
                </Group>
                <Text c="dimmed" size="sm">
                  Assign access policy and determine whether a given service principal can perform operations on keys, secrets or certificates.
                </Text>
              </Card>
            </Grid.Col>
            <Grid.Col span={{ base: 12, md: 4 }}>
              <Card shadow="sm">
                <Group justify="space-between" mb="xs">
                  <Group gap="xs"><IconActivity size={18} /><Text fw={600}>Enable logging and set up alerts</Text></Group>
                </Group>
                <Text c="dimmed" size="sm">
                  Enable logging to monitor access and performance; configure alerts for key metrics like latency and throttling.
                </Text>
              </Card>
            </Grid.Col>
    <Grid.Col span={{ base: 12, md: 4 }}>
              <Card shadow="sm">
                <Group justify="space-between" mb="xs">
      <Group gap="xs"><IconRefresh size={18} /><Text fw={600}>Turn on recovery options</Text></Group>
                </Group>
                <Text c="dimmed" size="sm">
                  Soft-delete is enabled. Turn on purge protection to guard against manual purging of deleted items.
                </Text>
              </Card>
            </Grid.Col>
          </Grid>
        </Tabs.Panel>

        <Tabs.Panel value="properties" pt="md">
          <Card><Text size="sm" c="dimmed">Properties view coming soon.</Text></Card>
        </Tabs.Panel>
        <Tabs.Panel value="monitoring" pt="md">
          <Card><Text size="sm" c="dimmed">Monitoring charts coming soon.</Text></Card>
        </Tabs.Panel>
        <Tabs.Panel value="tools" pt="md">
          <Card><Text size="sm" c="dimmed">Tools & SDKs coming soon.</Text></Card>
        </Tabs.Panel>
        <Tabs.Panel value="tutorials" pt="md">
          <Card><Text size="sm" c="dimmed">Tutorials coming soon.</Text></Card>
        </Tabs.Panel>
      </Tabs>
    </Stack>
  );
};
