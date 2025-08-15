/**
 * Chunking & Embedding Page - Full page for chunking and embedding settings
 */

import React from 'react';
import { Stack, Card, Text, Group, NumberInput, Select, Switch, Button, Divider } from '@mantine/core';
import { IconDatabase, IconDeviceFloppy } from '@tabler/icons-react';
import { SettingsPageLayout } from '../../components/layout/SettingsPageLayout';

export const ChunkingEmbeddingPage: React.FC = () => {
  return (
    <SettingsPageLayout
      title="Chunking & Embedding"
      description="Configure document chunking parameters and embedding settings for optimal search and retrieval."
      icon={<IconDatabase size="1.5rem" />}
      breadcrumbText="Chunking & Embedding"
    >
      <Stack gap="xl">
        <Card p="lg" withBorder>
          <Stack gap="lg">
            <Text size="lg" fw={600}>Document Chunking</Text>
            
            <Group grow>
              <NumberInput
                label="Chunk Size"
                description="Number of tokens per chunk"
                defaultValue={1000}
                min={100}
                max={4000}
              />
              <NumberInput
                label="Chunk Overlap"
                description="Overlap between chunks in tokens"
                defaultValue={200}
                min={0}
                max={500}
              />
            </Group>

            <Select
              label="Chunking Strategy"
              description="Method for splitting documents"
              defaultValue="recursive"
              data={[
                { value: 'recursive', label: 'Recursive Character Text Splitter' },
                { value: 'semantic', label: 'Semantic Chunking' },
                { value: 'fixed', label: 'Fixed Size Chunking' },
              ]}
            />

            <Divider />

            <Text size="lg" fw={600}>Embedding Configuration</Text>
            
            <Select
              label="Embedding Model"
              description="Model used for generating embeddings"
              defaultValue="all-MiniLM-L6-v2"
              data={[
                { value: 'all-MiniLM-L6-v2', label: 'all-MiniLM-L6-v2 (384 dim)' },
                { value: 'all-mpnet-base-v2', label: 'all-mpnet-base-v2 (768 dim)' },
                { value: 'text-embedding-ada-002', label: 'OpenAI Ada-002 (1536 dim)' },
              ]}
            />

            <Group justify="space-between">
              <div>
                <Text fw={500}>Enable batch processing</Text>
                <Text size="sm" c="dimmed">Process multiple documents simultaneously</Text>
              </div>
              <Switch defaultChecked />
            </Group>

            <NumberInput
              label="Batch Size"
              description="Number of chunks to process in parallel"
              defaultValue={100}
              min={1}
              max={1000}
            />

            <Group justify="flex-end" mt="lg">
              <Button leftSection={<IconDeviceFloppy size="1rem" />}>
                Save Configuration
              </Button>
            </Group>
          </Stack>
        </Card>
      </Stack>
    </SettingsPageLayout>
  );
};
