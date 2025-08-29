import React, { useMemo } from 'react';
import { useParams, Link, NavLink } from 'react-router-dom';
import { Box, Group, Title, Text, Button, Badge, Card, Grid, Stack, Tabs, SimpleGrid } from '@mantine/core';
import { IconTrash, IconRefresh, IconDeviceMobile, IconArrowRight, IconShieldCheck, IconActivity, IconRefreshCcw } from '@tabler/icons-react';

type EssentialsField = { label: string; value: string | React.ReactNode };

export const ProjectOverviewPage: React.FC = () => {
  const { projectId } = useParams();

  // TODO: Wire with real project metadata and stats selectors
  const projectName = projectId || 'kv-use-ais-prod-01';
  const projectType = 'Migration Project';

  const essentials: EssentialsField[] = useMemo(() => [
    { label: 'Resource group', value: 'rg-default' },
    { label: 'Location', value: 'East US' },
    { label: 'Subscription', value: 'Default-Account' },
    { label: 'Subscription ID', value: projectId || '—' },
    { label: 'Vault URI', value: 'https://storage.local/minio' },
    { label: 'Sku', value: 'Standard' },
    { label: 'Directory ID', value: '—' },
    { label: 'Directory Name', value: '—' },
    { label: 'Soft-delete', value: 'Enabled' },
    { label: 'Purge protection', value: 'Enabled' },
  ], [projectId]);

  const tags = [
    'Application Group: Migration',
    'Application Name: Ascent',
    'AutoShutDown: No',
    'Business Team: Cloud Practice',
    'Deployment Date: 29 Mar 2025',
  ];

  return (
    <Stack gap="xl">
      {/* Header */}
      <Group justify="space-between" align="flex-start">
        <div>
          <Title order={2} fw={700}>{projectName}</Title>
          <Text c="dimmed">{projectType}</Text>
        </div>
        <Group>
          <Button variant="default" leftSection={<IconTrash size={16} />}>Delete</Button>
          <Button variant="default">Move</Button>
          <Button variant="default" leftSection={<IconRefresh size={16} />}>Refresh</Button>
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
                  <Group gap="xs"><IconRefreshCcw size={18} /><Text fw={600}>Turn on recovery options</Text></Group>
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
