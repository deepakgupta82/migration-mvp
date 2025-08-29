import React from 'react';
import { Title, Text, Card, Stack } from '@mantine/core';

export const ProjectPlaceholderPage: React.FC<{ title: string; subtitle?: string }> = ({ title, subtitle }) => {
  return (
    <Stack gap="md">
      <Title order={2}>{title}</Title>
      {subtitle && <Text c="dimmed">{subtitle}</Text>}
      <Card>
        <Text size="sm" c="dimmed">
          This section is scaffolded and will be wired to data sources next. If you expected data here, it may depend on a service that isn't configured yet.
        </Text>
      </Card>
    </Stack>
  );
};
