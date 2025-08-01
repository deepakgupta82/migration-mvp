import React, { useState, useEffect } from 'react';
import {
  Card,
  Text,
  Timeline,
  Badge,
  Group,
  Stack,
  ScrollArea,
  ActionIcon,
  Select,
  Button,
  Divider,
  Box,
  Alert,
  Code,
  Collapse,
} from '@mantine/core';
import {
  IconCalendar,
  IconUser,
  IconUpload,
  IconPlayerPlay,
  IconFileText,
  IconSettings,
  IconRefresh,
  IconChevronDown,
  IconChevronRight,
  IconClock,
  IconCheck,
  IconX,
  IconEdit,
} from '@tabler/icons-react';

interface HistoryEntry {
  id: string;
  timestamp: string;
  type: 'project_created' | 'file_uploaded' | 'processing_started' | 'assessment_started' | 'assessment_completed' | 'report_generated' | 'settings_changed' | 'user_action';
  user: string;
  action: string;
  details?: any;
  status?: 'success' | 'error' | 'warning' | 'info';
  metadata?: {
    fileCount?: number;
    fileNames?: string[];
    duration?: string;
    reportType?: string;
    settingChanged?: string;
    oldValue?: any;
    newValue?: any;
  };
}

interface ProjectHistoryProps {
  projectId: string;
}

