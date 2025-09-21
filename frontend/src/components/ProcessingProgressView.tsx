import React, { useState, useEffect, useRef } from 'react';
import {
  Card,
  Text,
  Group,
  Button,
  Badge,
  Collapse,
  ScrollArea,
  Paper,
  Stack,
  ActionIcon,
  Divider
} from '@mantine/core';
import {
  IconChevronDown,
  IconChevronUp,
  IconActivity,
  IconAlertCircle,
  IconCircleCheck,
  IconInfoCircle,
  IconEye,
  IconEyeOff
} from '@tabler/icons-react';
import { useWebSocket, MessageType, LogMessage } from '../services/WebSocketManager';
import { useLogContext } from '../contexts/LogContext';

interface LogEntry {
  timestamp: string;
  level: 'INFO' | 'WARNING' | 'ERROR' | 'DEBUG';
  service: string;
  project_id: string;
  message: string;
  metadata?: Record<string, any>;
}

interface ProcessingProgressViewProps {
  projectId: string;
  isVisible: boolean;
  onToggleVisibility: () => void;
}

const ProcessingProgressView: React.FC<ProcessingProgressViewProps> = ({
  projectId,
  isVisible,
  onToggleVisibility
}) => {
  const [expandedSections, setExpandedSections] = useState({
    documentProcessing: true,
    entityExtraction: true,
    embeddings: true,
    graphUpdates: true
  });
  const [showDetailedLogs, setShowDetailedLogs] = useState(false);

  const scrollAreaRef = useRef<HTMLDivElement>(null);

  // Use centralized log context
  const { state, subscribeToWebSocket } = useLogContext();
  const { logs, isWebSocketConnected: isConnected } = state;

  // Subscribe to centralized WebSocket when visible
  useEffect(() => {
    if (isVisible && projectId) {
      subscribeToWebSocket(projectId, true);
    }
    return () => {
      if (projectId) {
        subscribeToWebSocket(projectId, false);
      }
    };
  }, [projectId, isVisible, subscribeToWebSocket]);

  // WebSocket connection is now handled by the centralized manager
  // Messages are received through the subscription callback

  // Auto-scroll to bottom when logs change
  useEffect(() => {
    if (scrollAreaRef.current) {
      scrollAreaRef.current.scrollTop = scrollAreaRef.current.scrollHeight;
    }
  }, [logs]);

  const toggleSection = (section: keyof typeof expandedSections) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section]
    }));
  };

  const getLogIcon = (level: string) => {
    switch (level) {
      case 'ERROR':
        return <IconAlertCircle size={16} color="red" />;
      case 'WARNING':
        return <IconAlertCircle size={16} color="orange" />;
      case 'INFO':
        return <IconInfoCircle size={16} color="blue" />;
      case 'DEBUG':
        return <IconActivity size={16} color="gray" />;
      default:
        return <IconCircleCheck size={16} color="green" />;
    }
  };

  const getBadgeColor = (level: string) => {
    switch (level) {
      case 'ERROR':
        return 'red';
      case 'WARNING':
        return 'yellow';
      case 'INFO':
        return 'blue';
      case 'DEBUG':
        return 'gray';
      default:
        return 'green';
    }
  };

  const filterLogsByCategory = (category: string) => {
    const keywords = {
      documentProcessing: ['document', 'processing', 'conversion', 'chunk', 'embed'],
      entityExtraction: ['entity', 'extraction', 'llm', 'chunk', 'json'],
      embeddings: ['embedding', 'chroma', 'vector', 'semantic'],
      graphUpdates: ['neo4j', 'graph', 'relationship', 'node', 'entity']
    };

    const categoryKeywords = keywords[category as keyof typeof keywords] || [];

    return logs.filter(log =>
      categoryKeywords.some(keyword =>
        log.message.toLowerCase().includes(keyword.toLowerCase()) ||
        log.source.toLowerCase().includes(keyword.toLowerCase()) ||
        (log.metadata?.operationName && log.metadata.operationName.toLowerCase().includes(keyword.toLowerCase()))
      )
    );
  };

  const formatTimestamp = (timestamp: string) => {
    return new Date(timestamp).toLocaleTimeString();
  };

  const renderLogEntry = (log: any, index: number) => (
    <Group key={index} align="flex-start" gap="sm" mb="xs">
      {getLogIcon(log.level)}
      <Stack gap={4} style={{ flex: 1 }}>
        <Group align="center" gap="xs">
          <Text size="xs" color="dimmed">{formatTimestamp(log.timestamp)}</Text>
          <Badge size="xs" color={getBadgeColor(log.level)}>{log.level}</Badge>
          <Badge size="xs" variant="outline">{log.source}</Badge>
        </Group>
        <Text size="sm">{log.message}</Text>
        {showDetailedLogs && log.metadata && Object.keys(log.metadata).length > 0 && (
          <Paper p="xs" bg="gray.1">
            <Text size="xs" component="pre" style={{ overflow: 'auto' }}>
              {JSON.stringify(log.metadata, null, 2)}
            </Text>
          </Paper>
        )}
      </Stack>
    </Group>
  );

  const renderSection = (title: string, icon: React.ReactNode, category: string, sectionKey: keyof typeof expandedSections) => {
    const sectionLogs = filterLogsByCategory(category).slice(-10);
    const isExpanded = expandedSections[sectionKey];

    return (
      <Paper key={sectionKey} withBorder p="md">
        <Group 
          justify="space-between" 
          style={{ cursor: 'pointer' }}
          onClick={() => toggleSection(sectionKey)}
          mb={isExpanded ? "md" : 0}
        >
          <Group>
            {icon}
            <Text fw={600}>{title}</Text>
            <Badge variant="outline">{sectionLogs.length} logs</Badge>
          </Group>
          <ActionIcon variant="subtle">
            {isExpanded ? <IconChevronUp size={16} /> : <IconChevronDown size={16} />}
          </ActionIcon>
        </Group>
        
        <Collapse in={isExpanded}>
          <Paper bg="gray.0" p="sm">
            <ScrollArea h={120}>
              {sectionLogs.map(renderLogEntry)}
            </ScrollArea>
          </Paper>
        </Collapse>
      </Paper>
    );
  };

  if (!isVisible) return null;

  return (
    <Card shadow="sm" padding="lg" radius="md" withBorder mt="md">
      <Group justify="space-between" mb="md">
        <Group align="center">
          <IconActivity size={20} />
          <Text size="lg" fw={600}>Document Processing Progress</Text>
          <Badge color={isConnected ? 'green' : 'gray'}>
            {isConnected ? 'Live' : 'Disconnected'}
          </Badge>
        </Group>
        <Group>
          <Button
            variant="light"
            size="xs"
            leftSection={showDetailedLogs ? <IconEyeOff size={14} /> : <IconEye size={14} />}
            onClick={() => setShowDetailedLogs(!showDetailedLogs)}
          >
            {showDetailedLogs ? 'Hide Details' : 'Show Details'}
          </Button>
          <Button
            variant="outline"
            size="xs"
            onClick={onToggleVisibility}
          >
            Hide Progress
          </Button>
        </Group>
      </Group>
      
      <Stack gap="md">
        {/* Processing Stages */}
        {renderSection("Document Processing", <IconActivity size={16} />, "documentProcessing", "documentProcessing")}
        {renderSection("Entity Extraction", <IconCircleCheck size={16} />, "entityExtraction", "entityExtraction")}
        {renderSection("Vector Embeddings", <IconInfoCircle size={16} />, "embeddings", "embeddings")}
        {renderSection("Knowledge Graph Updates", <IconActivity size={16} />, "graphUpdates", "graphUpdates")}

        {/* All Logs View (when detailed view is enabled) */}
        {showDetailedLogs && (
          <Paper withBorder p="md">
            <Group align="center" mb="md">
              <IconActivity size={16} />
              <Text fw={600}>All Processing Logs ({logs.length})</Text>
            </Group>
            <ScrollArea ref={scrollAreaRef} h={250}>
              <Stack gap="sm">
                {logs.map((log, index) => (
                  <Group key={index} align="flex-start" gap="sm">
                    {getLogIcon(log.level)}
                    <Stack gap={4} style={{ flex: 1 }}>
                      <Group align="center" gap="xs">
                        <Text size="xs" color="dimmed">{formatTimestamp(log.timestamp)}</Text>
                        <Badge size="xs" color={getBadgeColor(log.level)}>{log.level}</Badge>
                        <Badge size="xs" variant="outline">{log.source}</Badge>
                      </Group>
                      <Text size="sm">{log.message}</Text>
                      {log.metadata && Object.keys(log.metadata).length > 0 && (
                        <Paper p="xs" bg="gray.1">
                          <Text size="xs" component="pre" style={{ overflow: 'auto' }}>
                            {JSON.stringify(log.metadata, null, 2)}
                          </Text>
                        </Paper>
                      )}
                    </Stack>
                  </Group>
                ))}
              </Stack>
            </ScrollArea>
          </Paper>
        )}
      </Stack>
    </Card>
  );
};

export default ProcessingProgressView;