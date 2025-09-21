/**
 * Message Validation and Normalization Utilities
 * Provides robust validation, parsing, and normalization for standardized messages
 */

import {
  MessageType,
  ValidationResult,
  StandardizedMessage,
  AnyStandardizedMessage,
  StandardizedAssessmentMessage,
  StandardizedProcessingMessage,
  StandardizedLogMessage,
  StandardizedStatsMessage,
  LegacyBaseMessage,
  MESSAGE_SCHEMAS,
  PROJECT_ID_PATTERNS,
  LEGACY_TYPE_MAPPING,
  LogLevel
} from '../types/messages';

/**
 * Validates a project ID against known patterns
 */
export function validateProjectId(projectId: string): boolean {
  if (!projectId || typeof projectId !== 'string') {
    return false;
  }

  return PROJECT_ID_PATTERNS.some(pattern => pattern.test(projectId));
}

/**
 * Normalizes a project ID to a consistent format
 */
export function normalizeProjectId(projectId: string): string {
  if (!projectId || typeof projectId !== 'string') {
    throw new Error('Invalid project ID: must be a non-empty string');
  }

  // Trim whitespace and convert to lowercase for consistency
  return projectId.trim().toLowerCase();
}

/**
 * Validates and normalizes a timestamp
 */
export function validateAndNormalizeTimestamp(timestamp?: string): string {
  if (!timestamp) {
    return new Date().toISOString();
  }

  const date = new Date(timestamp);
  if (isNaN(date.getTime())) {
    // If invalid, use current time
    console.warn(`Invalid timestamp: ${timestamp}, using current time`);
    return new Date().toISOString();
  }

  return date.toISOString();
}

/**
 * Determines message type from legacy message
 */
export function determineMessageType(message: LegacyBaseMessage): MessageType | null {
  const typeMapping = LEGACY_TYPE_MAPPING[message.type];
  if (typeMapping) {
    return typeMapping.messageType;
  }

  // Fallback logic for unmapped types
  if (message.type.includes('agent') || message.type.includes('tool')) {
    return MessageType.ASSESSMENT;
  }
  if (message.type.includes('operation') || message.type.includes('progress') || message.type.includes('processing')) {
    return MessageType.PROCESSING;
  }
  if (message.type.includes('log')) {
    return MessageType.LOGS;
  }
  if (message.type.includes('stats')) {
    return MessageType.STATS;
  }

  return null;
}

/**
 * Validates a message against its schema
 */
export function validateMessage(message: any, expectedMessageType?: MessageType): ValidationResult {
  const errors: string[] = [];

  // Basic structure validation
  if (!message || typeof message !== 'object') {
    errors.push('Message must be a valid object');
    return { isValid: false, errors };
  }

  // Determine message type
  let messageType = expectedMessageType;
  if (!messageType) {
    const determinedType = determineMessageType(message);
    if (!determinedType) {
      errors.push(`Unable to determine message type for: ${message.type}`);
      return { isValid: false, errors };
    }
    messageType = determinedType;
  }

  const schema = MESSAGE_SCHEMAS[messageType];
  if (!schema) {
    errors.push(`No schema found for message type: ${messageType}`);
    return { isValid: false, errors };
  }

  // Validate required fields
  for (const field of schema.required) {
    if (!(field in message) || message[field] === null || message[field] === undefined) {
      if (field === 'project_id' && !message.project_id) {
        errors.push(`Missing required field: ${field}`);
      } else if (field !== 'project_id') {
        errors.push(`Missing required field: ${field}`);
      }
    }
  }

  // Validate type enum
  if (message.type && !(schema.typeEnum as any[]).includes(message.type)) {
    errors.push(`Invalid type '${message.type}' for ${messageType} messages. Valid types: ${schema.typeEnum.join(', ')}`);
  }

  // Validate project ID if present
  if (message.project_id && !validateProjectId(message.project_id)) {
    errors.push(`Invalid project ID format: ${message.project_id}`);
  }

  // Validate log level for log messages
  if (messageType === MessageType.LOGS && message.level) {
    const validLevels: LogLevel[] = ['INFO', 'WARNING', 'ERROR', 'DEBUG', 'SUCCESS'];
    if (!validLevels.includes(message.level)) {
      errors.push(`Invalid log level '${message.level}'. Valid levels: ${validLevels.join(', ')}`);
    }
  }

  // Validate progress percentage
  if (message.progress_percentage !== undefined) {
    const progress = Number(message.progress_percentage);
    if (isNaN(progress) || progress < 0 || progress > 100) {
      errors.push(`Invalid progress percentage: ${message.progress_percentage}. Must be between 0 and 100`);
    }
  }

  // If there are errors, return them
  if (errors.length > 0) {
    return { isValid: false, errors };
  }

  // Normalize the message
  try {
    const normalizedMessage = normalizeMessage(message, messageType);
    return { isValid: true, errors: [], normalizedMessage };
  } catch (error) {
    return { isValid: false, errors: [`Normalization failed: ${(error as Error).message}`] };
  }
}

