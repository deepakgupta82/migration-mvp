/**
 * Standardized Message Types and Validation for Migration Platform
 * Provides consistent message structure and robust validation across services
 */

// Core message types
export enum MessageType {
  ASSESSMENT = 'assessment',
  PROCESSING = 'processing',
  LOGS = 'logs',
  STATS = 'stats'
}

// Message validation result
export interface ValidationResult {
  isValid: boolean;
  errors: string[];
  normalizedMessage?: AnyStandardizedMessage;
}

// Standardized base message interface
export interface StandardizedMessage {
  id?: string; // Optional unique identifier
  type: string;
  timestamp: string;
  project_id: string; // Required for routing
  source?: string; // Service or component that sent the message
  version?: string; // Message format version for backward compatibility
  data?: Record<string, any>; // Additional payload data
  metadata?: Record<string, any>; // Additional metadata
}

// Assessment message types
export type AssessmentMessageType =
  | 'agent_action'
  | 'tool_result'
  | 'tool_error'
  | 'agent_finish'
  | 'agent_start'
  | 'assessment_progress'
  | 'assessment_complete'
  | 'assessment_failed'
  // Report markdown streaming (extended types)
  | 'FINAL_REPORT_MARKDOWN_START'
  | 'FINAL_REPORT_MARKDOWN_END';

export interface StandardizedAssessmentMessage extends StandardizedMessage {
  type: AssessmentMessageType;
  agent_name?: string;
  tool?: string;
  tool_input?: string;
  output?: string;
  error?: string;
  status?: string;
  goal?: string;
  action_description?: string;
  log?: string;
  progress_percentage?: number;
  current_step?: number;
  total_steps?: number;
}

// Processing message types
export type ProcessingMessageType =
  | 'operation_progress'
  | 'operation_completed'
  | 'operation_failed'
  | 'document_processing_start'
  | 'document_processing_progress'
  | 'document_processing_complete'
  | 'document_processing_failed';

export interface StandardizedProcessingMessage extends StandardizedMessage {
  type: ProcessingMessageType;
  operation_name?: string;
  current_step?: number;
  total_steps?: number;
  progress_percentage?: number;
  message?: string;
  service?: string;
  document_id?: string;
  file_name?: string;
  file_size?: number;
  processing_time_ms?: number;
}

// Log message types
export type LogMessageType =
  | 'log_entry'
  | 'error_log'
  | 'warning_log'
  | 'info_log'
  | 'debug_log'
  | 'system_log';

export type LogLevel = 'INFO' | 'WARNING' | 'ERROR' | 'DEBUG' | 'SUCCESS';

export interface StandardizedLogMessage extends StandardizedMessage {
  type: LogMessageType;
  level: LogLevel;
  service: string;
  message: string;
  component?: string;
  user_id?: string;
  session_id?: string;
  correlation_id?: string;
}

// Stats message types
export type StatsMessageType =
  | 'project_stats_update'
  | 'platform_stats_update'
  | 'performance_metrics'
  | 'usage_stats'
  | 'error_stats';

export interface StandardizedStatsMessage extends StandardizedMessage {
  type: StatsMessageType;
  event_type?: string;
  changes?: Record<string, any>;
  metrics?: Record<string, number>;
  period?: {
    start: string;
    end: string;
  };
}

// Union type for all standardized messages
export type AnyStandardizedMessage =
  | StandardizedAssessmentMessage
  | StandardizedProcessingMessage
  | StandardizedLogMessage
  | StandardizedStatsMessage;

// Legacy message interfaces for backward compatibility
export interface LegacyBaseMessage {
  type: string;
  timestamp?: string;
  project_id?: string;
  data?: any;
}

export interface LegacyAssessmentMessage extends LegacyBaseMessage {
  type: string; // Will be validated against AssessmentMessageType
  agent_name?: string;
  tool?: string;
  tool_input?: string;
  output?: string;
  error?: string;
  status?: string;
  goal?: string;
  action_description?: string;
  log?: string;
}

export interface LegacyProcessingMessage extends LegacyBaseMessage {
  type: string; // Will be validated against ProcessingMessageType
  operation_name?: string;
  current_step?: number;
  total_steps?: number;
  progress_percentage?: number;
  message?: string;
  service?: string;
}

