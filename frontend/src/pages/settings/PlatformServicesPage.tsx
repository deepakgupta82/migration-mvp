/**
 * Platform Services Page - Full page for platform services settings
 */

import React from 'react';
import { Stack, Card, Text, Group, Badge, Button, ActionIcon } from '@mantine/core';
import { IconServer, IconRefresh, IconPlayerPlay, IconPlayerStop } from '@tabler/icons-react';
import { SettingsPageLayout } from '../../components/layout/SettingsPageLayout';

export const PlatformServicesPage: React.FC = () => {
  const services = [
    { name: 'Backend API', status: 'running', port: '8000', uptime: '2d 4h' },
    { name: 'Project Service', status: 'running', port: '8002', uptime: '2d 4h' },
    { name: 'Reporting Service', status: 'running', port: '8003', uptime: '1d 2h' },
    { name: 'Neo4j Database', status: 'running', port: '7474', uptime: '5d 1h' },
    { name: 'PostgreSQL', status: 'running', port: '5432', uptime: '5d 1h' },
    { name: 'MinIO Storage', status: 'running', port: '9000', uptime: '5d 1h' },
  ];

  return (
    <SettingsPageLayout
      title="Platform Services"
      description="Monitor and manage platform services, check service health, and configure service settings."
      icon={<IconServer size="1.5rem" />}
      breadcrumbText="Platform Services"
    >
      <Stack gap="xl">
        <Card p="lg" withBorder>
          <Stack gap="md">
            <Text size="lg" fw={600}>Service Status</Text>
            {services.map((service, index) => (
              <Group key={index} justify="space-between" p="md" style={{ border: '1px solid #e9ecef', borderRadius: '6px' }}>
                <Group>
                  <div>
                    <Text fw={500}>{service.name}</Text>
                    <Group gap="xs">
                      <Badge color={service.status === 'running' ? 'green' : 'red'}>
                        {service.status.toUpperCase()}
                      </Badge>
                      <Text size="sm" c="dimmed">Port: {service.port}</Text>
                      <Text size="sm" c="dimmed">Uptime: {service.uptime}</Text>
                    </Group>
                  </div>
                </Group>
                <Group>
                  <ActionIcon variant="light" color="blue">
                    <IconRefresh size="1rem" />
                  </ActionIcon>
                  <ActionIcon variant="light" color={service.status === 'running' ? 'red' : 'green'}>
                    {service.status === 'running' ? <IconPlayerStop size="1rem" /> : <IconPlayerPlay size="1rem" />}
                  </ActionIcon>
                </Group>
              </Group>
            ))}
          </Stack>
        </Card>
      </Stack>
    </SettingsPageLayout>
  );
};