/**
 * Normalizes a message to standardized format
 */
export function normalizeMessage(message: any, messageType: MessageType): AnyStandardizedMessage {
  const baseMessage: StandardizedMessage = {
    id: message.id || generateMessageId(),
    type: message.type,
    timestamp: validateAndNormalizeTimestamp(message.timestamp),
    project_id: message.project_id ? normalizeProjectId(message.project_id) : '',
    source: message.source || 'unknown',
    version: message.version || '1.0',
    data: message.data || {},
    metadata: message.metadata || {}
  };

  switch (messageType) {
    case MessageType.ASSESSMENT:
      return {
        ...baseMessage,
        type: message.type as StandardizedAssessmentMessage['type'],
        agent_name: message.agent_name,
        tool: message.tool,
        tool_input: message.tool_input,
        output: message.output,
        error: message.error,
        status: message.status,
        goal: message.goal,
        action_description: message.action_description,
        log: message.log,
        progress_percentage: message.progress_percentage ? Number(message.progress_percentage) : undefined,
        current_step: message.current_step ? Number(message.current_step) : undefined,
        total_steps: message.total_steps ? Number(message.total_steps) : undefined,
      } as StandardizedAssessmentMessage;

    case MessageType.PROCESSING:
      return {
        ...baseMessage,
        type: message.type as StandardizedProcessingMessage['type'],
        operation_name: message.operation_name,
        current_step: message.current_step ? Number(message.current_step) : undefined,
        total_steps: message.total_steps ? Number(message.total_steps) : undefined,
        progress_percentage: message.progress_percentage ? Number(message.progress_percentage) : undefined,
        message: message.message,
        service: message.service,
        document_id: message.document_id,
        file_name: message.file_name,
        file_size: message.file_size ? Number(message.file_size) : undefined,
        processing_time_ms: message.processing_time_ms ? Number(message.processing_time_ms) : undefined,
      } as StandardizedProcessingMessage;

    case MessageType.LOGS:
      return {
        ...baseMessage,
        type: message.type as StandardizedLogMessage['type'],
        level: message.level || 'INFO',
        service: message.service || 'unknown',
        message: message.message || '',
        component: message.component,
        user_id: message.user_id,
        session_id: message.session_id,
        correlation_id: message.correlation_id,
      } as StandardizedLogMessage;

    case MessageType.STATS:
      return {
        ...baseMessage,
        type: message.type as StandardizedStatsMessage['type'],
        event_type: message.event_type,
        changes: message.changes,
        metrics: message.metrics,
        period: message.period,
      } as StandardizedStatsMessage;

    default:
      throw new Error(`Unknown message type: ${messageType}`);
  }
}

/**
 * Parses and validates a raw message string
 */
export function parseAndValidateMessage(data: string, expectedMessageType?: MessageType): ValidationResult {
  try {
    const message = JSON.parse(data);
    return validateMessage(message, expectedMessageType);
  } catch (error) {
    return {
      isValid: false,
      errors: [`Failed to parse JSON: ${(error as Error).message}`]
    };
  }
}

/**
 * Generates a unique message ID
 */
export function generateMessageId(): string {
  return `${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

/**
 * Checks if a message matches the expected type and project
 */
export function messageMatchesCriteria(
  message: StandardizedMessage,
  expectedMessageType: MessageType,
  projectId?: string
): boolean {
  // Check project ID match if specified
  if (projectId && message.project_id !== projectId) {
    return false;
  }

  // Check message type match using schema
  const schema = MESSAGE_SCHEMAS[expectedMessageType];
  if (!schema) {
    return false;
  }

  return (schema.typeEnum as any[]).includes(message.type);
}

/**
 * Converts legacy message format to standardized format
 */
export function convertLegacyMessage(legacyMessage: LegacyBaseMessage): AnyStandardizedMessage | null {
  const messageType = determineMessageType(legacyMessage);
  if (!messageType) {
    console.warn(`Unable to convert legacy message with type: ${legacyMessage.type}`);
    return null;
  }

  const validation = validateMessage(legacyMessage, messageType);
  if (!validation.isValid) {
    console.warn(`Legacy message validation failed:`, validation.errors);
    return null;
  }

  return validation.normalizedMessage ?? null;
}

/**
 * Batch validates multiple messages
 */
export function validateMessages(messages: any[], expectedMessageType?: MessageType): ValidationResult[] {
  return messages.map(message => validateMessage(message, expectedMessageType));
}

/**
 * Filters messages by type and project
 */
export function filterMessages(
  messages: StandardizedMessage[],
  messageType: MessageType,
  projectId?: string
): StandardizedMessage[] {
  return messages.filter(message => messageMatchesCriteria(message, messageType, projectId));
}