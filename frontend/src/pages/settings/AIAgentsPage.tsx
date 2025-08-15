/**
 * AI Agents Page - Full page for AI agents settings
 */

import React from 'react';
import { Stack, Card, Text, Group, Badge, Button, Switch } from '@mantine/core';
import { IconBrain, IconPlus, IconSettings } from '@tabler/icons-react';
import { SettingsPageLayout } from '../../components/layout/SettingsPageLayout';

export const AIAgentsPage: React.FC = () => {
  const agents = [
    { name: 'Research Agent', status: 'active', role: 'Document Analysis' },
    { name: 'Content Architect', status: 'active', role: 'Content Generation' },
    { name: 'Quality Reviewer', status: 'active', role: 'Content Review' },
    { name: 'Infrastructure Analyst', status: 'inactive', role: 'System Analysis' },
  ];

  return (
    <SettingsPageLayout
      title="AI Agents"
      description="Configure and manage AI agents, their roles, and capabilities within the platform."
      icon={<IconBrain size="1.5rem" />}
      breadcrumbText="AI Agents"
      actions={
        <Button leftSection={<IconPlus size="1rem" />}>
          Create Agent
        </Button>
      }
    >
      <Stack gap="xl">
        <Card p="lg" withBorder>
          <Stack gap="md">
            <Text size="lg" fw={600}>Active AI Agents</Text>
            {agents.map((agent, index) => (
              <Group key={index} justify="space-between" p="md" style={{ border: '1px solid #e9ecef', borderRadius: '6px' }}>
                <Group>
                  <div>
                    <Text fw={500}>{agent.name}</Text>
                    <Group gap="xs">
                      <Badge color={agent.status === 'active' ? 'green' : 'gray'}>
                        {agent.status.toUpperCase()}
                      </Badge>
                      <Text size="sm" c="dimmed">{agent.role}</Text>
                    </Group>
                  </div>
                </Group>
                <Group>
                  <Switch checked={agent.status === 'active'} />
                  <Button size="xs" variant="light" leftSection={<IconSettings size="0.8rem" />}>
                    Configure
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
