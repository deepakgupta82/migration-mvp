/**
 * Global Document Templates Page - Full page for template settings
 */

import React from 'react';
import { Stack, Card, Text, Group, Button, Table, ActionIcon } from '@mantine/core';
import { IconFileText, IconPlus, IconEdit, IconTrash } from '@tabler/icons-react';
import { SettingsPageLayout } from '../../components/layout/SettingsPageLayout';

export const GlobalDocumentTemplatesPage: React.FC = () => {
  const templates = [
    { name: 'Migration Assessment Report', type: 'PDF', lastModified: '2024-08-10' },
    { name: 'Technical Architecture Document', type: 'DOCX', lastModified: '2024-08-05' },
    { name: 'Risk Analysis Report', type: 'PDF', lastModified: '2024-07-28' },
  ];

  return (
    <SettingsPageLayout
      title="Global Document Templates"
      description="Manage document templates used across the platform for reports, assessments, and documentation."
      icon={<IconFileText size="1.5rem" />}
      breadcrumbText="Global Document Templates"
      actions={
        <Button leftSection={<IconPlus size="1rem" />}>
          Add Template
        </Button>
      }
    >
      <Stack gap="xl">
        <Card p="lg" withBorder>
          <Stack gap="md">
            <Text size="lg" fw={600}>Document Templates</Text>
            <Table>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Template Name</Table.Th>
                  <Table.Th>Type</Table.Th>
                  <Table.Th>Last Modified</Table.Th>
                  <Table.Th>Actions</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {templates.map((template, index) => (
                  <Table.Tr key={index}>
                    <Table.Td>
                      <Text fw={500}>{template.name}</Text>
                    </Table.Td>
                    <Table.Td>{template.type}</Table.Td>
                    <Table.Td>{template.lastModified}</Table.Td>
                    <Table.Td>
                      <Group gap="xs">
                        <ActionIcon variant="light">
                          <IconEdit size="1rem" />
                        </ActionIcon>
                        <ActionIcon variant="light" color="red">
                          <IconTrash size="1rem" />
                        </ActionIcon>
                      </Group>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Stack>
        </Card>
      </Stack>
    </SettingsPageLayout>
  );
};
