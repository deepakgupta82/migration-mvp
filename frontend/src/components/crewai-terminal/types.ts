import { ReactNode } from 'react';

// WebSocket message types from backend
export interface CrewAIMessage {
  type: 'crewai_event' | 'crewai_message' | 'custom_message';
  event_type?: string;
  channel?: string;
  project_id: string;
  correlation_id: string;
  timestamp: string;
  data?: any;
  metadata?: Record<string, any>;
  source?: string;
  payload?: any;
  message?: any;
}

// Processed terminal entry for display
export interface TerminalEntry {
  id: string;
  timestamp: Date;
  type: 'info' | 'success' | 'warning' | 'error' | 'agent' | 'tool' | 'task' | 'crew' | 'progress';
  message: string;
  rawMessage: CrewAIMessage;
  formattedMessage: string;
  color: string;
  icon?: ReactNode;
  metadata?: {
    agent_name?: string;
    tool_name?: string;
    task_name?: string;
    crew_id?: string;
    progress_percentage?: number;
    correlation_id?: string;
  };
}

// WebSocket connection states
export type ConnectionState = 'connecting' | 'connected' | 'disconnected' | 'error' | 'reconnecting';

// Filter options for terminal entries
export interface FilterOptions {
  eventTypes: string[];
  searchTerm: string;
  timeRange?: {
    start: Date;
    end: Date;
  };
  correlationId?: string;
  agentName?: string;
}

// Terminal component props
export interface CrewAITerminalProps {
  projectId?: string;
  correlationId?: string;
  websocketUrl?: string;
  maxEntries?: number;
  autoScroll?: boolean;
  showHeader?: boolean;
  showControls?: boolean;
  className?: string;
  height?: string | number;
  onMessage?: (message: CrewAIMessage) => void;
  onConnectionChange?: (state: ConnectionState) => void;
  onError?: (error: Error) => void;
}

// WebSocket hook return type
export interface UseWebSocketReturn {
  connectionState: ConnectionState;
  messages: CrewAIMessage[];
  error: Error | null;
  reconnect: () => void;
  disconnect: () => void;
  sendMessage: (message: any) => void;
}

// Terminal state management
export interface TerminalState {
  entries: TerminalEntry[];
  filteredEntries: TerminalEntry[];
  isCollapsed: boolean;
  autoScrollEnabled: boolean;
  isUserScrolling: boolean;
  filterOptions: FilterOptions;
  searchTerm: string;
  connectionState: ConnectionState;
  error: Error | null;
}

// Event type mappings for color coding
export const EVENT_TYPE_COLORS: Record<string, string> = {
  crew_start: '#3b82f6', // blue
  crew_complete: '#10b981', // green
  crew_error: '#ef4444', // red
  agent_switch: '#06b6d4', // cyan
  agent_start: '#22c55e', // green
  agent_complete: '#10b981', // green
  agent_error: '#ef4444', // red
  agent_reasoning: '#eab308', // yellow
  tool_execution_start: '#3b82f6', // blue
  tool_execution_complete: '#10b981', // green
  tool_execution_error: '#ef4444', // red
  task_start: '#a855f7', // purple
  task_complete: '#10b981', // green
  task_error: '#ef4444', // red
  progress_update: '#06b6d4', // cyan
  status_update: '#6b7280', // gray
};

// Event type icons/emojis
export const EVENT_TYPE_ICONS: Record<string, string> = {
  crew_start: '🚀',
  crew_complete: '✅',
  crew_error: '❌',
  agent_switch: '🤖',
  agent_start: '🤖',
  agent_complete: '✅',
  agent_error: '❌',
  agent_reasoning: '💭',
  tool_execution_start: '🔧',
  tool_execution_complete: '✅',
  tool_execution_error: '❌',
  task_start: '📋',
  task_complete: '✅',
  task_error: '❌',
  progress_update: '⚙️',
  status_update: 'ℹ️',
};

// ANSI color to CSS color mapping
export const ANSI_COLOR_MAP: Record<string, string> = {
  '\x1b[0m': '', // reset
  '\x1b[30m': '#000000', // black
  '\x1b[31m': '#ef4444', // red
  '\x1b[32m': '#22c55e', // green
  '\x1b[33m': '#eab308', // yellow
  '\x1b[34m': '#3b82f6', // blue
  '\x1b[35m': '#a855f7', // magenta
  '\x1b[36m': '#06b6d4', // cyan
  '\x1b[37m': '#ffffff', // white
  '\x1b[91m': '#f87171', // bright_red
  '\x1b[92m': '#4ade80', // bright_green
  '\x1b[93m': '#facc15', // bright_yellow
  '\x1b[94m': '#60a5fa', // bright_blue
  '\x1b[95m': '#c084fc', // bright_magenta
  '\x1b[96m': '#22d3ee', // bright_cyan
};