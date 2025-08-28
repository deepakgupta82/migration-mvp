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
        </div>

        <div style={{ marginTop: 4 }}>
          <SystemLogsViewer />
        </div>
      </Stack>
    </Container>
  );
};

export default SystemLogsView;
