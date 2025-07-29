import React, { useState, useEffect, useRef } from 'react';
import {
  Drawer,
  Stack,
  Text,
  Group,
  ActionIcon,
  Tabs,
  ScrollArea,
  Code,
  Badge,
  Button,
  Divider,
  Card,
  Box,
  Tooltip
} from '@mantine/core';
import {
  IconPin,
  IconPinFilled,
  IconX,
  IconTerminal,
  IconRobot,
  IconPlayerStop,
  IconRefresh
} from '@tabler/icons-react';

interface LogEntry {
  timestamp: string;
  level: 'info' | 'warning' | 'error' | 'success';
  message: string;
  source?: string;
}

interface RightLogPaneProps {
  opened: boolean;
  onClose: () => void;
  assessmentLogs: string[];
  agenticLogs: LogEntry[];
  isAssessing: boolean;
  onStopAssessment?: () => void;
  projectName?: string;
}

const RightLogPane: React.FC<RightLogPaneProps> = ({
  opened,
  onClose,
  assessmentLogs,
  agenticLogs,
  isAssessing,
  onStopAssessment,
  projectName
}) => {
  const [isPinned, setIsPinned] = useState(false);
  const [activeTab, setActiveTab] = useState<string>('assessment');
  const assessmentScrollRef = useRef<HTMLDivElement>(null);
  const agenticScrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new logs are added
  useEffect(() => {
    if (activeTab === 'assessment' && assessmentScrollRef.current) {
      assessmentScrollRef.current.scrollTop = assessmentScrollRef.current.scrollHeight;
    }
  }, [assessmentLogs, activeTab]);

  useEffect(() => {
    if (activeTab === 'agentic' && agenticScrollRef.current) {
      agenticScrollRef.current.scrollTop = agenticScrollRef.current.scrollHeight;
    }
  }, [agenticLogs, activeTab]);

  const handleClose = () => {
    if (!isPinned) {
      onClose();
    }
  };

  const getLogLevelColor = (level: string) => {
    switch (level) {
      case 'error': return 'red';
      case 'warning': return 'yellow';
      case 'success': return 'green';
      case 'info':
      default: return 'blue';
    }
  };

  const formatTimestamp = (timestamp: string) => {
    return new Date(timestamp).toLocaleTimeString();
  };

  const formatAssessmentLog = (log: string, index: number) => {
    const isError = log.toLowerCase().includes('error');
    const isWarning = log.toLowerCase().includes('warning');
    const isSuccess = log.toLowerCase().includes('success') || log.toLowerCase().includes('completed');

    let color = 'dimmed';
    if (isError) color = 'red';
    else if (isWarning) color = 'yellow';
    else if (isSuccess) color = 'green';

    return (
      <Box key={index} mb="xs">
        <Text size="xs" c={color} ff="monospace">
          {log}
        </Text>
      </Box>
    );
  };

  return (
    <Drawer
      opened={opened}
      onClose={handleClose}
      position="right"
      size="xl"
      title={
        <Group justify="space-between" w="100%">
          <Group>
            <IconTerminal size={20} />
            <Text fw={600}>Assessment Logs</Text>
            {projectName && (
              <Badge variant="light" color="blue">
                {projectName}
              </Badge>
            )}
          </Group>
          <Group gap="xs">
            {isAssessing && onStopAssessment && (
              <Tooltip label="Stop Assessment">
                <Button
                  size="xs"
                  color="red"
                  variant="light"
                  leftSection={<IconPlayerStop size={14} />}
                  onClick={onStopAssessment}
                >
                  Stop
                </Button>
              </Tooltip>
            )}
            <Tooltip label={isPinned ? "Unpin pane" : "Pin pane"}>
              <ActionIcon
                variant={isPinned ? "filled" : "light"}
                color="blue"
                onClick={() => setIsPinned(!isPinned)}
              >
                {isPinned ? <IconPinFilled size={16} /> : <IconPin size={16} />}
              </ActionIcon>
            </Tooltip>
            <Tooltip label="Close">
              <ActionIcon
                variant="light"
                color="gray"
                onClick={onClose}
                disabled={isPinned}
              >
                <IconX size={16} />
              </ActionIcon>
            </Tooltip>
          </Group>
        </Group>
      }
      overlayProps={{ backgroundOpacity: isPinned ? 0 : 0.5 }}
      closeOnClickOutside={!isPinned}
      closeOnEscape={!isPinned}
      withCloseButton={false}
      styles={{
        content: {
          height: '100vh',
        },
        body: {
          height: 'calc(100vh - 60px)',
          padding: 0,
        }
      }}
    >
      <Stack h="100%" gap={0}>
        {/* Status Bar */}
        <Card p="sm" radius={0} withBorder>
          <Group justify="space-between">
            <Group gap="xs">
              <Badge
                color={isAssessing ? "green" : "gray"}
                variant={isAssessing ? "filled" : "light"}
                size="sm"
              >
                {isAssessing ? "Running" : "Idle"}
              </Badge>
              <Text size="sm" c="dimmed">
                Assessment Logs: {assessmentLogs.length} | Agentic Logs: {agenticLogs.length}
              </Text>
            </Group>
            <ActionIcon
              variant="light"
              size="sm"
              onClick={() => {
                // Refresh/clear logs functionality can be added here
              }}
            >
              <IconRefresh size={14} />
            </ActionIcon>
          </Group>
        </Card>

        <Divider />

        {/* Tabs */}
        <Tabs
          value={activeTab}
          onChange={(value) => setActiveTab(value || 'assessment')}
          style={{ flex: 1, display: 'flex', flexDirection: 'column' }}
        >
          <Tabs.List>
            <Tabs.Tab
              value="assessment"
              leftSection={<IconTerminal size={16} />}
            >
              Assessment Logs
              {assessmentLogs.length > 0 && (
                <Badge size="xs" ml="xs" variant="light">
                  {assessmentLogs.length}
                </Badge>
              )}
            </Tabs.Tab>
            <Tabs.Tab
              value="agentic"
              leftSection={<IconRobot size={16} />}
            >
              Agentic Interactions
              {agenticLogs.length > 0 && (
                <Badge size="xs" ml="xs" variant="light">
                  {agenticLogs.length}
                </Badge>
              )}
            </Tabs.Tab>
          </Tabs.List>

          {/* Assessment Logs Tab */}
          <Tabs.Panel value="assessment" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
            <ScrollArea
              style={{ flex: 1 }}
              p="md"
              viewportRef={assessmentScrollRef}
            >
              {assessmentLogs.length === 0 ? (
                <Text c="dimmed" ta="center" mt="xl">
                  No assessment logs yet. Start an assessment to see real-time progress.
                </Text>
              ) : (
                <Stack gap="xs">
                  {assessmentLogs.map((log, index) => formatAssessmentLog(log, index))}
                </Stack>
              )}
            </ScrollArea>
          </Tabs.Panel>

          {/* Agentic Logs Tab */}
          <Tabs.Panel value="agentic" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
            <ScrollArea
              style={{ flex: 1 }}
              p="md"
              viewportRef={agenticScrollRef}
            >
              {agenticLogs.length === 0 ? (
                <Text c="dimmed" ta="center" mt="xl">
                  No agentic interaction logs yet. AI agents will log their activities here during assessment.
                </Text>
              ) : (
                <Stack gap="xs">
                  {agenticLogs.map((log, index) => (
                    <Card key={index} p="xs" withBorder>
                      <Group justify="space-between" mb="xs">
                        <Badge
                          size="xs"
                          color={getLogLevelColor(log.level)}
                          variant="light"
                        >
                          {log.level.toUpperCase()}
                        </Badge>
                        <Text size="xs" c="dimmed">
                          {formatTimestamp(log.timestamp)}
                        </Text>
                      </Group>
                      {log.source && (
                        <Text size="xs" c="dimmed" mb="xs">
                          Source: {log.source}
                        </Text>
                      )}
                      <Code block style={{ fontSize: '12px' }}>
                        {log.message}
                      </Code>
                    </Card>
                  ))}
                </Stack>
              )}
            </ScrollArea>
          </Tabs.Panel>
        </Tabs>
      </Stack>
    </Drawer>
  );
};

export default RightLogPane;
