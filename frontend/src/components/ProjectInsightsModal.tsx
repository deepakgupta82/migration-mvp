import React, { useState } from 'react';
import { Modal, ScrollArea, Text, Loader, Alert, Group, Badge, Button } from '@mantine/core';
import { IconAlertCircle, IconBrain, IconRefresh } from '@tabler/icons-react';
import ReactMarkdown from 'react-markdown';

interface ProjectInsightsModalProps {
  opened: boolean;
  onClose: () => void;
  projectId: string;
  projectName?: string;
}

interface ProjectInsights {
  insights: string;
  line_count: number;
  document_count: number;
  generated_at: string;
}

const ProjectInsightsModal: React.FC<ProjectInsightsModalProps> = ({
  opened,
  onClose,
  projectId,
  projectName,
}) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [insightsData, setInsightsData] = useState<ProjectInsights | null>(null);

  const generateInsights = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch(
        `/api/documents/${projectId}/generate-comprehensive-insights`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token') || ''}`,
            'Content-Type': 'application/json',
          },
        }
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Failed to generate insights: ${response.statusText}`);
      }

      const data: ProjectInsights = await response.json();
      setInsightsData(data);
    } catch (err: any) {
      console.error('Error generating insights:', err);
      setError(err.message || 'Failed to generate project insights');
    } finally {
      setLoading(false);
    }
  };

  // Auto-generate on open if no data
  React.useEffect(() => {
    if (opened && !insightsData && !loading && !error) {
      generateInsights();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [opened]);

  const handleRegenerate = () => {
    setInsightsData(null);
    generateInsights();
  };

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={
        <Group gap="sm">
          <IconBrain size={20} />
          <Text fw={600}>Project Insights{projectName ? `: ${projectName}` : ''}</Text>
        </Group>
      }
      size="xl"
      padding="lg"
    >
      {loading && (
        <Group justify="center" p="xl">
          <Loader size="lg" />
          <Text c="dimmed">
            Generating comprehensive project insights...
            <br />
            <Text size="xs" c="dimmed" mt="xs">
              This may take a few minutes for large projects
            </Text>
          </Text>
        </Group>
      )}

      {error && (
        <Alert icon={<IconAlertCircle size={16} />} color="red" mb="md">
          {error}
          <Group mt="sm">
            <Button
              size="xs"
              variant="light"
              leftSection={<IconRefresh size={14} />}
              onClick={handleRegenerate}
            >
              Retry
            </Button>
          </Group>
        </Alert>
      )}

      {insightsData && !loading && (
        <>
          {/* Header with metadata */}
          <Group gap="md" mb="md" justify="space-between">
            <Group gap="md">
              <Badge color="grape" variant="light">
                {insightsData.line_count} lines
              </Badge>
              <Badge color="cyan" variant="light">
                {insightsData.document_count} documents
              </Badge>
              <Text size="xs" c="dimmed">
                Generated: {new Date(insightsData.generated_at).toLocaleString()}
              </Text>
            </Group>
            <Button
              size="xs"
              variant="subtle"
              leftSection={<IconRefresh size={14} />}
              onClick={handleRegenerate}
            >
              Regenerate
            </Button>
          </Group>

          {/* Insights content */}
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
                  h4: ({ node, ...props }) => (
                    <Text
                      component="h4"
                      size="sm"
                      fw={600}
                      mb="xs"
                      mt="sm"
                      {...props}
                    />
                  ),
                  ul: ({ node, ...props }) => (
                    <ul style={{ marginLeft: '1.5rem', marginBottom: '0.5rem' }} {...props} />
                  ),
                  ol: ({ node, ...props }) => (
                    <ol style={{ marginLeft: '1.5rem', marginBottom: '0.5rem' }} {...props} />
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
                  table: ({ node, ...props }) => (
                    <div style={{ overflowX: 'auto', marginBottom: '1rem' }}>
                      <table style={{ 
                        width: '100%', 
                        borderCollapse: 'collapse',
                        border: '1px solid var(--mantine-color-gray-3)'
                      }} {...props} />
                    </div>
                  ),
                  th: ({ node, ...props }) => (
                    <th style={{
                      padding: '0.5rem',
                      border: '1px solid var(--mantine-color-gray-3)',
                      backgroundColor: 'var(--mantine-color-gray-1)',
                      textAlign: 'left'
                    }}>
                      <Text size="sm" fw={600} {...props} />
                    </th>
                  ),
                  td: ({ node, ...props }) => (
                    <td style={{
                      padding: '0.5rem',
                      border: '1px solid var(--mantine-color-gray-3)'
                    }}>
                      <Text size="sm" {...props} />
                    </td>
                  ),
                }}
              >
                {insightsData.insights}
              </ReactMarkdown>
            </div>
          </ScrollArea>
        </>
      )}

      {!loading && !error && !insightsData && (
        <Alert color="yellow" icon={<IconAlertCircle size={16} />}>
          Click the button below to generate comprehensive project insights.
          <Group mt="md">
            <Button
              leftSection={<IconBrain size={16} />}
              onClick={generateInsights}
            >
              Generate Insights
            </Button>
          </Group>
        </Alert>
      )}
    </Modal>
  );
};

export default ProjectInsightsModal;
