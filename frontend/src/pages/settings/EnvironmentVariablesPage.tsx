/**
 * Environment Variables Page - Full page for environment settings
 */

import React from 'react';
import { Stack, Card, Text, Group, Button, TextInput, PasswordInput, Badge } from '@mantine/core';
import { IconSettings, IconPlus, IconEdit } from '@tabler/icons-react';
import { SettingsPageLayout } from '../../components/layout/SettingsPageLayout';

export const EnvironmentVariablesPage: React.FC = () => {
  const envVars = [
    { key: 'OPENAI_API_KEY', value: '••••••••••••••••', category: 'AI Services' },
    { key: 'DATABASE_URL', value: 'postgresql://localhost:5432/db', category: 'Database' },
    { key: 'REDIS_URL', value: 'redis://localhost:6379', category: 'Cache' },
  ];

  return (
    <SettingsPageLayout
      title="Environment Variables"
      description="Manage environment variables, API keys, and configuration settings for the platform."
      icon={<IconSettings size="1.5rem" />}
      breadcrumbText="Environment Variables"
      actions={
        <Button leftSection={<IconPlus size="1rem" />}>
          Add Variable
        </Button>
      }
    >
      <Stack gap="xl">
        <Card p="lg" withBorder>
          <Stack gap="md">
            <Text size="lg" fw={600}>Environment Variables</Text>
            {envVars.map((envVar, index) => (
              <Group key={index} justify="space-between" p="sm" style={{ border: '1px solid #e9ecef', borderRadius: '6px' }}>
                <Group>
                  <div>
                    <Text fw={500}>{envVar.key}</Text>
                    <Badge size="sm" variant="light">{envVar.category}</Badge>
                  </div>
                </Group>
                <Group>
                  <Text size="sm" c="dimmed">{envVar.value}</Text>
                  <Button size="xs" variant="light" leftSection={<IconEdit size="0.8rem" />}>
                    Edit
                  </Button>
                </Group>
              </Group>
            ))}
          </Stack>
        </Card>
      </Stack>
    </SettingsPageLayout>
  );
};