export interface LegacyLogMessage extends LegacyBaseMessage {
  type: string; // Usually 'log_entry'
  level?: LogLevel;
  service?: string;
  message?: string;
  metadata?: Record<string, any>;
}

export interface LegacyStatsMessage extends LegacyBaseMessage {
  type: string; // Will be validated against StatsMessageType
  event_type?: string;
  changes?: Record<string, any>;
}

// Message validation schemas
export const MESSAGE_SCHEMAS = {
  [MessageType.ASSESSMENT]: {
    required: ['type', 'project_id'],
    typeEnum: ['agent_action', 'tool_result', 'tool_error', 'agent_finish', 'agent_start', 'assessment_progress', 'assessment_complete', 'assessment_failed'] as AssessmentMessageType[],
    optional: ['agent_name', 'tool', 'tool_input', 'output', 'error', 'status', 'goal', 'action_description', 'log', 'progress_percentage', 'current_step', 'total_steps', 'timestamp', 'source', 'version', 'data', 'metadata']
  },
  [MessageType.PROCESSING]: {
    required: ['type', 'project_id'],
    typeEnum: ['operation_progress', 'operation_completed', 'operation_failed', 'document_processing_start', 'document_processing_progress', 'document_processing_complete', 'document_processing_failed'] as ProcessingMessageType[],
    optional: ['operation_name', 'current_step', 'total_steps', 'progress_percentage', 'message', 'service', 'document_id', 'file_name', 'file_size', 'processing_time_ms', 'timestamp', 'source', 'version', 'data', 'metadata']
  },
  [MessageType.LOGS]: {
    required: ['type', 'project_id', 'level', 'service', 'message'],
    typeEnum: ['log_entry', 'error_log', 'warning_log', 'info_log', 'debug_log', 'system_log'] as LogMessageType[],
    optional: ['component', 'user_id', 'session_id', 'correlation_id', 'timestamp', 'source', 'version', 'data', 'metadata']
  },
  [MessageType.STATS]: {
    required: ['type', 'project_id'],
    typeEnum: ['project_stats_update', 'platform_stats_update', 'performance_metrics', 'usage_stats', 'error_stats'] as StatsMessageType[],
    optional: ['event_type', 'changes', 'metrics', 'period', 'timestamp', 'source', 'version', 'data', 'metadata']
  }
} as const;

// Project ID validation patterns
export const PROJECT_ID_PATTERNS = [
  /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i, // UUID v4
  /^[a-zA-Z0-9_-]+$/, // Alphanumeric with dashes and underscores
  /^[0-9]+$/, // Numeric only
];

// Message type mapping for legacy compatibility
export const LEGACY_TYPE_MAPPING: Record<string, { messageType: MessageType; standardizedType?: string }> = {
  // Assessment mappings
  'agent_action': { messageType: MessageType.ASSESSMENT, standardizedType: 'agent_action' },
  'tool_result': { messageType: MessageType.ASSESSMENT, standardizedType: 'tool_result' },
  'tool_error': { messageType: MessageType.ASSESSMENT, standardizedType: 'tool_error' },
  'agent_finish': { messageType: MessageType.ASSESSMENT, standardizedType: 'agent_finish' },
  'agent_start': { messageType: MessageType.ASSESSMENT, standardizedType: 'agent_start' },

  // Processing mappings
  'operation_progress': { messageType: MessageType.PROCESSING, standardizedType: 'operation_progress' },
  'operation_completed': { messageType: MessageType.PROCESSING, standardizedType: 'operation_completed' },
  'operation_failed': { messageType: MessageType.PROCESSING, standardizedType: 'operation_failed' },
  'progress': { messageType: MessageType.PROCESSING, standardizedType: 'operation_progress' },

  // Log mappings
  'log_entry': { messageType: MessageType.LOGS, standardizedType: 'log_entry' },

  // Stats mappings
  'project_stats_update': { messageType: MessageType.STATS, standardizedType: 'project_stats_update' },
  'platform_stats_update': { messageType: MessageType.STATS, standardizedType: 'platform_stats_update' },
  'stats': { messageType: MessageType.STATS, standardizedType: 'project_stats_update' },
};