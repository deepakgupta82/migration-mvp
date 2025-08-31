import { CrewAIMessage, TerminalEntry, EVENT_TYPE_COLORS, EVENT_TYPE_ICONS, ANSI_COLOR_MAP } from './types';
import { v4 as uuidv4 } from 'uuid';

// Convert ANSI escape sequences to HTML spans with CSS colors
export const parseANSIToHTML = (text: string): string => {
  let result = text;

  // Replace ANSI color codes with HTML spans
  Object.entries(ANSI_COLOR_MAP).forEach(([ansiCode, cssColor]) => {
    if (cssColor) {
      result = result.replace(
        new RegExp(ansiCode.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g'),
        `<span style="color: ${cssColor}">`
      );
    } else {
      // Reset code - close the span
      result = result.replace(
        new RegExp(ansiCode.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g'),
        '</span>'
      );
    }
  });

  // Handle any remaining ANSI codes that might not be in our map
  result = result.replace(/\x1b\[[0-9;]*m/g, '');

  return result;
};

// Extract event type from message
export const getEventType = (message: CrewAIMessage): string => {
  if (message.event_type) {
    return message.event_type;
  }

  if (message.type === 'crewai_message' && message.channel) {
    return message.channel;
  }

  return 'info';
};

// Get color for event type
export const getEventColor = (eventType: string): string => {
  return EVENT_TYPE_COLORS[eventType] || EVENT_TYPE_COLORS.status_update || '#6b7280';
};

// Get icon for event type
export const getEventIcon = (eventType: string): string => {
  return EVENT_TYPE_ICONS[eventType] || EVENT_TYPE_ICONS.status_update || 'ℹ️';
};

// Process a single CrewAI message into a terminal entry
export const processMessage = (message: CrewAIMessage): TerminalEntry => {
  const eventType = getEventType(message);
  const timestamp = new Date(message.timestamp);
  const color = getEventColor(eventType);
  const icon = getEventIcon(eventType);

  // Extract formatted message from data if available
  let formattedMessage = '';
  let rawMessage = '';

  if (message.data?.formatted_message) {
    formattedMessage = parseANSIToHTML(message.data.formatted_message);
    rawMessage = message.data.formatted_message;
  } else if (message.message) {
    formattedMessage = parseANSIToHTML(message.message);
    rawMessage = message.message;
  } else if (message.payload) {
    formattedMessage = parseANSIToHTML(JSON.stringify(message.payload, null, 2));
    rawMessage = JSON.stringify(message.payload);
  } else {
    formattedMessage = parseANSIToHTML(JSON.stringify(message.data || message, null, 2));
    rawMessage = JSON.stringify(message.data || message);
  }

  // Extract metadata
  const metadata = {
    agent_name: message.data?.agent_name || message.metadata?.agent_name,
    tool_name: message.data?.tool_name || message.metadata?.tool_name,
    task_name: message.data?.task_name || message.metadata?.task_name,
    crew_id: message.data?.crew_id || message.metadata?.crew_id,
    progress_percentage: message.data?.progress_percentage,
    correlation_id: message.correlation_id,
  };

  return {
    id: uuidv4(),
    timestamp,
    type: getEntryType(eventType),
    message: rawMessage,
    rawMessage: message,
    formattedMessage,
    color,
    icon,
    metadata,
  };
};

// Determine entry type based on event type
const getEntryType = (eventType: string): TerminalEntry['type'] => {
  const typeMap: Record<string, TerminalEntry['type']> = {
    crew_start: 'crew',
    crew_complete: 'success',
    crew_error: 'error',
    agent_start: 'agent',
    agent_complete: 'success',
    agent_error: 'error',
    agent_switch: 'agent',
    agent_reasoning: 'info',
    tool_execution_start: 'tool',
    tool_execution_complete: 'success',
    tool_execution_error: 'error',
    task_start: 'task',
    task_complete: 'success',
    task_error: 'error',
    progress_update: 'progress',
    status_update: 'info',
  };

  return typeMap[eventType] || 'info';
};

// Filter entries based on search term and filters
export const filterEntries = (
  entries: TerminalEntry[],
  searchTerm: string,
  eventTypes: string[] = []
): TerminalEntry[] => {
  return entries.filter(entry => {
    // Filter by event types
    if (eventTypes.length > 0 && !eventTypes.includes(entry.type)) {
      return false;
    }

    // Filter by search term
    if (searchTerm) {
      const searchLower = searchTerm.toLowerCase();
      const messageMatch = entry.message.toLowerCase().includes(searchLower);
      const metadataMatch = Object.values(entry.metadata || {})
        .some(value => value && String(value).toLowerCase().includes(searchLower));

      if (!messageMatch && !metadataMatch) {
        return false;
      }
    }

    return true;
  });
};

// Create a progress bar string
export const createProgressBar = (percentage: number, width: number = 20): string => {
  const filled = Math.round(width * percentage / 100);
  const empty = width - filled;
  const bar = '█'.repeat(filled) + '░'.repeat(empty);
  return `[${bar}]`;
};

// Format timestamp for display
export const formatTimestamp = (date: Date): string => {
  return date.toLocaleTimeString('en-US', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
};

// Debounce function for high-frequency updates
export const debounce = <T extends (...args: any[]) => any>(
  func: T,
  wait: number
): ((...args: Parameters<T>) => void) => {
  let timeout: NodeJS.Timeout | null = null;

  return (...args: Parameters<T>) => {
    if (timeout) {
      clearTimeout(timeout);
    }

    timeout = setTimeout(() => {
      func(...args);
    }, wait);
  };
};

// Throttle function for scroll events
export const throttle = <T extends (...args: any[]) => any>(
  func: T,
  limit: number
): ((...args: Parameters<T>) => void) => {
  let inThrottle: boolean;

  return (...args: Parameters<T>) => {
    if (!inThrottle) {
      func(...args);
      inThrottle = true;
      setTimeout(() => inThrottle = false, limit);
    }
  };
};