export const ProjectHistory: React.FC<ProjectHistoryProps> = ({ projectId }) => {
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [filterType, setFilterType] = useState<string>('all');
  const [expandedItems, setExpandedItems] = useState<Set<string>>(new Set());

  // Load real project history from API
  useEffect(() => {
    const loadProjectHistory = async () => {
      setLoading(true);
      try {
        // For now, create minimal real history based on project data
        const response = await fetch(`http://localhost:8002/projects/${projectId}`);
        if (response.ok) {
          const project = await response.json();

          const realHistory: HistoryEntry[] = [
            {
              id: '1',
              timestamp: project.created_at,
              type: 'project_created',
              user: 'user',
              action: `Created project "${project.name}"`,
              status: 'success',
              details: {
                projectName: project.name,
                description: project.description || 'No description provided',
                clientName: project.client_name,
              },
            },
          ];

          // Add file upload history if files exist
          try {
            const filesResponse = await fetch(`http://localhost:8002/projects/${projectId}/files`);
            if (filesResponse.ok) {
              const files = await filesResponse.json();
              if (files.length > 0) {
                realHistory.push({
                  id: '2',
                  timestamp: files[0].uploaded_at || project.updated_at,
                  type: 'file_uploaded',
                  user: 'user',
                  action: `Uploaded ${files.length} file(s)`,
                  status: 'success',
                  metadata: {
                    fileCount: files.length,
                    fileNames: files.map((f: any) => f.filename).slice(0, 3),
                  },
                  details: {
                    totalSize: `${(files.reduce((sum: number, f: any) => sum + (f.size || 0), 0) / 1024 / 1024).toFixed(1)} MB`,
                  },
                });
              }
            }
          } catch (error) {
            console.log('Could not load file history:', error);
          }

          // Add processing history if project has been processed
          if (project.status === 'completed' || project.status === 'running') {
            realHistory.push({
              id: '3',
              timestamp: project.updated_at,
              type: 'processing_started',
              user: 'system',
              action: 'Started document processing and analysis',
              status: project.status === 'completed' ? 'success' : 'info',
              details: {
                processingType: 'AI-powered document analysis',
                status: project.status,
              },
            });
          }

          setHistory(realHistory);
        }
      } catch (error) {
        console.error('Failed to load project history:', error);
        // Fallback to minimal history
        setHistory([
          {
            id: '1',
            timestamp: new Date().toISOString(),
            type: 'project_created',
            user: 'user',
            action: 'Project created',
            status: 'success',
          },
        ]);
      } finally {
        setLoading(false);
      }
    };

    loadProjectHistory();
  }, [projectId]);

  const getTypeIcon = (type: HistoryEntry['type']) => {
    switch (type) {
      case 'project_created':
        return <IconCalendar size={16} />;
      case 'file_uploaded':
        return <IconUpload size={16} />;
      case 'processing_started':
        return <IconPlayerPlay size={16} />;
      case 'assessment_started':
        return <IconPlayerPlay size={16} />;
      case 'assessment_completed':
        return <IconCheck size={16} />;
      case 'report_generated':
        return <IconFileText size={16} />;
      case 'settings_changed':
        return <IconSettings size={16} />;
      case 'user_action':
        return <IconUser size={16} />;
      default:
        return <IconClock size={16} />;
    }
  };

  const getStatusColor = (status?: HistoryEntry['status']) => {
    switch (status) {
      case 'success': return 'green';
      case 'error': return 'red';
      case 'warning': return 'yellow';
      case 'info': return 'blue';
      default: return 'gray';
    }
  };

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    return {
      date: date.toLocaleDateString(),
      time: date.toLocaleTimeString(),
      relative: getRelativeTime(date),
    };
  };

  const getRelativeTime = (date: Date) => {
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${diffDays}d ago`;
  };

  const toggleExpanded = (id: string) => {
    const newExpanded = new Set(expandedItems);
    if (newExpanded.has(id)) {
      newExpanded.delete(id);
    } else {
      newExpanded.add(id);
    }
    setExpandedItems(newExpanded);
  };

  const filteredHistory = history.filter(entry => {
    if (filterType === 'all') return true;
    return entry.type === filterType;
  });

  const refreshHistory = () => {
    setLoading(true);
    // Simulate API call
    setTimeout(() => {
      setLoading(false);
    }, 1000);
  };

  return (
    <Card shadow="sm" p="lg" radius="md" withBorder>
      <Group justify="space-between" mb="md">
        <Text size="lg" fw={600}>
          Project History
        </Text>
        <Group gap="sm">
          <Select
            size="sm"
            value={filterType}
            onChange={(value) => setFilterType(value || 'all')}
            data={[
              { value: 'all', label: 'All Activities' },
              { value: 'project_created', label: 'Project Events' },
              { value: 'file_uploaded', label: 'File Operations' },
              { value: 'assessment_started', label: 'Assessments' },
              { value: 'report_generated', label: 'Reports' },
              { value: 'settings_changed', label: 'Settings' },
              { value: 'user_action', label: 'User Actions' },
            ]}
            style={{ width: 150 }}
          />
          <ActionIcon
            variant="subtle"
            onClick={refreshHistory}
            loading={loading}
          >
            <IconRefresh size={16} />
          </ActionIcon>
        </Group>
      </Group>

      <Divider mb="md" />

      {filteredHistory.length === 0 ? (
        <Alert color="blue" icon={<IconClock size={16} />}>
          No history entries found for the selected filter.
        </Alert>
      ) : (
        <ScrollArea h={500}>
          <Timeline active={filteredHistory.length} bulletSize={24} lineWidth={2}>
            {filteredHistory.map((entry) => {
              const timestamp = formatTimestamp(entry.timestamp);
              const isExpanded = expandedItems.has(entry.id);
              const hasDetails = entry.details || entry.metadata;

              return (
                <Timeline.Item
                  key={entry.id}
                  bullet={getTypeIcon(entry.type)}
                  title={
                    <Box>
                      <Group justify="space-between" align="flex-start">
                        <Box style={{ flex: 1 }}>
                          <Text fw={500} size="sm">
                            {entry.action}
                          </Text>
                          <Group gap="xs" mt="xs">
                            <Badge size="xs" color={getStatusColor(entry.status)}>
                              {entry.status || 'info'}
                            </Badge>
                            <Text size="xs" c="dimmed">
                              by {entry.user}
                            </Text>
                            <Text size="xs" c="dimmed">
                              {timestamp.relative}
                            </Text>
                          </Group>
                        </Box>
                        {hasDetails && (
                          <ActionIcon
                            size="sm"
                            variant="subtle"
                            onClick={() => toggleExpanded(entry.id)}
                          >
                            {isExpanded ? <IconChevronDown size={14} /> : <IconChevronRight size={14} />}
                          </ActionIcon>
                        )}
                      </Group>

                      <Collapse in={isExpanded}>
                        <Box mt="md" p="sm" style={{ backgroundColor: '#f8f9fa', borderRadius: '4px' }}>
                          {entry.metadata && (
                            <Stack gap="xs" mb="sm">
                              <Text size="xs" fw={500} c="dimmed">
                                METADATA
                              </Text>
                              {entry.metadata.fileCount && (
                                <Text size="xs">
                                  Files: {entry.metadata.fileCount}
                                  {entry.metadata.fileNames && (
                                    <Code ml="xs">
                                      {entry.metadata.fileNames.join(', ')}
                                    </Code>
                                  )}
                                </Text>
                              )}
                              {entry.metadata.duration && (
                                <Text size="xs">
                                  Duration: {entry.metadata.duration}
                                </Text>
                              )}
                              {entry.metadata.settingChanged && (
                                <Text size="xs">
                                  Setting: {entry.metadata.settingChanged}
                                  <br />
                                  {entry.metadata.oldValue && (
                                    <>
                                      Old: <Code>{String(entry.metadata.oldValue)}</Code>
                                      <br />
                                    </>
                                  )}
                                  {entry.metadata.newValue && (
                                    <>
                                      New: <Code>{String(entry.metadata.newValue)}</Code>
                                    </>
                                  )}
                                </Text>
                              )}
                            </Stack>
                          )}

                          {entry.details && (
                            <Stack gap="xs">
                              <Text size="xs" fw={500} c="dimmed">
                                DETAILS
                              </Text>
                              <Code block>
                                {JSON.stringify(entry.details, null, 2)}
                              </Code>
                            </Stack>
                          )}
                        </Box>
                      </Collapse>
                    </Box>
                  }
                />
              );
            })}
          </Timeline>
        </ScrollArea>
      )}
    </Card>
  );
};

export default ProjectHistory;
