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

interface AgentLogEntry {
  type: 'agent_action' | 'tool_result' | 'tool_error' | 'agent_finish';
  timestamp: string;
  agent_name: string;
  tool?: string;
  tool_input?: string;
  output?: string;
  error?: string;
  status?: string;
  log?: string;
}

interface AgentActivityLogProps {
  projectId: string;
  isAssessmentRunning: boolean;
}

const AgentActivityLog: React.FC<AgentActivityLogProps> = ({ projectId, isAssessmentRunning }) => {
  const [logs, setLogs] = useState<AgentLogEntry[]>([]);
  const [expandedItems, setExpandedItems] = useState<Set<number>>(new Set());
  const [websocket, setWebsocket] = useState<WebSocket | null>(null);

  useEffect(() => {
    if (isAssessmentRunning && !websocket) {
      // Connect to the assessment WebSocket to receive real-time logs
      const ws = new WebSocket(`ws://localhost:8001/ws/run_assessment/${projectId}`);

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          // Check if this is a log entry (has type field)
          if (data.type && ['agent_action', 'tool_result', 'tool_error', 'agent_finish'].includes(data.type)) {
            setLogs(prevLogs => [...prevLogs, data]);
          }
        } catch (error) {
          // Ignore non-JSON messages (status updates, etc.)
        }
      };

      ws.onclose = () => {
        setWebsocket(null);
      };

      setWebsocket(ws);
    }

    return () => {
      if (websocket) {
        websocket.close();
        setWebsocket(null);
      }
    };
  }, [isAssessmentRunning, projectId, websocket]);

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
      case 'agent_action':
        return <IconRobot size={16} color="#228be6" />;
      case 'tool_result':
        return status === 'error' ? <IconAlertCircle size={16} color="#fa5252" /> : <IconTool size={16} color="#40c057" />;
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
      case 'agent_action':
        return 'blue';
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

  const getLogTitle = (log: AgentLogEntry) => {
    switch (log.type) {
      case 'agent_action':
        return `${log.agent_name} is using ${log.tool}`;
      case 'tool_result':
        return `${log.tool || 'Tool'} completed successfully`;
      case 'tool_error':
        return `${log.tool || 'Tool'} encountered an error`;
      case 'agent_finish':
        return `${log.agent_name} completed their task`;
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
        {isAssessmentRunning && (
          <Group gap="xs">
            <Loader size="sm" />
            <Text size="sm" c="dimmed">Live monitoring</Text>
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
                    {(log.tool_input || log.output || log.error) && (
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
                  {log.tool_input && (
                    <Box>
                      <Text size="xs" fw={500} mb={4}>Tool Input:</Text>
                      <Code block style={{ fontSize: '11px' }}>
                        {log.tool_input}
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
