import React from 'react';
import { Container, Title, Text, Stack } from '@mantine/core';
import SystemLogsViewer from '../components/admin/SystemLogsViewer';

export const SystemLogsView: React.FC = () => {
  return (
    <Container size="xl" py="md">
      <Stack gap="lg">
        <div>
          <Title order={1} size="h2" mb="xs">
            System Logs & Monitoring
          </Title>
          <Text size="sm" c="dimmed">
            Real-time monitoring and logging for all platform services, containers, and agent activities.
            Monitor system health, stream logs, and track performance metrics across the entire infrastructure.
          </Text>
        </div>
        
        <SystemLogsViewer />
      </Stack>
    </Container>
  );
};

export default SystemLogsView;
