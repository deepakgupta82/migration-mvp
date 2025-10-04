import React, { useState, useEffect, useCallback } from 'react';
import { Modal, ScrollArea, Text, Loader, Alert, Group, Badge } from '@mantine/core';
import { IconAlertCircle, IconFileText } from '@tabler/icons-react';
import ReactMarkdown from 'react-markdown';

interface FactsViewerModalProps {
  opened: boolean;
  onClose: () => void;
  projectId: string;
  filename: string;
}

interface StructuredFacts {
  formatted_facts: string;
  fact_count: number;
  categories: Record<string, number>;
  generated_at: string;
  cached?: boolean;
}

const FactsViewerModal: React.FC<FactsViewerModalProps> = ({
  opened,
  onClose,
  projectId,
  filename,
}) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [factsData, setFactsData] = useState<StructuredFacts | null>(null);

  const fetchFacts = useCallback(async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch(
        `/api/graphs/projects/${projectId}/documents/${filename}/facts/structured`,
        {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token') || ''}`,
          },
        }
      );

      if (!response.ok) {
        throw new Error(`Failed to fetch facts: ${response.statusText}`);
      }

      const data: StructuredFacts = await response.json();
      setFactsData(data);
    } catch (err: any) {
      console.error('Error fetching facts:', err);
      setError(err.message || 'Failed to fetch facts');
    } finally {
      setLoading(false);
    }
  }, [projectId, filename]);

  useEffect(() => {
    if (opened && projectId && filename) {
      fetchFacts();
    }
  }, [opened, projectId, filename, fetchFacts]);

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={
        <Group gap="sm">
          <IconFileText size={20} />
          <Text fw={600}>Extracted Facts: {filename}</Text>
        </Group>
      }
      size="xl"
      padding="lg"
    >
      {loading && (
        <Group justify="center" p="xl">
          <Loader size="lg" />
          <Text c="dimmed">Loading facts...</Text>
        </Group>
      )}

      {error && (
        <Alert icon={<IconAlertCircle size={16} />} color="red" mb="md">
          {error}
        </Alert>
      )}

      {factsData && !loading && (
        <>
          {/* Header with metadata */}
          <Group gap="md" mb="md">
            <Badge color="blue" variant="light">
              {factsData.fact_count} {factsData.fact_count === 1 ? 'fact' : 'facts'}
            </Badge>
            {factsData.cached && (
              <Badge color="green" variant="light">
                Cached
              </Badge>
            )}
            <Text size="xs" c="dimmed">
              Generated: {new Date(factsData.generated_at).toLocaleString()}
            </Text>
          </Group>

          {/* Categories breakdown */}
          {factsData.categories && Object.keys(factsData.categories).length > 0 && (
            <Group gap="xs" mb="md">
              {Object.entries(factsData.categories).map(([category, count]) => (
                <Badge key={category} color="gray" variant="outline" size="sm">
                  {category}: {count}
                </Badge>
              ))}
            </Group>
          )}

          {/* Formatted facts content */}
          <ScrollArea h={600} type="scroll">
            <div
              style={{
                padding: '1rem',
                backgroundColor: 'var(--mantine-color-gray-0)',
                borderRadius: '8px',
              }}
            >
              <ReactMarkdown
                components={{
                  h1: ({ node, ...props }) => (
                    <Text
                      component="h1"
                      size="xl"
                      fw={700}
                      mb="md"
                      mt="lg"
                      {...props}
                    />
                  ),
                  h2: ({ node, ...props }) => (
                    <Text
                      component="h2"
                      size="lg"
                      fw={600}
                      mb="sm"
                      mt="md"
                      {...props}
                    />
                  ),
                  h3: ({ node, ...props }) => (
                    <Text
                      component="h3"
                      size="md"
                      fw={600}
                      mb="xs"
                      mt="sm"
                      {...props}
                    />
                  ),
                  ul: ({ node, ...props }) => (
                    <ul style={{ marginLeft: '1.5rem', marginBottom: '0.5rem' }} {...props} />
                  ),
                  li: ({ node, ...props }) => {
                    // eslint-disable-next-line @typescript-eslint/no-unused-vars
                    const { children, ...restProps } = props;
                    return (
                      <li style={{ marginBottom: '0.25rem' }}>
                        <Text size="sm" component="span">{children}</Text>
                      </li>
                    );
                  },
                  p: ({ node, ...props }) => (
                    <Text size="sm" mb="xs" {...props} />
                  ),
                  strong: ({ node, ...props }) => (
                    <Text component="strong" fw={600} {...props} />
                  ),
                }}
              >
                {factsData.formatted_facts}
              </ReactMarkdown>
            </div>
          </ScrollArea>
        </>
      )}

      {!loading && !error && !factsData && (
        <Alert color="yellow" icon={<IconAlertCircle size={16} />}>
          No facts available for this document. Please ensure the document has been processed.
        </Alert>
      )}
    </Modal>
  );
};

export default FactsViewerModal;
