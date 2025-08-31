import React from 'react';
import { Group, Text, ActionIcon, Badge, Tooltip } from '@mantine/core';
import {
  IconTerminal,
  IconChevronDown,
  IconChevronUp,
  IconRefresh,
  IconPlayerStop,
  IconWifi,
  IconWifiOff
} from '@tabler/icons-react';
import { ConnectionState } from './types';
import classes from './TerminalHeader.module.css';

interface TerminalHeaderProps {
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  connectionState: ConnectionState;
  entryCount: number;
  onReconnect: () => void;
  onDisconnect: () => void;
}

const TerminalHeader: React.FC<TerminalHeaderProps> = ({
  isCollapsed,
  onToggleCollapse,
  connectionState,
  entryCount,
  onReconnect,
  onDisconnect,
}) => {
  const getConnectionBadgeColor = () => {
    switch (connectionState) {
      case 'connected': return 'green';
      case 'connecting': return 'yellow';
      case 'reconnecting': return 'orange';
      case 'error': return 'red';
      default: return 'gray';
    }
  };

  const getConnectionText = () => {
    switch (connectionState) {
      case 'connected': return 'Connected';
      case 'connecting': return 'Connecting...';
      case 'reconnecting': return 'Reconnecting...';
      case 'error': return 'Error';
      case 'disconnected': return 'Disconnected';
      default: return 'Unknown';
    }
  };

  return (
    <div className={classes.header}>
      <Group justify="space-between" h="100%" px="md">
        {/* Left side - Title and connection status */}
        <Group gap="sm">
          <IconTerminal size={18} className={classes.terminalIcon} />
          <Text size="sm" fw={600} c="white">
            CrewAI Terminal
          </Text>
          <Badge
            size="sm"
            color={getConnectionBadgeColor()}
            variant="filled"
            leftSection={
              connectionState === 'connected' ?
                <IconWifi size={12} /> :
                <IconWifiOff size={12} />
            }
          >
            {getConnectionText()}
          </Badge>
          <Text size="xs" c="dimmed">
            {entryCount} entries
          </Text>
        </Group>

        {/* Right side - Controls */}
        <Group gap="xs">
          <Tooltip label="Reconnect">
            <ActionIcon
              size="sm"
              variant="subtle"
              color="blue"
              onClick={onReconnect}
              disabled={connectionState === 'connecting' || connectionState === 'reconnecting'}
            >
              <IconRefresh size={16} />
            </ActionIcon>
          </Tooltip>

          <Tooltip label="Disconnect">
            <ActionIcon
              size="sm"
              variant="subtle"
              color="red"
              onClick={onDisconnect}
              disabled={connectionState === 'disconnected'}
            >
              <IconPlayerStop size={16} />
            </ActionIcon>
          </Tooltip>

          <Tooltip label={isCollapsed ? "Expand" : "Collapse"}>
            <ActionIcon
              size="sm"
              variant="subtle"
              onClick={onToggleCollapse}
            >
              {isCollapsed ? <IconChevronUp size={16} /> : <IconChevronDown size={16} />}
            </ActionIcon>
          </Tooltip>
        </Group>
      </Group>
    </div>
  );
};

export default TerminalHeader;