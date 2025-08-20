import React from 'react';
import { Container, Title, Text, Stack } from '@mantine/core';
import SystemLogsViewer from '../components/admin/SystemLogsViewer';

export const SystemLogsView: React.FC = () => {
  return (
    <Container size="100%" px={8} py={6}>
      <Stack gap={6}>
        <div style={{ marginBottom: 4 }}>
          <Title order={1} size="h2" mb={2}>
            System Logs & Monitoring
          </Title>
          <Text size="sm" c="dimmed" style={{ marginTop: 2 }}>
            Real-time monitoring and logging for all platform services, containers, and agent activities. Monitor system health, stream logs, and track performance metrics across the entire infrastructure.
          </Text>
        </div>

        <div style={{ marginTop: 4 }}>
          <SystemLogsViewer />
        </div>
      </Stack>
    </Container>
  );
};

export default SystemLogsView;
