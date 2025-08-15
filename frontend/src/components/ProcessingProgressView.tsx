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
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [expandedSections, setExpandedSections] = useState({
    documentProcessing: true,
    entityExtraction: true,
    embeddings: true,
    graphUpdates: true
  });
  const [showDetailedLogs, setShowDetailedLogs] = useState(false);
  
  const wsRef = useRef<WebSocket | null>(null);
  const scrollAreaRef = useRef<HTMLDivElement>(null);

  // WebSocket connection for real-time log streaming
  useEffect(() => {
    if (!isVisible) return;

    const connectWebSocket = () => {
      try {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.host;
        const wsUrl = `${protocol}//${host}/ws/logs/document_processing`;
        
        console.log('Connecting to WebSocket:', wsUrl);
        
        const ws = new WebSocket(wsUrl);
        
        ws.onopen = () => {
          console.log('WebSocket connected for document processing logs');
          setIsConnected(true);
        };
        
        ws.onmessage = (event) => {
          try {
            const logEntry: LogEntry = JSON.parse(event.data);
            
            // Filter logs for this project or general document processing
            if (logEntry.project_id === projectId || 
                logEntry.service === 'document_processing' ||
                logEntry.service === `project_${projectId}`) {
              setLogs(prevLogs => {
                const newLogs = [...prevLogs, logEntry].slice(-200); // Keep last 200 logs
                return newLogs;
              });
              
              // Auto-scroll to bottom
              setTimeout(() => {
                if (scrollAreaRef.current) {
                  scrollAreaRef.current.scrollTop = scrollAreaRef.current.scrollHeight;
                }
              }, 100);
            }
          } catch (error) {
            console.error('Error parsing WebSocket message:', error);
          }
        };
        
        ws.onclose = () => {
          console.log('WebSocket disconnected');
          setIsConnected(false);
          // Attempt to reconnect after 3 seconds
          setTimeout(connectWebSocket, 3000);
        };
        
        ws.onerror = (error) => {
          console.error('WebSocket error:', error);
          setIsConnected(false);
        };
        
        wsRef.current = ws;
        
      } catch (error) {
        console.error('Failed to create WebSocket connection:', error);
      }
    };

    connectWebSocket();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [isVisible, projectId]);

  // Clear logs when project changes
  useEffect(() => {
    setLogs([]);
  }, [projectId]);

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

  const filterLogsByCategory = (category: string): LogEntry[] => {
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
        log.service.toLowerCase().includes(keyword.toLowerCase())
      )
    );
  };

  const formatTimestamp = (timestamp: string) => {
    return new Date(timestamp).toLocaleTimeString();
  };

  const renderLogEntry = (log: LogEntry, index: number) => (
    <Group key={index} align="flex-start" gap="sm" mb="xs">
      {getLogIcon(log.level)}
      <Stack gap={4} style={{ flex: 1 }}>
        <Group align="center" gap="xs">
          <Text size="xs" color="dimmed">{formatTimestamp(log.timestamp)}</Text>
          <Badge size="xs" color={getBadgeColor(log.level)}>{log.level}</Badge>
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
                        <Badge size="xs" variant="outline">{log.service}</Badge>
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