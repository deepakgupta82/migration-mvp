import React, { useState, useEffect, useMemo, useRef } from 'react';
import { Paper, Box, Collapse, Alert, Loader, Text } from '@mantine/core';
import { IconTerminal, IconChevronDown, IconChevronUp, IconRefresh, IconX } from '@tabler/icons-react';
import { CrewAITerminalProps, TerminalEntry, FilterOptions } from './types';
import { useWebSocket, useTerminalProcessor, useTerminalScroll } from './hooks';
import { processMessage, filterEntries, formatTimestamp } from './utils';
import TerminalHeader from './TerminalHeader';
import TerminalOutput from './TerminalOutput';
import TerminalControls from './TerminalControls';
import classes from './CrewAITerminal.module.css';

const CrewAITerminal: React.FC<CrewAITerminalProps> = ({
  projectId,
  correlationId,
  websocketUrl = 'ws://localhost:8009/ws/crewai',
  maxEntries = 1000,
  autoScroll = true,
  showHeader = true,
  showControls = true,
  className,
  height = 400,
  onMessage,
  onConnectionChange,
  onError,
}) => {
  // State management
  const [entries, setEntries] = useState<TerminalEntry[]>([]);
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [autoScrollEnabled, setAutoScrollEnabled] = useState(autoScroll);
  const [filterOptions, setFilterOptions] = useState<FilterOptions>({
    eventTypes: [],
    searchTerm: '',
  });

  // WebSocket connection
  const {
    connectionState,
    messages,
    error: wsError,
    reconnect,
    disconnect,
  } = useWebSocket(websocketUrl, ['crewai_activities', 'crewai_terminal'], projectId);

  // Process messages into terminal entries
  const processedMessages = useTerminalProcessor(messages, maxEntries);

  // Container ref for scrolling
  const containerRef = useRef<HTMLDivElement>(null);

  // Scroll management
  const { scrollToBottom, handleScroll, isUserScrolling } = useTerminalScroll(
    autoScrollEnabled,
    containerRef
  );

  // Process incoming messages
  useEffect(() => {
    const newEntries = processedMessages.map(processMessage);
    setEntries(prev => {
      const combined = [...prev, ...newEntries];
      return combined.slice(-maxEntries);
    });

    // Notify parent component
    newEntries.forEach(entry => {
      onMessage?.(entry.rawMessage);
    });
  }, [processedMessages, maxEntries, onMessage]);

  // Auto-scroll when new entries arrive
  useEffect(() => {
    if (entries.length > 0 && !isUserScrolling) {
      scrollToBottom();
    }
  }, [entries, isUserScrolling, scrollToBottom]);

  // Notify connection state changes
  useEffect(() => {
    onConnectionChange?.(connectionState);
  }, [connectionState, onConnectionChange]);

  // Notify errors
  useEffect(() => {
    if (wsError) {
      onError?.(wsError);
    }
  }, [wsError, onError]);

  // Filter entries based on current filters
  const filteredEntries = useMemo(() => {
    return filterEntries(entries, filterOptions.searchTerm, filterOptions.eventTypes);
  }, [entries, filterOptions]);

  // Handle filter changes
  const handleFilterChange = (newFilters: Partial<FilterOptions>) => {
    setFilterOptions(prev => ({ ...prev, ...newFilters }));
  };

  // Clear all entries
  const handleClear = () => {
    setEntries([]);
  };

  // Toggle collapse
  const toggleCollapse = () => {
    setIsCollapsed(prev => !prev);
  };

  // Get connection status color
  const getConnectionStatusColor = () => {
    switch (connectionState) {
      case 'connected': return 'green';
      case 'connecting': return 'yellow';
      case 'reconnecting': return 'orange';
      case 'error': return 'red';
      default: return 'gray';
    }
  };

  return (
    <Paper
      shadow="sm"
      className={`${classes.terminal} ${className || ''}`}
      style={{ height: typeof height === 'number' ? `${height}px` : height }}
    >
      {/* Header */}
      {showHeader && (
        <TerminalHeader
          isCollapsed={isCollapsed}
          onToggleCollapse={toggleCollapse}
          connectionState={connectionState}
          entryCount={entries.length}
          onReconnect={reconnect}
          onDisconnect={disconnect}
        />
      )}

      {/* Collapsible Content */}
      <Collapse in={!isCollapsed}>
        <Box className={classes.content}>
          {/* Connection Status */}
          {connectionState !== 'connected' && (
            <Alert
              color={getConnectionStatusColor()}
              variant="light"
              className={classes.statusAlert}
              icon={connectionState === 'connecting' || connectionState === 'reconnecting' ? <Loader size="sm" /> : undefined}
            >
              <Text size="sm">
                {connectionState === 'connecting' && 'Connecting to CrewAI terminal...'}
                {connectionState === 'reconnecting' && 'Reconnecting to CrewAI terminal...'}
                {connectionState === 'error' && `Connection error: ${wsError?.message || 'Unknown error'}`}
                {connectionState === 'disconnected' && 'Disconnected from CrewAI terminal'}
              </Text>
            </Alert>
          )}

          {/* Controls */}
          {showControls && (
            <TerminalControls
              filterOptions={filterOptions}
              onFilterChange={handleFilterChange}
              onClear={handleClear}
              autoScrollEnabled={autoScrollEnabled}
              onToggleAutoScroll={() => setAutoScrollEnabled(prev => !prev)}
              isUserScrolling={isUserScrolling}
            />
          )}

          {/* Terminal Output */}
          <TerminalOutput
            entries={filteredEntries}
            containerRef={containerRef}
            onScroll={handleScroll}
            autoScrollEnabled={autoScrollEnabled}
            isUserScrolling={isUserScrolling}
          />
        </Box>
      </Collapse>
    </Paper>
  );
};

export default CrewAITerminal;