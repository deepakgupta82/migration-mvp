/**
 * Knowledge Base Page - Full page for knowledge base settings
 */

import React from 'react';
import { Stack, Card, Text, Switch, Group, Button, Divider } from '@mantine/core';
import { IconMessage, IconDatabase, IconRefresh } from '@tabler/icons-react';
import { SettingsPageLayout } from '../../components/layout/SettingsPageLayout';

export const KnowledgeBasePage: React.FC = () => {
  return (
    <SettingsPageLayout
      title="Knowledge Base"
      description="Configure knowledge base settings, document indexing, and search capabilities."
      icon={<IconMessage size="1.5rem" />}
      breadcrumbText="Knowledge Base"
    >
      <Stack gap="xl">
        <Card p="lg" withBorder>
          <Stack gap="md">
            <Text size="lg" fw={600}>Document Processing</Text>
            <Group justify="space-between">
              <div>
                <Text fw={500}>Auto-index new documents</Text>
                <Text size="sm" c="dimmed">Automatically process uploaded documents</Text>
              </div>
              <Switch defaultChecked />
            </Group>
            <Divider />
            <Group justify="space-between">
              <div>
                <Text fw={500}>Enable semantic search</Text>
                <Text size="sm" c="dimmed">Use AI-powered semantic search</Text>
              </div>
              <Switch defaultChecked />
            </Group>
          </Stack>
        </Card>
      </Stack>
    </SettingsPageLayout>
  );
};
