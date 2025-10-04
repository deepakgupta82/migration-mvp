import React, { useState, useEffect, useCallback } from 'react';
import { Modal, ScrollArea, Text, Loader, Alert, Group, Badge } from '@mantine/core';
import { IconAlertCircle, IconFileText } from '@tabler/icons-react';
import ReactMarkdown from 'react-markdown';

interface AssessmentViewerModalProps {
  opened: boolean;
  onClose: () => void;
  projectId: string;
  filename: string;
}

interface FormattedAssessment {
  assessment: string;
  line_count: number;
  generated_at: string;
}

const AssessmentViewerModal: React.FC<AssessmentViewerModalProps> = ({
  opened,
  onClose,
  projectId,
  filename,
}) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [assessmentData, setAssessmentData] = useState<FormattedAssessment | null>(null);

  const fetchAssessment = useCallback(async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch(
        `/api/documents/${projectId}/documents/${filename}/assessment/formatted`,
        {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token') || ''}`,
          },
        }
      );

      if (!response.ok) {
        throw new Error(`Failed to fetch assessment: ${response.statusText}`);
      }

      const data: FormattedAssessment = await response.json();
      setAssessmentData(data);
    } catch (err: any) {
      console.error('Error fetching assessment:', err);
      setError(err.message || 'Failed to fetch assessment');
    } finally {
      setLoading(false);
    }
  }, [projectId, filename]);

  useEffect(() => {
    if (opened && projectId && filename) {
      fetchAssessment();
    }
  }, [opened, projectId, filename, fetchAssessment]);

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={
        <Group gap="sm">
          <IconFileText size={20} />
          <Text fw={600}>Document Assessment: {filename}</Text>
        </Group>
      }
      size="xl"
      padding="lg"
    >
      {loading && (
        <Group justify="center" p="xl">
          <Loader size="lg" />
          <Text c="dimmed">Generating assessment...</Text>
        </Group>
      )}

      {error && (
        <Alert icon={<IconAlertCircle size={16} />} color="red" mb="md">
          {error}
        </Alert>
      )}

      {assessmentData && !loading && (
        <>
          {/* Header with metadata */}
          <Group gap="md" mb="md">
            <Badge color="violet" variant="light">
              {assessmentData.line_count} lines
            </Badge>
            <Text size="xs" c="dimmed">
              Generated: {new Date(assessmentData.generated_at).toLocaleString()}
            </Text>
          </Group>

          {/* Assessment content */}
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
                {assessmentData.assessment}
              </ReactMarkdown>
            </div>
          </ScrollArea>
        </>
      )}

      {!loading && !error && !assessmentData && (
        <Alert color="yellow" icon={<IconAlertCircle size={16} />}>
          No assessment available for this document. Please ensure the document has been processed.
        </Alert>
      )}
    </Modal>
  );
};

export default AssessmentViewerModal;
