import React, { useState } from 'react';
import { Group, TextInput, MultiSelect, ActionIcon, Tooltip, Switch, Text } from '@mantine/core';
import {
  IconSearch,
  IconFilter,
  IconClearAll,
  IconPlayerPlay,
  IconPlayerPause,
  IconChevronDown,
  IconChevronUp
} from '@tabler/icons-react';
import { FilterOptions } from './types';
import classes from './TerminalControls.module.css';

interface TerminalControlsProps {
  filterOptions: FilterOptions;
  onFilterChange: (filters: Partial<FilterOptions>) => void;
  onClear: () => void;
  autoScrollEnabled: boolean;
  onToggleAutoScroll: () => void;
  isUserScrolling: boolean;
}

const EVENT_TYPE_OPTIONS = [
  { value: 'info', label: 'Info' },
  { value: 'success', label: 'Success' },
  { value: 'warning', label: 'Warning' },
  { value: 'error', label: 'Error' },
  { value: 'agent', label: 'Agent' },
  { value: 'tool', label: 'Tool' },
  { value: 'task', label: 'Task' },
  { value: 'crew', label: 'Crew' },
  { value: 'progress', label: 'Progress' },
];

const TerminalControls: React.FC<TerminalControlsProps> = ({
  filterOptions,
  onFilterChange,
  onClear,
  autoScrollEnabled,
  onToggleAutoScroll,
  isUserScrolling,
}) => {
  const [showFilters, setShowFilters] = useState(false);

  const handleSearchChange = (value: string) => {
    onFilterChange({ searchTerm: value });
  };

  const handleEventTypeChange = (values: string[]) => {
    onFilterChange({ eventTypes: values });
  };

  return (
    <div className={classes.controls}>
      <Group justify="space-between" gap="sm" px="md" py="xs">
        {/* Left side - Search and filters */}
        <Group gap="sm">
          <TextInput
            placeholder="Search terminal entries..."
            value={filterOptions.searchTerm}
            onChange={(event) => handleSearchChange(event.currentTarget.value)}
            leftSection={<IconSearch size={16} />}
            size="xs"
            className={classes.searchInput}
            style={{ width: 200 }}
          />

          <Tooltip label={showFilters ? "Hide filters" : "Show filters"}>
            <ActionIcon
              size="sm"
              variant={showFilters ? "filled" : "subtle"}
              onClick={() => setShowFilters(!showFilters)}
            >
              <IconFilter size={16} />
            </ActionIcon>
          </Tooltip>

          {showFilters && (
            <MultiSelect
              data={EVENT_TYPE_OPTIONS}
              value={filterOptions.eventTypes}
              onChange={handleEventTypeChange}
              placeholder="Filter by type"
              size="xs"
              className={classes.filterSelect}
              style={{ width: 180 }}
              clearable
            />
          )}
        </Group>

        {/* Right side - Controls */}
        <Group gap="sm">
          {/* Auto-scroll toggle */}
          <Group gap="xs">
            <Text size="xs" c="dimmed">
              Auto-scroll
            </Text>
            <Switch
              size="xs"
              checked={autoScrollEnabled}
              onChange={onToggleAutoScroll}
              color="blue"
            />
            {isUserScrolling && autoScrollEnabled && (
              <Text size="xs" c="orange" fw={500}>
                Paused
              </Text>
            )}
          </Group>

          {/* Clear button */}
          <Tooltip label="Clear all entries">
            <ActionIcon
              size="sm"
              variant="subtle"
              color="red"
              onClick={onClear}
            >
              <IconClearAll size={16} />
            </ActionIcon>
          </Tooltip>
        </Group>
      </Group>
    </div>
  );
};

export default TerminalControls;