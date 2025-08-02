import React, { useState, useEffect, useRef } from 'react';
import {
  Card,
  Group,
  Text,
  ActionIcon,
  Switch,
  Badge,
  Paper,
  ScrollArea,
  TextInput,
  Tooltip,
} from '@mantine/core';
import {
  IconPlayerPlay,
  IconPlayerStop,
  IconTrash,
  IconDownload,
  IconSearch,
  IconCopy,
} from '@tabler/icons-react';

interface ConsoleEntry {
  timestamp: string;
  level: 'INFO' | 'WARNING' | 'ERROR' | 'DEBUG';
  service: string;
  message: string;
  raw?: string;
}

interface ModernConsoleProps {
  service: string;
  title: string;
  icon: React.ReactNode;
  mode?: 'console' | 'logs';
}

export const ModernConsole: React.FC<ModernConsoleProps> = ({ service, title, icon, mode = 'logs' }) => {
  const [isStreaming, setIsStreaming] = useState(false);
  const [logs, setLogs] = useState<ConsoleEntry[]>([]);
  const [autoScroll, setAutoScroll] = useState(true);
  const [showTimestamps, setShowTimestamps] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedText, setSelectedText] = useState('');

  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const consoleRef = useRef<HTMLDivElement>(null);

  // WebSocket connection for real-time logs
  const startStreaming = () => {
    if (wsRef.current) {
      wsRef.current.close();
    }

    const wsUrl = mode === 'console'
      ? `ws://localhost:8000/ws/console/${service}`
      : `ws://localhost:8000/ws/logs/${service}`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log(`✅ Connected to ${service} console`);
      setIsStreaming(true);

      // Add connection log
      const connectionLog: ConsoleEntry = {
        timestamp: new Date().toISOString(),
        level: 'INFO',
        service: service,
        message: `✅ Connected to ${service} console stream`,
        raw: `[${new Date().toLocaleTimeString()}] INFO: Connected to ${service} console stream`
      };
      setLogs(prev => [...prev, connectionLog]);
    };

    ws.onmessage = (event) => {
      try {
        const logEntry = JSON.parse(event.data);
        const consoleEntry: ConsoleEntry = {
          timestamp: logEntry.timestamp,
          level: logEntry.level,
          service: logEntry.service,
          message: logEntry.message,
          raw: `[${new Date(logEntry.timestamp).toLocaleTimeString()}] ${logEntry.level}: ${logEntry.message}`
        };

        setLogs(prev => [...prev, consoleEntry].slice(-1000)); // Keep last 1000 logs

        // Auto-scroll to bottom if enabled
        if (autoScroll && scrollAreaRef.current) {
          setTimeout(() => {
            const scrollArea = scrollAreaRef.current;
            if (scrollArea) {
              // Find the actual scrollable element
              const scrollableElement = scrollArea.querySelector('[data-radix-scroll-area-viewport]');
              if (scrollableElement) {
                scrollableElement.scrollTop = scrollableElement.scrollHeight;
              } else {
                scrollArea.scrollTop = scrollArea.scrollHeight;
              }
            }
          }, 50);
        }
      } catch (error) {
        console.error('Error parsing console log:', error);
      }
    };

    ws.onclose = (event) => {
      console.log(`⚠️ Disconnected from ${service} console. Code: ${event.code}, Reason: ${event.reason || 'Unknown'}`);
      setIsStreaming(false);

      // Add disconnection log
      const disconnectLog: ConsoleEntry = {
        timestamp: new Date().toISOString(),
        level: 'WARNING',
        service: service,
        message: `⚠️ Disconnected from ${service} console stream. Code: ${event.code}${event.reason ? `, Reason: ${event.reason}` : ''}`,
        raw: `[${new Date().toLocaleTimeString()}] WARNING: Disconnected from ${service} console stream`
      };
      setLogs(prev => [...prev, disconnectLog]);
    };

    ws.onerror = (error) => {
      console.error(`❌ Console WebSocket error for ${service}:`, error);
      setIsStreaming(false);

      // Add error log
      const errorLog: ConsoleEntry = {
        timestamp: new Date().toISOString(),
        level: 'ERROR',
        service: service,
        message: `❌ Console connection error: WebSocket failed to connect to ${service}. Check if backend is running.`,
        raw: `[${new Date().toLocaleTimeString()}] ERROR: Console connection error: WebSocket failed`
      };
      setLogs(prev => [...prev, errorLog]);
    };

    wsRef.current = ws;
  };

  const stopStreaming = () => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setIsStreaming(false);
  };

  const clearLogs = () => {
    setLogs([]);
  };

  const downloadLogs = () => {
    const logText = logs.map(log => log.raw || log.message).join('\n');
    const blob = new Blob([logText], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${service}_console_${new Date().toISOString().split('T')[0]}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const copySelectedText = () => {
    if (selectedText) {
      navigator.clipboard.writeText(selectedText);
    } else {
      // Copy all visible logs
      const allText = filteredLogs.map(log => log.raw || log.message).join('\n');
      navigator.clipboard.writeText(allText);
    }
  };

  const handleTextSelection = () => {
    const selection = window.getSelection();
    if (selection) {
      setSelectedText(selection.toString());
    }
  };

  // Filter logs based on search term
  const filteredLogs = logs.filter(log =>
    searchTerm === '' ||
    log.message.toLowerCase().includes(searchTerm.toLowerCase()) ||
    log.service.toLowerCase().includes(searchTerm.toLowerCase())
  );

  // Get log level color
  const getLogLevelColor = (level: string) => {
    switch (level) {
      case 'ERROR': return '#ff6b6b';
      case 'WARNING': return '#ffa726';
      case 'INFO': return '#42a5f5';
      case 'DEBUG': return '#9e9e9e';
      default: return '#ffffff';
    }
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  return (
    <Card shadow="sm" p="lg" radius="md" withBorder>
      {/* Console Header - All controls in one line */}
      <Group justify="space-between" mb="md" wrap="nowrap">
        <Group gap="sm" style={{ flexShrink: 0 }}>
          {icon}
          <Text size="lg" fw={600} style={{ whiteSpace: 'nowrap' }}>{title}</Text>
          <Badge color={isStreaming ? 'green' : 'gray'} variant="light" size="sm">
            {isStreaming ? 'Streaming' : 'Stopped'}
          </Badge>
        </Group>

        <Group gap="sm" wrap="nowrap" style={{ flexShrink: 0 }}>
          {/* Search */}
          <TextInput
            size="xs"
            placeholder="Search logs..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.currentTarget.value)}
            leftSection={<IconSearch size={14} />}
            style={{ width: '180px' }}
          />

          {/* Controls */}
          <Switch
            size="xs"
            label="Timestamps"
            checked={showTimestamps}
            onChange={(event) => setShowTimestamps(event.currentTarget.checked)}
          />

          <Switch
            size="xs"
            label="Auto-scroll"
            checked={autoScroll}
            onChange={(event) => setAutoScroll(event.currentTarget.checked)}
          />

          <Tooltip label="Copy">
            <ActionIcon
              size="sm"
              variant="light"
              color="blue"
              onClick={copySelectedText}
            >
              <IconCopy size={14} />
            </ActionIcon>
          </Tooltip>

          <Tooltip label="Clear Console">
            <ActionIcon
              size="sm"
              variant="light"
              color="orange"
              onClick={clearLogs}
            >
              <IconTrash size={14} />
            </ActionIcon>
          </Tooltip>

          <Tooltip label="Download Logs">
            <ActionIcon
              size="sm"
              variant="light"
              color="green"
              onClick={downloadLogs}
            >
              <IconDownload size={14} />
            </ActionIcon>
          </Tooltip>

          <Tooltip label={isStreaming ? "Stop Streaming" : "Start Streaming"}>
            <ActionIcon
              size="sm"
              variant="light"
              color={isStreaming ? "red" : "blue"}
              onClick={isStreaming ? stopStreaming : startStreaming}
            >
              {isStreaming ? <IconPlayerStop size={14} /> : <IconPlayerPlay size={14} />}
            </ActionIcon>
          </Tooltip>
        </Group>
      </Group>

      {/* Console Window */}
      <Paper
        style={{
          backgroundColor: '#1a1a1a',
          border: '1px solid #333',
          borderRadius: '4px',
          height: '500px',
          fontFamily: 'Monaco, Menlo, "Ubuntu Mono", monospace',
          fontSize: '13px',
          overflow: 'hidden'
        }}
      >
        <ScrollArea
          h={500}
          ref={scrollAreaRef}
          style={{ padding: '12px' }}
        >
          <div
            ref={consoleRef}
            onMouseUp={handleTextSelection}
            style={{ userSelect: 'text' }}
          >
            {filteredLogs.length === 0 ? (
              <Text
                size="sm"
                c="dimmed"
                ta="center"
                mt="xl"
                style={{ color: '#666' }}
              >
                {searchTerm ? 'No logs match your search.' : 'No logs available. Click the play button to start streaming.'}
              </Text>
            ) : (
              filteredLogs.map((log, index) => (
                <div
                  key={index}
                  style={{
                    marginBottom: '2px',
                    lineHeight: '1.4',
                    wordBreak: 'break-word',
                    color: getLogLevelColor(log.level)
                  }}
                >
                  {showTimestamps && (
                    <span style={{ color: '#888', marginRight: '8px' }}>
                      [{new Date(log.timestamp).toLocaleTimeString()}]
                    </span>
                  )}
                  <span
                    style={{
                      color: getLogLevelColor(log.level),
                      fontWeight: log.level === 'ERROR' ? 'bold' : 'normal'
                    }}
                  >
                    {log.level}:
                  </span>
                  <span style={{ marginLeft: '8px', color: '#e0e0e0' }}>
                    {log.message}
                  </span>
                </div>
              ))
            )}

            {/* Cursor */}
            {isStreaming && (
              <div
                style={{
                  display: 'inline-block',
                  width: '8px',
                  height: '14px',
                  backgroundColor: '#00ff00',
                  animation: 'blink 1s infinite',
                  marginLeft: '4px'
                }}
              />
            )}
          </div>
        </ScrollArea>
      </Paper>

      {/* Console Footer */}
      <Group justify="space-between" mt="sm">
        <Text size="xs" c="dimmed">
          {filteredLogs.length} {filteredLogs.length === 1 ? 'entry' : 'entries'}
          {searchTerm && ` (filtered from ${logs.length})`}
        </Text>

        {selectedText && (
          <Text size="xs" c="blue">
            {selectedText.length} characters selected
          </Text>
        )}
      </Group>

      {/* CSS for blinking cursor */}
      <style>
        {`
          @keyframes blink {
            0%, 50% { opacity: 1; }
            51%, 100% { opacity: 0; }
          }
        `}
      </style>
    </Card>
  );
};

export default ModernConsole;
