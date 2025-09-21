import React, { useState, useEffect } from 'react';
import {
  Paper,
  Text,
  Stack,
  Badge,
  Timeline,
  ScrollArea,
  Group,
  ActionIcon,
  Collapse,
  Code,
  Alert,
  Loader,
  Box
} from '@mantine/core';
import { IconChevronDown, IconChevronRight, IconRobot, IconTool, IconAlertCircle, IconCheck } from '@tabler/icons-react';
import { useWebSocket, MessageType, AssessmentMessage } from '../../services/WebSocketManager';
import { useLogContext } from '../../contexts/LogContext';

interface AgentLogEntry {
  type: 'agent_action' | 'tool_result' | 'tool_error' | 'agent_finish' | 'agent_start';
  timestamp: string;
  agent_name: string;
  tool?: string;
  tool_input?: string;
  output?: string;
  error?: string;
  status?: string;
  log?: string;
  goal?: string;
  action_description?: string;
}

interface AgentActivityLogProps {
  projectId: string;
  isAssessmentRunning: boolean;
  isDocumentGenerating?: boolean;
}

const AgentActivityLog: React.FC<AgentActivityLogProps> = ({ projectId, isAssessmentRunning, isDocumentGenerating = false }) => {
  const [expandedItems, setExpandedItems] = useState<Set<number>>(new Set());

  // Use centralized log context
  const { state, subscribeToWebSocket } = useLogContext();
  const { logs: allLogs, isWebSocketConnected: isConnected } = state;

  // Filter logs for agent activity
  const logs = allLogs.filter(log => log.type === 'agent_activity' && log.projectId === projectId);

  // Subscribe to centralized WebSocket when assessment is running
  useEffect(() => {
    if ((isAssessmentRunning || isDocumentGenerating) && projectId) {
      subscribeToWebSocket(projectId, true);
    }
    return () => {
      if (projectId) {
        subscribeToWebSocket(projectId, false);
      }
    };
  }, [projectId, isAssessmentRunning, isDocumentGenerating, subscribeToWebSocket]);

  // WebSocket messages are now handled by the centralized LogContext
  // Global event listener for document generation
  useEffect(() => {
    const handleDocumentGenerationLogs = (event: CustomEvent) => {
      const data = event.detail;

      // Check if this is a log entry from document generation
      if (data && data.type && ['agent_action', 'tool_result', 'tool_error', 'agent_finish', 'agent_start'].includes(data.type)) {
        // This will be handled by the LogContext through WebSocket
        console.log('Document generation log received:', data);
      }
    };

    // Listen for document generation events
    window.addEventListener('documentGenerationLog', handleDocumentGenerationLogs as EventListener);

    return () => {
      window.removeEventListener('documentGenerationLog', handleDocumentGenerationLogs as EventListener);
    };
  }, []);

  const toggleExpanded = (index: number) => {
    const newExpanded = new Set(expandedItems);
    if (newExpanded.has(index)) {
      newExpanded.delete(index);
    } else {
      newExpanded.add(index);
    }
    setExpandedItems(newExpanded);
  };

  const getLogIcon = (type: string, status?: string) => {
    switch (type) {
      case 'agent_start':
        return <IconRobot size={16} color="#228be6" />;
      case 'agent_action':
        return <IconTool size={16} color="#fd7e14" />;
      case 'tool_result':
        return status === 'error' ? <IconAlertCircle size={16} color="#fa5252" /> : <IconCheck size={16} color="#40c057" />;
      case 'tool_error':
        return <IconAlertCircle size={16} color="#fa5252" />;
      case 'agent_finish':
        return <IconCheck size={16} color="#40c057" />;
      default:
        return <IconRobot size={16} />;
    }
  };

  const getLogColor = (type: string, status?: string) => {
    switch (type) {
      case 'agent_start':
        return 'blue';
      case 'agent_action':
        return 'orange';
      case 'tool_result':
        return status === 'error' ? 'red' : 'green';
      case 'tool_error':
        return 'red';
      case 'agent_finish':
        return 'green';
      default:
        return 'gray';
    }
  };

  const formatTimestamp = (timestamp: string) => {
    return new Date(timestamp).toLocaleTimeString();
  };

  const getLogTitle = (log: any) => {
    switch (log.type) {
      case 'agent_start':
        return `${log.agentName} started working`;
      case 'agent_action':
        return log.actionDescription || `${log.agentName} is using ${log.tool}`;
      case 'tool_result':
        return `${log.tool || 'Tool'} completed successfully`;
      case 'tool_error':
        return `${log.tool || 'Tool'} encountered an error`;
      case 'agent_finish':
        return `${log.agentName} completed their task`;
      default:
        return 'Agent Activity';
    }
  };

  if (!isAssessmentRunning && logs.length === 0) {
    return (
      <Paper p="md" withBorder>
        <Text c="dimmed" ta="center">
          Agent activity will appear here when an assessment is running
        </Text>
      </Paper>
    );
  }

  return (
    <Paper p="md" withBorder>
      <Group justify="space-between" mb="md">
        <Text fw={600} size="lg">Agent Activity Log</Text>
        {(isAssessmentRunning || isDocumentGenerating) && (
          <Group gap="xs">
            <Loader size="sm" />
            <Text size="sm" c="dimmed">
              {isConnected ? 'Live monitoring' : 'Connecting...'}
            </Text>
          </Group>
        )}
      </Group>

      <ScrollArea h={400}>
        <Timeline active={logs.length} bulletSize={24} lineWidth={2}>
          {logs.map((log, index) => (
            <Timeline.Item
              key={index}
              bullet={getLogIcon(log.type, log.status)}
              title={
                <Group justify="space-between" style={{ width: '100%' }}>
                  <Box>
                    <Text fw={500} size="sm">{getLogTitle(log)}</Text>
                    <Text size="xs" c="dimmed">{formatTimestamp(log.timestamp)}</Text>
                  </Box>
                  <Group gap="xs">
                    <Badge size="xs" color={getLogColor(log.type, log.status)}>
                      {log.type.replace('_', ' ')}
                    </Badge>
                    {(log.toolInput || log.output || log.error) && (
                      <ActionIcon
                        size="sm"
                        variant="subtle"
                        onClick={() => toggleExpanded(index)}
                      >
                        {expandedItems.has(index) ? <IconChevronDown size={14} /> : <IconChevronRight size={14} />}
                      </ActionIcon>
                    )}
                  </Group>
                </Group>
              }
            >
              <Collapse in={expandedItems.has(index)}>
                <Stack gap="xs" mt="xs">
                  {log.toolInput && (
                    <Box>
                      <Text size="xs" fw={500} mb={4}>Tool Input:</Text>
                      <Code block style={{ fontSize: '11px' }}>
                        {log.toolInput}
                      </Code>
                    </Box>
                  )}

                  {log.output && (
                    <Box>
                      <Text size="xs" fw={500} mb={4}>Output:</Text>
                      <Code block style={{ fontSize: '11px', maxHeight: '150px', overflow: 'auto' }}>
                        {log.output}
                      </Code>
                    </Box>
                  )}

                  {log.error && (
                    <Alert icon={<IconAlertCircle size={16} />} color="red">
                      <Text size="xs">{log.error}</Text>
                    </Alert>
                  )}

                  {log.log && (
                    <Box>
                      <Text size="xs" fw={500} mb={4}>Agent Log:</Text>
                      <Text size="xs" c="dimmed">{log.log}</Text>
                    </Box>
                  )}
                </Stack>
              </Collapse>
            </Timeline.Item>
          ))}
        </Timeline>

        {logs.length === 0 && isAssessmentRunning && (
          <Group justify="center" mt="xl">
            <Loader size="sm" />
            <Text size="sm" c="dimmed">Waiting for agent activity...</Text>
          </Group>
        )}
      </ScrollArea>
    </Paper>
  );
};

export default AgentActivityLog;
