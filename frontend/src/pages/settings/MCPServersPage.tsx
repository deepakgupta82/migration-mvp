import React from 'react';
import { Card, Stack, Group, Text, Divider } from '@mantine/core';
import MCPServersPanel from '../../components/settings/MCPServersPanel';

export const MCPServersPage: React.FC = () => {
  return (
    <Stack>
      <Card>
        <Stack gap="md">
          <Group justify="space-between">
            <div>
              <Text size="lg" fw={600}>MCP Servers</Text>
              <Text size="sm" c="dimmed">Register and manage AWS/Azure/GCP MCP servers; discover tools for CrewAI and AutoGen agents.</Text>
            </div>
          </Group>
          <Divider />
          <MCPServersPanel />
        </Stack>
      </Card>
    </Stack>
  );
};

export default MCPServersPage;
